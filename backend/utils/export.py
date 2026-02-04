"""
Export Service - 匯出功能
"""
import csv
import io
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ExportService:
    """匯出服務"""
    
    def export_to_csv(
        self, 
        data: List[Dict[str, Any]], 
        columns: List[str] = None,
        headers: Dict[str, str] = None
    ) -> str:
        """
        將資料匯出為 CSV 格式
        
        Args:
            data: 資料列表
            columns: 要匯出的欄位列表（可選）
            headers: 欄位標題對應（可選）
        
        Returns:
            CSV 字串
        """
        if not data:
            return ""
        
        # Use all keys if columns not specified
        if columns is None:
            columns = list(data[0].keys())
        
        # Use column names as headers if not specified
        if headers is None:
            headers = {col: col for col in columns}
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        header_row = [headers.get(col, col) for col in columns]
        writer.writerow(header_row)
        
        # Write data
        for row in data:
            row_data = [row.get(col, "") for col in columns]
            writer.writerow(row_data)
        
        return output.getvalue()
    
    def export_stocks_csv(self, stocks: List[Dict[str, Any]]) -> str:
        """
        匯出股票資料為 CSV
        
        Args:
            stocks: 股票資料列表
        
        Returns:
            CSV 字串
        """
        columns = [
            "symbol", "name", "industry", "close_price", "change_percent",
            "volume", "turnover_rate", "trade_date"
        ]
        
        headers = {
            "symbol": "股票代號",
            "name": "股票名稱",
            "industry": "產業類別",
            "close_price": "收盤價",
            "change_percent": "漲跌幅(%)",
            "volume": "成交量(張)",
            "turnover_rate": "週轉率(%)",
            "trade_date": "交易日期"
        }
        
        return self.export_to_csv(stocks, columns, headers)


# 全域實例
export_service = ExportService()
