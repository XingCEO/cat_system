"""
Stocks Router - API endpoints for stock filtering and data
"""
from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional, List
from datetime import date

from schemas.stock import StockFilterParams, StockListResponse, StockResponse, StockDetailResponse
from schemas.filter import BatchCompareRequest, BatchCompareResponse, BatchCompareItem
from schemas.common import APIResponse
from services.stock_filter import stock_filter
from services.data_fetcher import data_fetcher
from services.calculator import calculator
from utils.validators import validate_date, validate_symbol
from utils.date_utils import get_previous_trading_day, format_date

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.get("/filter", response_model=APIResponse[StockListResponse])
async def filter_stocks(
    date: Optional[str] = Query(None, description="查詢日期 YYYY-MM-DD"),
    change_min: Optional[float] = Query(None, description="漲幅下限(%)"),
    change_max: Optional[float] = Query(None, description="漲幅上限(%)"),
    volume_min: Optional[int] = Query(None, description="最小成交量(張)"),
    volume_max: Optional[int] = Query(None, description="最大成交量(張)"),
    price_min: Optional[float] = Query(None, description="最低股價"),
    price_max: Optional[float] = Query(None, description="最高股價"),
    consecutive_up_min: Optional[int] = Query(None, description="最少連續上漲天數"),
    consecutive_up_max: Optional[int] = Query(None, description="最多連續上漲天數"),
    amplitude_min: Optional[float] = Query(None, description="振幅下限(%)"),
    amplitude_max: Optional[float] = Query(None, description="振幅上限(%)"),
    volume_ratio_min: Optional[float] = Query(None, description="量比下限"),
    volume_ratio_max: Optional[float] = Query(None, description="量比上限"),
    industries: Optional[str] = Query(None, description="產業類別(逗號分隔)"),
    exclude_etf: bool = Query(True, description="排除ETF"),
    exclude_special: bool = Query(True, description="排除權證/特別股"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    sort_by: str = Query("change_percent", description="排序欄位"),
    sort_order: str = Query("desc", description="排序方向")
):
    """
    篩選符合條件的股票

    預設條件：
    - 漲幅 2%-10%
    - 成交量 >= 500 張
    - 股價 >= 10 元
    - 排除 ETF 和特別股
    """
    # Parse industries from comma-separated string
    industry_list = industries.split(",") if industries else None
    
    params = StockFilterParams(
        date=date,
        change_min=change_min,
        change_max=change_max,
        volume_min=volume_min,
        volume_max=volume_max,
        price_min=price_min,
        price_max=price_max,
        consecutive_up_min=consecutive_up_min,
        consecutive_up_max=consecutive_up_max,
        amplitude_min=amplitude_min,
        amplitude_max=amplitude_max,
        volume_ratio_min=volume_ratio_min,
        volume_ratio_max=volume_ratio_max,
        industries=industry_list,
        exclude_etf=exclude_etf,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    try:
        result = await stock_filter.filter_stocks(params)
        
        # Apply advanced filters if needed
        items = result.get("items", [])
        
        if consecutive_up_min is not None or consecutive_up_max is not None or \
           amplitude_min is not None or amplitude_max is not None or \
           volume_ratio_min is not None or volume_ratio_max is not None:
            items = await stock_filter.apply_advanced_filters(
                items,
                consecutive_up_min=consecutive_up_min,
                consecutive_up_max=consecutive_up_max,
                amplitude_min=amplitude_min,
                amplitude_max=amplitude_max,
                volume_ratio_min=volume_ratio_min,
                volume_ratio_max=volume_ratio_max
            )
            result["items"] = items
            result["total"] = len(items)
        
        response_data = StockListResponse(
            items=[StockResponse(**item) for item in result["items"]],
            total=result["total"],
            page=result["page"],
            page_size=result["page_size"],
            total_pages=result["total_pages"],
            query_date=result["query_date"],
            is_trading_day=result["is_trading_day"]
        )
        
        return APIResponse.ok(data=response_data)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{symbol}", response_model=APIResponse[StockDetailResponse])
async def get_stock_detail(symbol: str):
    """
    取得單一股票詳細資料
    """
    valid, error = validate_symbol(symbol)
    if not valid:
        raise HTTPException(status_code=400, detail=error)
    
    try:
        # Get stock info
        stock_info = await data_fetcher.get_stock_info(symbol)
        if not stock_info:
            raise HTTPException(status_code=404, detail=f"查無股票: {symbol}")
        
        # Get latest trading date
        trade_date = format_date(get_previous_trading_day())
        
        # Get daily data
        daily_df = await data_fetcher.get_daily_data(trade_date)
        stock_daily = daily_df[daily_df["stock_id"] == symbol]
        
        if stock_daily.empty:
            raise HTTPException(status_code=404, detail=f"查無 {symbol} 的交易資料")
        
        row = stock_daily.iloc[0]
        
        # Get historical data for calculations
        from datetime import datetime, timedelta
        end_date = trade_date
        start_date = (datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=400)).strftime("%Y-%m-%d")
        hist_df = await data_fetcher.get_historical_data(symbol, start_date, end_date)
        
        # Build response
        result = {
            "symbol": symbol,
            "name": stock_info.get("stock_name", symbol),
            "industry": stock_info.get("industry_category", ""),
            "open_price": row.get("open"),
            "high_price": row.get("max"),
            "low_price": row.get("min"),
            "close_price": row.get("close"),
            "volume": row.get("Trading_Volume", 0) // 1000,
            "trade_date": trade_date
        }
        
        # Calculate prev_close and metrics
        if "spread" in row:
            result["prev_close"] = row["close"] - row["spread"]
            result["change_percent"] = round(row["spread"] / result["prev_close"] * 100, 2)
        
        # Enrich with calculations
        if not hist_df.empty:
            hist_df = hist_df.sort_values("date", ascending=False)
            enriched = calculator.enrich_stock_data(result, hist_df)
            result.update(enriched)
        
        return APIResponse.ok(data=StockDetailResponse(**result))
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{symbol}/history")
async def get_stock_history(
    symbol: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    days: int = Query(60, ge=1, le=365)
):
    """
    取得股票歷史K線資料
    """
    valid, error = validate_symbol(symbol)
    if not valid:
        raise HTTPException(status_code=400, detail=error)
    
    try:
        from datetime import datetime, timedelta
        
        if not end_date:
            end_date = format_date(get_previous_trading_day())
        if not start_date:
            start_date = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=days * 2)).strftime("%Y-%m-%d")
        
        df = await data_fetcher.get_historical_data(symbol, start_date, end_date)
        
        if df.empty:
            return APIResponse.ok(data=[])
        
        # Format for chart
        df = df.sort_values("date")
        result = []
        for _, row in df.tail(days).iterrows():
            result.append({
                "date": str(row.get("date", "")),
                "open": row.get("open"),
                "high": row.get("max", row.get("high")),
                "low": row.get("min", row.get("low")),
                "close": row.get("close"),
                "volume": row.get("Trading_Volume", row.get("volume", 0))
            })
        
        return APIResponse.ok(data=result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-compare", response_model=APIResponse[BatchCompareResponse])
async def batch_compare_stocks(request: BatchCompareRequest):
    """
    批次日期比對 - 找出在多個交易日都符合條件的股票
    """
    if not request.dates or len(request.dates) < 2:
        raise HTTPException(status_code=400, detail="至少需要2個交易日進行比對")
    
    try:
        # Track occurrences
        occurrences = {}  # symbol -> list of dates
        stock_data = {}  # symbol -> latest data
        
        for trade_date in request.dates:
            params = StockFilterParams(
                date=trade_date,
                change_min=request.filter_params.change_min,
                change_max=request.filter_params.change_max,
                volume_min=request.filter_params.volume_min,
                volume_max=request.filter_params.volume_max,
                price_min=request.filter_params.price_min,
                price_max=request.filter_params.price_max,
                industries=request.filter_params.industries,
                exclude_etf=request.filter_params.exclude_etf,
                page=1,
                page_size=200
            )
            
            result = await stock_filter.filter_stocks(params)
            
            for item in result.get("items", []):
                symbol = item["symbol"]
                if symbol not in occurrences:
                    occurrences[symbol] = []
                occurrences[symbol].append(trade_date)
                stock_data[symbol] = item
        
        # Filter by minimum occurrence
        matches = []
        for symbol, dates in occurrences.items():
            if len(dates) >= request.min_occurrence:
                data = stock_data[symbol]
                matches.append(BatchCompareItem(
                    symbol=symbol,
                    name=data.get("name", symbol),
                    industry=data.get("industry"),
                    occurrence_count=len(dates),
                    occurrence_dates=sorted(dates),
                    avg_change=sum(d.get("change_percent", 0) for d in [stock_data[symbol]]) / len(dates),
                    total_volume=sum(d.get("volume", 0) for d in [stock_data[symbol]]) * len(dates),
                    latest_price=data.get("close_price"),
                    latest_change=data.get("change_percent")
                ))
        
        # Sort by occurrence count
        matches.sort(key=lambda x: x.occurrence_count, reverse=True)
        
        response = BatchCompareResponse(
            items=matches,
            total=len(matches),
            dates_queried=request.dates,
            filter_params=request.filter_params.model_dump()
        )
        
        return APIResponse.ok(data=response)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/realtime")
async def get_realtime_quotes(
    symbols: str = Query(..., description="股票代號(逗號分隔，最多50檔)")
):
    """盤中即時報價 — TWSE MIS API"""
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()][:50]
    if not symbol_list:
        raise HTTPException(status_code=400, detail="請提供至少一個股票代號")
    results = await data_fetcher.get_realtime_quotes(symbol_list)
    return {"success": True, "data": results, "count": len(results)}
