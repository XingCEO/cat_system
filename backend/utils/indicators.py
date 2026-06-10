"""
Shared technical indicator primitives.

全系統共用的指標計算，確保 Legacy 服務 (technical_analysis / chart fallback)
與 v1 引擎 (data_sync) 算出一致的值：

- RSI 採 Wilder 平滑 (RMA, alpha=1/n)，與 pandas-ta `ta.rsi` 及主流看盤軟體
  (XQ、Yahoo、TradingView RSI) 一致。舊版各處使用 SMA (Cutler's RSI)，
  且彼此週期/平滑不一致，導致同一檔股票在不同頁面 RSI 不同。
- KD 採台股慣例 (9,3,3)：RSV → %K = SMA(RSV,3) → %D = SMA(%K,3)，
  與 pandas-ta `ta.stoch(k=9, d=3, smooth_k=3)` 欄位語意相同。
"""
import pandas as pd

RSI_LENGTH = 14
KD_LENGTH = 9
KD_SMOOTH_K = 3
KD_SMOOTH_D = 3


def wilder_rsi(closes: pd.Series, length: int = RSI_LENGTH) -> pd.Series:
    """
    Wilder's RSI (RMA 平滑)。

    邊界值依 Wilder 定義：
    - avg_loss == 0 且 avg_gain > 0 → RSI = 100
    - avg_gain == 0 且 avg_loss == 0 (完全橫盤) → RSI = 50
    """
    closes = pd.to_numeric(closes, errors="coerce")
    delta = closes.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    rsi[(avg_loss == 0) & (avg_gain > 0)] = 100.0
    rsi[(avg_loss == 0) & (avg_gain == 0)] = 50.0
    return rsi


def stoch_kd(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    length: int = KD_LENGTH,
    smooth_k: int = KD_SMOOTH_K,
    smooth_d: int = KD_SMOOTH_D,
) -> tuple[pd.Series, pd.Series]:
    """
    Stochastic %K/%D (慢速 KD)。

    RSV = (close - lowN) / (highN - lowN) * 100
    %K  = SMA(RSV, smooth_k)
    %D  = SMA(%K, smooth_d)

    區間為 0 (highN == lowN，連續一字線) 時 RSV 不可除 → 以 50 中性值代替，
    避免 NaN 在後續平滑中擴散。
    """
    high = pd.to_numeric(high, errors="coerce")
    low = pd.to_numeric(low, errors="coerce")
    close = pd.to_numeric(close, errors="coerce")

    low_n = low.rolling(window=length).min()
    high_n = high.rolling(window=length).max()
    span = high_n - low_n
    rsv = 100 * (close - low_n) / span.where(span != 0)
    rsv = rsv.where(span != 0, 50.0)

    k = rsv.rolling(window=smooth_k).mean()
    d = k.rolling(window=smooth_d).mean()
    return k, d
