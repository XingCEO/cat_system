"""
Turnover Tracker Service - Track high turnover limit-up stocks performance
追蹤高周轉漲停股的後續表現
"""
import logging
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session_maker
from models.turnover import TurnoverTrack, TurnoverRanking
from services.data_fetcher import data_fetcher
from utils.date_utils import get_latest_trading_day, get_trading_days_between, parse_date, get_taiwan_today

logger = logging.getLogger(__name__)


class TurnoverTrackerService:
    """高周轉漲停股追蹤服務"""

    async def create_track(
        self,
        trigger_date: str,
        symbols: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        建立追蹤任務

        Args:
            trigger_date: 觸發日期 (YYYY-MM-DD)
            symbols: 指定股票列表，None 表示追蹤當日所有高周轉漲停股

        Returns:
            追蹤任務建立結果
        """
        try:
            trigger_dt = parse_date(trigger_date)
            if trigger_dt is None:
                return {"success": False, "error": "無效的日期格式"}

            async with async_session_maker() as session:
                # 取得當日高周轉漲停股
                if symbols is None:
                    # 查詢當日周轉率前200名中的漲停股
                    query = select(TurnoverRanking).where(
                        and_(
                            TurnoverRanking.date == trigger_dt,
                            TurnoverRanking.is_limit_up == True,
                            TurnoverRanking.turnover_rank <= 200
                        )
                    )
                    result = await session.execute(query)
                    rankings = result.scalars().all()

                    if not rankings:
                        # 如果資料庫沒有，嘗試從 analyzer 獲取
                        from services.high_turnover_analyzer import high_turnover_analyzer
                        analyzer_result = await high_turnover_analyzer.get_high_turnover_limit_up(
                            date=trigger_date
                        )
                        if analyzer_result.get("success"):
                            symbols = [item["symbol"] for item in analyzer_result.get("items", [])]
                        else:
                            return {"success": False, "error": "無法取得當日漲停股資料"}
                    else:
                        symbols = [r.symbol for r in rankings]

                if not symbols:
                    return {"success": False, "error": "無符合條件的股票"}

                # 建立追蹤記錄
                created_count = 0
                skipped_count = 0

                for symbol in symbols:
                    # 檢查是否已存在
                    existing = await session.execute(
                        select(TurnoverTrack).where(
                            and_(
                                TurnoverTrack.symbol == symbol,
                                TurnoverTrack.trigger_date == trigger_dt
                            )
                        )
                    )
                    if existing.scalar_one_or_none():
                        skipped_count += 1
                        continue

                    # 取得觸發價格和排名
                    ranking_query = select(TurnoverRanking).where(
                        and_(
                            TurnoverRanking.date == trigger_dt,
                            TurnoverRanking.symbol == symbol
                        )
                    )
                    ranking_result = await session.execute(ranking_query)
                    ranking = ranking_result.scalar_one_or_none()

                    trigger_price = ranking.close_price if ranking else 0
                    turnover_rank = ranking.turnover_rank if ranking else 0

                    track = TurnoverTrack(
                        symbol=symbol,
                        trigger_date=trigger_dt,
                        turnover_rank=turnover_rank,
                        trigger_price=trigger_price or 0,
                        is_complete=False
                    )
                    session.add(track)
                    created_count += 1

                await session.commit()

                return {
                    "success": True,
                    "message": f"追蹤任務已建立",
                    "date": trigger_date,
                    "created_count": created_count,
                    "skipped_count": skipped_count,
                    "symbols": symbols
                }

        except Exception as e:
            logger.error(f"建立追蹤任務失敗: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def update_track_results(self) -> Dict[str, Any]:
        """
        更新所有未完成追蹤任務的結果

        此方法應由定時任務呼叫，每日收盤後執行
        """
        try:
            async with async_session_maker() as session:
                # 取得所有未完成的追蹤任務
                query = select(TurnoverTrack).where(
                    TurnoverTrack.is_complete == False
                )
                result = await session.execute(query)
                tracks = result.scalars().all()

                if not tracks:
                    return {"success": True, "message": "無待更新的追蹤任務", "updated": 0}

                updated_count = 0
                today = get_taiwan_today()

                for track in tracks:
                    trigger_dt = track.trigger_date
                    days_passed = (today - trigger_dt).days

                    if days_passed < 1:
                        continue  # 還未過隔日

                    try:
                        # 取得該股票的歷史價格
                        history = await self._get_stock_history(
                            track.symbol,
                            trigger_dt,
                            days=10
                        )

                        if not history:
                            continue

                        # 計算各時間點的漲跌幅
                        trigger_price = track.trigger_price
                        if trigger_price <= 0:
                            continue

                        # Day 1
                        if days_passed >= 1 and track.day1_change is None:
                            day1_data = self._get_day_data(history, trigger_dt, 1)
                            if day1_data:
                                track.day1_change = round(
                                    (day1_data["close"] - trigger_price) / trigger_price * 100, 2
                                )
                                # 判斷是否繼續漲停 (漲幅 >= 9.5%)
                                track.day1_limit_up = day1_data.get("change_pct", 0) >= 9.5

                        # Day 3
                        if days_passed >= 3 and track.day3_change is None:
                            day3_data = self._get_day_data(history, trigger_dt, 3)
                            if day3_data:
                                track.day3_change = round(
                                    (day3_data["close"] - trigger_price) / trigger_price * 100, 2
                                )

                        # Day 5
                        if days_passed >= 5 and track.day5_change is None:
                            day5_data = self._get_day_data(history, trigger_dt, 5)
                            if day5_data:
                                track.day5_change = round(
                                    (day5_data["close"] - trigger_price) / trigger_price * 100, 2
                                )

                        # Day 7
                        if days_passed >= 7 and track.day7_change is None:
                            day7_data = self._get_day_data(history, trigger_dt, 7)
                            if day7_data:
                                track.day7_change = round(
                                    (day7_data["close"] - trigger_price) / trigger_price * 100, 2
                                )

                        # 檢查是否完成 (7日後資料已填入)
                        if track.day7_change is not None:
                            track.is_complete = True

                        updated_count += 1

                    except Exception as e:
                        logger.warning(f"更新 {track.symbol} 追蹤結果失敗: {e}")
                        continue

                await session.commit()

                return {
                    "success": True,
                    "message": f"已更新 {updated_count} 筆追蹤結果",
                    "updated": updated_count
                }

        except Exception as e:
            logger.error(f"更新追蹤結果失敗: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def get_track_stats(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        取得追蹤統計

        Args:
            start_date: 開始日期
            end_date: 結束日期
        """
        try:
            async with async_session_maker() as session:
                query = select(TurnoverTrack)

                conditions = []
                if start_date:
                    start_dt = parse_date(start_date)
                    if start_dt:
                        conditions.append(TurnoverTrack.trigger_date >= start_dt)
                if end_date:
                    end_dt = parse_date(end_date)
                    if end_dt:
                        conditions.append(TurnoverTrack.trigger_date <= end_dt)

                if conditions:
                    query = query.where(and_(*conditions))

                result = await session.execute(query)
                tracks = result.scalars().all()

                if not tracks:
                    return {
                        "success": True,
                        "total_tracked": 0,
                        "day1_continued_limit_up_ratio": None,
                        "day1_avg_change": None,
                        "day3_avg_change": None,
                        "day7_avg_change": None,
                        "results": []
                    }

                # 計算統計
                total = len(tracks)

                # Day 1 統計
                day1_changes = [t.day1_change for t in tracks if t.day1_change is not None]
                day1_limit_ups = [t for t in tracks if t.day1_limit_up == True]

                # Day 3 統計
                day3_changes = [t.day3_change for t in tracks if t.day3_change is not None]

                # Day 7 統計
                day7_changes = [t.day7_change for t in tracks if t.day7_change is not None]

                # 計算平均
                day1_avg = round(sum(day1_changes) / len(day1_changes), 2) if day1_changes else None
                day3_avg = round(sum(day3_changes) / len(day3_changes), 2) if day3_changes else None
                day7_avg = round(sum(day7_changes) / len(day7_changes), 2) if day7_changes else None

                # 隔日續漲停比例
                day1_limit_up_ratio = None
                if day1_changes:
                    day1_limit_up_ratio = round(len(day1_limit_ups) / len(day1_changes) * 100, 2)

                # 組裝結果列表
                results = [
                    {
                        "symbol": t.symbol,
                        "trigger_date": str(t.trigger_date),
                        "trigger_price": t.trigger_price,
                        "turnover_rank": t.turnover_rank,
                        "day1_change": t.day1_change,
                        "day1_limit_up": t.day1_limit_up,
                        "day3_change": t.day3_change,
                        "day5_change": t.day5_change,
                        "day7_change": t.day7_change,
                    }
                    for t in tracks
                ]

                return {
                    "success": True,
                    "total_tracked": total,
                    "day1_continued_limit_up_ratio": day1_limit_up_ratio,
                    "day1_avg_change": day1_avg,
                    "day3_avg_change": day3_avg,
                    "day7_avg_change": day7_avg,
                    "results": results
                }

        except Exception as e:
            logger.error(f"取得追蹤統計失敗: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_stock_history(
        self,
        symbol: str,
        from_date: date,
        days: int = 10
    ) -> List[Dict]:
        """取得股票歷史價格"""
        try:
            end_date = from_date + timedelta(days=days + 5)  # 多取幾天以應對假日

            df = await data_fetcher.get_historical_data(
                symbol,
                from_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d")
            )

            if df.empty:
                return []

            history = []
            for _, row in df.iterrows():
                history.append({
                    "date": row.get("date"),
                    "close": row.get("close"),
                    "change_pct": row.get("change_percent", 0)
                })

            return history

        except Exception as e:
            logger.debug(f"取得 {symbol} 歷史資料失敗: {e}")
            return []

    def _get_day_data(
        self,
        history: List[Dict],
        trigger_date: date,
        days_after: int
    ) -> Optional[Dict]:
        """取得觸發日後第 N 個交易日的資料"""
        trading_days_count = 0

        for item in history:
            item_date = item.get("date")
            if item_date is None:
                continue

            if isinstance(item_date, str):
                item_dt = parse_date(item_date)
            else:
                item_dt = item_date

            if item_dt and item_dt > trigger_date:
                trading_days_count += 1
                if trading_days_count == days_after:
                    return item

        return None


# 全域實例
turnover_tracker = TurnoverTrackerService()
