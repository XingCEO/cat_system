"""
Turnover Router - API endpoints for high turnover rate limit-up analysis
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List

from services.high_turnover_analyzer import high_turnover_analyzer
from services.turnover_tracker import turnover_tracker
from schemas.turnover import (
    HighTurnoverLimitUpResponse, Top20Response, TurnoverStats,
    TurnoverHistoryResponse, SymbolTurnoverHistoryResponse,
    HighTurnoverFilterParams, TrackRequest, TrackStatsResponse
)

router = APIRouter(prefix="/api/turnover", tags=["高周轉漲停分析"])


@router.get("/limit-up", response_model=HighTurnoverLimitUpResponse)
async def get_high_turnover_limit_up(
    date: Optional[str] = Query(None, description="查詢日期 YYYY-MM-DD"),
    min_turnover_rate: Optional[float] = Query(None, description="最低周轉率", ge=0),
    limit_up_types: Optional[str] = Query(None, description="漲停類型(逗號分隔): 一字板,秒板,盤中,尾盤"),
    max_open_count: Optional[int] = Query(None, description="開板次數上限", ge=0),
    industries: Optional[str] = Query(None, description="產業類別(逗號分隔)"),
    price_min: Optional[float] = Query(None, description="最低股價"),
    price_max: Optional[float] = Query(None, description="最高股價"),
    volume_min: Optional[int] = Query(None, description="最低成交量(張)"),
    preset: Optional[str] = Query(None, description="快速預設: strong_retail/demon/big_player/low_price"),
):
    """
    取得周轉率前20中的漲停股
    
    核心邏輯：
    1. 計算當日所有股票周轉率
    2. 依周轉率排序取前20名
    3. 在前20名中篩選漲停股（漲幅>=9.9%）
    
    回傳資料包含統計資訊及股票明細
    """
    filters = {}
    
    if min_turnover_rate is not None:
        filters["min_turnover_rate"] = min_turnover_rate
    if limit_up_types:
        filters["limit_up_types"] = [t.strip() for t in limit_up_types.split(",")]
    if max_open_count is not None:
        filters["max_open_count"] = max_open_count
    if industries:
        filters["industries"] = [i.strip() for i in industries.split(",")]
    if price_min is not None:
        filters["price_min"] = price_min
    if price_max is not None:
        filters["price_max"] = price_max
    if volume_min is not None:
        filters["volume_min"] = volume_min
    if preset:
        filters["preset"] = preset
    
    result = await high_turnover_analyzer.get_high_turnover_limit_up(
        date=date,
        filters=filters if filters else None
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "查詢失敗"))
    
    return result


@router.get("/limit-up/stats", response_model=TurnoverStats)
async def get_limit_up_stats(
    date: Optional[str] = Query(None, description="查詢日期 YYYY-MM-DD"),
):
    """
    取得高周轉漲停統計資訊
    
    包含：
    - 周轉率前20總數
    - 其中漲停股數量
    - 漲停占比
    - 平均周轉率
    - 總成交金額
    """
    result = await high_turnover_analyzer.get_high_turnover_limit_up(date=date)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "查詢失敗"))
    
    return result["stats"]


@router.get("/top20", response_model=Top20Response)
async def get_top20_turnover(
    date: Optional[str] = Query(None, description="查詢日期 YYYY-MM-DD"),
):
    """
    取得周轉率前20完整名單
    
    顯示所有前20名股票，並標註哪些有漲停
    """
    result = await high_turnover_analyzer.get_top20_turnover(date=date)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "查詢失敗"))
    
    return result


@router.get("/history", response_model=TurnoverHistoryResponse)
async def get_turnover_history(
    days: int = Query(10, ge=1, le=60, description="查詢天數"),
    min_occurrence: int = Query(2, ge=1, description="最少出現次數"),
):
    """
    批次歷史分析
    
    找出連續多日都在周轉率前20且漲停的股票
    
    範例：查詢最近10個交易日，找出至少出現2次的股票
    """
    result = await high_turnover_analyzer.get_history(
        days=days,
        min_occurrence=min_occurrence
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "查詢失敗"))
    
    return result


@router.get("/{symbol}/history", response_model=SymbolTurnoverHistoryResponse)
async def get_symbol_turnover_history(
    symbol: str,
    days: int = Query(20, ge=1, le=60, description="查詢天數"),
):
    """
    查詢單一股票在過去N天的周轉率排名變化
    
    顯示該股票每日是否進入前20名及其排名
    """
    result = await high_turnover_analyzer.get_symbol_history(
        symbol=symbol.upper(),
        days=days
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "查詢失敗"))
    
    return result


@router.post("/track")
async def create_track(request: TrackRequest):
    """
    建立追蹤任務

    追蹤高周轉漲停股的後續表現：
    - 隔日漲跌幅
    - 隔日是否繼續漲停
    - 3/5/7日後表現
    """
    result = await turnover_tracker.create_track(
        trigger_date=request.date,
        symbols=request.symbols
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "建立追蹤失敗"))

    return result


@router.get("/track/stats", response_model=TrackStatsResponse)
async def get_track_stats(
    start_date: Optional[str] = Query(None, description="開始日期"),
    end_date: Optional[str] = Query(None, description="結束日期"),
):
    """
    取得追蹤統計

    顯示高周轉漲停股的後續表現統計：
    - 隔日繼續漲停比例
    - 隔日平均漲跌幅
    - 7日後平均報酬
    """
    result = await turnover_tracker.get_track_stats(
        start_date=start_date,
        end_date=end_date
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "查詢失敗"))

    return result


@router.post("/track/update")
async def update_track_results():
    """
    更新追蹤結果（手動觸發）

    更新所有未完成追蹤任務的後續表現數據
    建議每日收盤後執行
    """
    result = await turnover_tracker.update_track_results()

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "更新失敗"))

    return result


# ===== 快速預設查詢 =====

@router.get("/presets/strong-retail")
async def get_strong_retail(date: Optional[str] = Query(None)):
    """
    超強游資股
    周轉率>20% + 漲停 + 開板<=1次
    """
    return await high_turnover_analyzer.get_high_turnover_limit_up(
        date=date,
        filters={"preset": "strong_retail"}
    )


@router.get("/presets/demon")
async def get_demon_stocks(date: Optional[str] = Query(None)):
    """
    妖股候選
    周轉率前20 + 連續漲停>=2天
    """
    return await high_turnover_analyzer.get_high_turnover_limit_up(
        date=date,
        filters={"preset": "demon"}
    )


@router.get("/presets/big-player")
async def get_big_player(date: Optional[str] = Query(None)):
    """
    大戶進場
    周轉率>15% + 封單>5000張
    """
    return await high_turnover_analyzer.get_high_turnover_limit_up(
        date=date,
        filters={"preset": "big_player"}
    )


@router.get("/presets/low-price")
async def get_low_price_stocks(date: Optional[str] = Query(None)):
    """
    低價飆股
    周轉率前20 + 漲停 + 股價<30元
    """
    return await high_turnover_analyzer.get_high_turnover_limit_up(
        date=date,
        filters={"preset": "low_price"}
    )


# ===== Top20 Limit-Up Dedicated Endpoints =====

@router.get("/top20-limit-up")
async def get_top20_limit_up(
    date: Optional[str] = Query(None, description="查詢日期 YYYY-MM-DD"),
):
    """
    取得當日周轉率前20名且漲停的股票（專用端點）
    
    回傳增強的統計資訊：
    - 符合條件股票清單
    - 完整前20名清單
    - 詳細統計數據
    """
    result = await high_turnover_analyzer.get_top20_limit_up_enhanced(date=date)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "查詢失敗"))
    
    return result


@router.get("/top20-limit-up/batch")
async def get_top20_limit_up_batch(
    start_date: str = Query(..., description="開始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="結束日期 YYYY-MM-DD"),
    min_occurrence: int = Query(2, ge=1, description="最少出現次數"),
):
    """
    批次查詢多日資料，找出連續出現的股票

    回傳：
    - 各日期符合條件的股票
    - 重複出現的股票統計
    """
    result = await high_turnover_analyzer.get_top20_limit_up_batch(
        start_date=start_date,
        end_date=end_date,
        min_occurrence=min_occurrence
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "查詢失敗"))

    return result


# ===== 新增篩選功能 =====

@router.get("/top200-limit-up")
async def get_top200_limit_up(
    start_date: Optional[str] = Query(None, description="開始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="結束日期 YYYY-MM-DD"),
):
    """
    週轉率前200名且漲停股（支援日期區間）
    """
    result = await high_turnover_analyzer.get_top200_limit_up_range(
        start_date=start_date,
        end_date=end_date
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "查詢失敗"))

    return result


@router.get("/top200-change-range")
async def get_top200_change_range(
    start_date: Optional[str] = Query(None, description="開始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="結束日期 YYYY-MM-DD"),
    change_min: Optional[float] = Query(None, description="漲幅下限(%)"),
    change_max: Optional[float] = Query(None, description="漲幅上限(%)"),
):
    """
    週轉率前200名且漲幅在指定區間（支援日期區間）

    範例：change_min=1&change_max=3 取得漲幅1%~3%的股票
    """
    result = await high_turnover_analyzer.get_top200_change_range_batch(
        start_date=start_date,
        end_date=end_date,
        change_min=change_min,
        change_max=change_max
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "查詢失敗"))

    return result


@router.get("/top200-5day-high")
async def get_top200_5day_high(
    start_date: Optional[str] = Query(None, description="開始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="結束日期 YYYY-MM-DD"),
):
    """
    週轉率前200名且收盤價五日內創新高（支援日期區間）
    """
    result = await high_turnover_analyzer.get_top200_5day_high_range(
        start_date=start_date,
        end_date=end_date
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "查詢失敗"))

    return result


@router.get("/top200-5day-low")
async def get_top200_5day_low(
    start_date: Optional[str] = Query(None, description="開始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="結束日期 YYYY-MM-DD"),
):
    """
    週轉率前200名且收盤價五日內創新低（支援日期區間）
    """
    result = await high_turnover_analyzer.get_top200_5day_low_range(
        start_date=start_date,
        end_date=end_date
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "查詢失敗"))

    return result


@router.get("/ma-breakout")
async def get_ma_breakout(
    start_date: Optional[str] = Query(None, description="開始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="結束日期 YYYY-MM-DD"),
    min_change: Optional[float] = Query(None, description="最低漲幅(%)"),
    max_change: Optional[float] = Query(None, description="最高漲幅(%)"),
):
    """
    突破糾結均線且漲幅在指定區間（支援日期區間）

    糾結均線定義：5日、10日、20日均線在3%範圍內糾結，今日收盤突破
    範例：min_change=1&max_change=5 取得漲幅1%~5%的突破股
    """
    result = await high_turnover_analyzer.get_ma_breakout_range(
        start_date=start_date,
        end_date=end_date,
        min_change=min_change,
        max_change=max_change
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "查詢失敗"))

    return result


@router.get("/volume-surge")
async def get_volume_surge(
    start_date: Optional[str] = Query(None, description="開始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="結束日期 YYYY-MM-DD"),
    volume_ratio: float = Query(1.5, description="成交量倍數(預設1.5倍)", ge=1.0),
):
    """
    成交量放大篩選（週轉率前200名且成交量 >= 昨日成交量 * 倍數）

    範例：volume_ratio=1.5 取得成交量>=昨日1.5倍的股票
    """
    result = await high_turnover_analyzer.get_volume_surge(
        date=start_date,
        volume_ratio=volume_ratio
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "查詢失敗"))

    return result


@router.get("/institutional-buy")
async def get_institutional_buy(
    start_date: Optional[str] = Query(None, description="開始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="結束日期 YYYY-MM-DD"),
    min_days: int = Query(3, description="最少連買天數(預設3天)", ge=1),
):
    """
    法人連買篩選（週轉率前200名且法人連續買超N日以上）

    範例：min_days=3 取得法人連續買超3天以上的股票
    """
    result = await high_turnover_analyzer.get_institutional_buy(
        date=start_date,
        min_consecutive_days=min_days
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "查詢失敗"))

    return result


@router.get("/above-ma20-uptrend")
async def get_above_ma20_uptrend(
    date: Optional[str] = Query(None, description="查詢日期 YYYY-MM-DD"),
):
    """
    股價 >= MA20 且 MA20 向上趨勢篩選

    條件：
    1. 當日收盤價 >= 20日均線
    2. MA20 向上趨勢（今日 MA20 > 昨日 MA20）

    從週轉率前200名中篩選
    """
    result = await high_turnover_analyzer.get_above_ma20_uptrend(date=date)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "查詢失敗"))

    return result


@router.get("/combo-filter")
async def get_combo_filter(
    start_date: Optional[str] = Query(None, description="開始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="結束日期 YYYY-MM-DD"),
    turnover_min: Optional[float] = Query(None, description="周轉率下限(%)"),
    turnover_max: Optional[float] = Query(None, description="周轉率上限(%)"),
    change_min: Optional[float] = Query(None, description="漲幅下限(%)"),
    change_max: Optional[float] = Query(None, description="漲幅上限(%)"),
    min_buy_days: Optional[int] = Query(None, description="法人連買最少天數"),
    volume_ratio: Optional[float] = Query(None, description="成交量倍數(相對昨日)"),
    is_5day_high: Optional[bool] = Query(None, description="五日創新高"),
    is_5day_low: Optional[bool] = Query(None, description="五日創新低"),
    is_ma20_uptrend: Optional[bool] = Query(None, description="股價>=MA20且MA20向上"),
):
    """
    複合篩選（週轉率前200名 + 多條件組合）

    範例：turnover_min=1&turnover_max=3&min_buy_days=3&volume_ratio=1.5&is_5day_high=true
    取得週轉率1~3%、法人連買3日、成交量>昨日1.5倍、五日創新高的股票
    """
    result = await high_turnover_analyzer.get_combo_filter(
        start_date=start_date,
        end_date=end_date,
        turnover_min=turnover_min,
        turnover_max=turnover_max,
        change_min=change_min,
        change_max=change_max,
        min_buy_days=min_buy_days,
        volume_ratio=volume_ratio,
        is_5day_high=is_5day_high,
        is_5day_low=is_5day_low,
        is_ma20_uptrend=is_ma20_uptrend
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "查詢失敗"))

    return result


# ===== 均線策略篩選 =====

@router.get("/ma-strategy/{strategy}")
async def get_ma_strategy(
    strategy: str,
    date: Optional[str] = Query(None, description="查詢日期 YYYY-MM-DD"),
):
    """
    均線策略篩選（週轉率前200名）

    策略類型：
    - extreme: 極強勢多頭 (多頭排列 + 均線向上 + Close > MA5)
    - steady: 穩健多頭 (多頭排列 + 均線向上 + Close > MA20)
    - support: 波段支撐 (多頭排列 + 均線向上 + Close > MA60)
    - tangled: 均線糾結突破 (均線間距 < 1% + Close > max(MA))
    """
    result = await high_turnover_analyzer.get_ma_strategy(strategy, date)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "查詢失敗"))

    return result


@router.get("/ma-strategy")
async def get_all_ma_strategies(
    date: Optional[str] = Query(None, description="查詢日期 YYYY-MM-DD"),
):
    """
    取得所有均線策略結果

    回傳 4 種策略的篩選結果：
    - extreme: 極強勢多頭
    - steady: 穩健多頭
    - support: 波段支撐
    - tangled: 均線糾結突破
    """
    result = await high_turnover_analyzer.get_all_ma_strategies(date)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "查詢失敗"))

    return result
