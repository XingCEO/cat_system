"""
Combo Filter Mixin - 複合篩選器
"""
import asyncio
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ComboFilterMixin:
    """複合篩選器混入類"""

    async def get_combo_filter(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        turnover_min: Optional[float] = None,
        turnover_max: Optional[float] = None,
        change_min: Optional[float] = None,
        change_max: Optional[float] = None,
        min_buy_days: Optional[int] = None,
        volume_ratio: Optional[float] = None,
        is_5day_high: Optional[bool] = None,
        is_5day_low: Optional[bool] = None,
        is_ma20_uptrend: Optional[bool] = None
    ) -> Dict[str, Any]:
        """複合篩選（週轉率前200名 + 多條件組合）"""
        if start_date is None:
            from utils.date_utils import get_latest_trading_day
            start_date = get_latest_trading_day()

        if end_date is None:
            end_date = start_date

        dates = await self._get_date_range(start_date, end_date)
        all_items = []

        for date in dates:
            top200_result = await self.get_top20_turnover(date)
            if not top200_result.get("success"):
                continue

            stocks = top200_result.get("items", [])

            institutional_data = {}
            if min_buy_days is not None:
                institutional_data = await self._fetch_institutional_data(date)

            filtered_stocks = []

            for stock in stocks:
                symbol = stock["symbol"]
                turnover_rate = stock.get("turnover_rate", 0) or 0
                change_pct = stock.get("change_percent", 0) or 0
                today_volume = stock.get("volume", 0) or 0

                # 條件1: 周轉率區間
                if turnover_min is not None and turnover_rate < turnover_min:
                    continue
                if turnover_max is not None and turnover_rate > turnover_max:
                    continue

                # 條件2: 漲幅區間
                if change_min is not None and change_pct < change_min:
                    continue
                if change_max is not None and change_pct > change_max:
                    continue

                # 條件3: 法人連買天數
                if min_buy_days is not None:
                    inst_info = institutional_data.get(symbol, {})
                    consecutive_days = inst_info.get("consecutive_buy_days", 0)
                    if consecutive_days < min_buy_days:
                        continue
                    stock["consecutive_buy_days"] = consecutive_days
                    stock["foreign_buy"] = inst_info.get("foreign_buy", 0)
                    stock["trust_buy"] = inst_info.get("trust_buy", 0)

                # 條件4: 成交量倍數
                if volume_ratio is not None and today_volume > 0:
                    try:
                        history_df = await self._fetch_yahoo_history_for_ma(symbol)
                        if history_df.empty or len(history_df) < 2:
                            continue

                        if "volume" in history_df.columns:
                            volumes = history_df["volume"].tolist()[:5]
                            if len(volumes) >= 2 and volumes[1] is not None:
                                yesterday_volume = volumes[1] / 1000
                                if yesterday_volume > 0:
                                    actual_ratio = today_volume / yesterday_volume
                                    if actual_ratio < volume_ratio:
                                        continue
                                    stock["volume_ratio_calc"] = round(actual_ratio, 2)
                                else:
                                    continue
                            else:
                                continue
                        else:
                            continue
                    except Exception as e:
                        logger.debug(f"Error getting volume for {symbol}: {e}")
                        continue

                # 條件5: 五日創新高
                if is_5day_high is True:
                    try:
                        history_df = await self._fetch_yahoo_history_for_ma(symbol)
                        if history_df.empty or len(history_df) < 6:
                            continue
                        closes = history_df["close"].tolist()[:6]
                        today_close = closes[0] if closes[0] is not None else 0
                        past_5day_high = max([c for c in closes[1:6] if c is not None], default=0)
                        if today_close <= past_5day_high:
                            continue
                        stock["is_5day_high"] = True
                    except Exception as e:
                        logger.debug(f"Error checking 5day high for {symbol}: {e}")
                        continue

                # 條件6: 五日創新低
                if is_5day_low is True:
                    try:
                        history_df = await self._fetch_yahoo_history_for_ma(symbol)
                        if history_df.empty or len(history_df) < 6:
                            continue
                        closes = history_df["close"].tolist()[:6]
                        today_close = closes[0] if closes[0] is not None else float('inf')
                        past_5day_low = min([c for c in closes[1:6] if c is not None], default=float('inf'))
                        if today_close >= past_5day_low:
                            continue
                        stock["is_5day_low"] = True
                    except Exception as e:
                        logger.debug(f"Error checking 5day low for {symbol}: {e}")
                        continue

                # 條件7: 股價>=MA20 且 MA20向上
                if is_ma20_uptrend is True:
                    try:
                        history_df = await self._fetch_yahoo_history_for_ma(symbol)
                        if history_df.empty or len(history_df) < 21:
                            continue
                        closes = history_df["close"].tolist()[:25]
                        if len(closes) < 21:
                            continue
                        today_ma20 = self._safe_ma(closes, 20)
                        yesterday_ma20 = self._safe_ma(closes[1:], 20)
                        if today_ma20 is None or yesterday_ma20 is None:
                            continue
                        current_close = stock.get("close_price", 0) or 0
                        if current_close < today_ma20 or today_ma20 <= yesterday_ma20:
                            continue
                        stock["ma20"] = round(today_ma20, 2)
                        stock["is_ma20_uptrend"] = True
                    except Exception as e:
                        logger.debug(f"Error checking MA20 uptrend for {symbol}: {e}")
                        continue

                stock["query_date"] = date
                filtered_stocks.append(stock)

            all_items.extend(filtered_stocks)

        all_items.sort(key=lambda x: x.get("change_percent", 0), reverse=True)

        filter_desc = []
        if turnover_min is not None or turnover_max is not None:
            if turnover_min and turnover_max:
                filter_desc.append(f"周轉率 {turnover_min}%~{turnover_max}%")
            elif turnover_min:
                filter_desc.append(f"周轉率 ≥ {turnover_min}%")
            else:
                filter_desc.append(f"周轉率 ≤ {turnover_max}%")
        if change_min is not None or change_max is not None:
            if change_min and change_max:
                filter_desc.append(f"漲幅 {change_min}%~{change_max}%")
            elif change_min:
                filter_desc.append(f"漲幅 ≥ {change_min}%")
            else:
                filter_desc.append(f"漲幅 ≤ {change_max}%")
        if min_buy_days is not None:
            filter_desc.append(f"法人連買 ≥ {min_buy_days}日")
        if volume_ratio is not None:
            filter_desc.append(f"成交量 ≥ 昨日{volume_ratio}倍")
        if is_5day_high is True:
            filter_desc.append("五日創新高")
        if is_5day_low is True:
            filter_desc.append("五日創新低")
        if is_ma20_uptrend is True:
            filter_desc.append("股價≥MA20且MA20↑")

        return {
            "success": True,
            "start_date": start_date,
            "end_date": end_date,
            "filter": {
                "turnover_min": turnover_min,
                "turnover_max": turnover_max,
                "change_min": change_min,
                "change_max": change_max,
                "min_buy_days": min_buy_days,
                "volume_ratio": volume_ratio,
                "is_5day_high": is_5day_high,
                "is_5day_low": is_5day_low,
            },
            "filter_description": " + ".join(filter_desc) if filter_desc else "無篩選條件",
            "total_days": len(dates),
            "filtered_count": len(all_items),
            "items": all_items,
        }
