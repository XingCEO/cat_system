"""
Formula Parser — 自訂公式安全解析器
白名單 Token 驗證 + pandas.eval() 沙箱執行
"""
import re
import logging
import pandas as pd

logger = logging.getLogger(__name__)

# 允許的欄位名稱 (白名單)
ALLOWED_FIELDS = {
    # 價格
    "open", "high", "low", "close", "volume",
    # 移動平均
    "ma5", "ma10", "ma20", "ma60",
    # 技術指標
    "rsi14",
    # 基本面
    "pe_ratio", "eps",
    # 籌碼
    "foreign_buy", "trust_buy", "margin_balance",
    # 漲跌
    "change_percent",
}

# 允許的運算符號（移除 '.' 以禁止屬性/方法存取，避免安全風險）
ALLOWED_OPERATORS = {"+", "-", "*", "/", "(", ")", " "}

# 公式長度與複雜度上限（防 DOS）
MAX_FORMULA_LENGTH = 500
MAX_TOKEN_COUNT = 50

# Token 正則（移除 . 作為獨立運算子）
TOKEN_PATTERN = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*|[0-9]+\.?[0-9]*|[+\-*/()\s]")


def tokenize(formula: str) -> list[str]:
    """將公式字串分割為 token 列表"""
    tokens = TOKEN_PATTERN.findall(formula)
    return [t.strip() for t in tokens if t.strip()]


def is_number(s: str) -> bool:
    """檢查字串是否為數字"""
    try:
        float(s)
        return True
    except ValueError:
        return False


def validate_formula(formula: str) -> tuple[bool, str]:
    """
    驗證公式是否安全

    Returns:
        (is_valid, error_message)
    """
    if not formula or not formula.strip():
        return False, "公式不可為空"

    if len(formula) > MAX_FORMULA_LENGTH:
        return False, f"公式長度超過上限 ({MAX_FORMULA_LENGTH} 字元)"

    tokens = tokenize(formula)
    if not tokens:
        return False, "公式解析失敗"

    if len(tokens) > MAX_TOKEN_COUNT:
        return False, f"公式複雜度超過上限 ({MAX_TOKEN_COUNT} tokens)"

    for token in tokens:
        if token in ALLOWED_OPERATORS:
            continue
        if is_number(token):
            continue
        if token in ALLOWED_FIELDS:
            continue
        return False, f"不允許的 token: {token}"

    # 檢查括號配對
    depth = 0
    for token in tokens:
        if token == "(":
            depth += 1
        elif token == ")":
            depth -= 1
        if depth < 0:
            return False, "括號不配對"
    if depth != 0:
        return False, "括號不配對"

    return True, ""


def safe_eval_formula(df: pd.DataFrame, name: str, formula: str) -> pd.DataFrame:
    """
    安全地計算自訂公式並將結果加入 DataFrame

    Args:
        df: 資料 DataFrame
        name: 新欄位名稱
        formula: 公式字串

    Returns:
        更新後的 DataFrame

    Raises:
        ValueError: 公式驗證失敗
    """
    is_valid, error_msg = validate_formula(formula)
    if not is_valid:
        raise ValueError(f"公式驗證失敗: {error_msg}")

    try:
        df[name] = df.eval(formula, engine="numexpr")
        logger.info(f"自訂公式 '{name}' = '{formula}' 計算完成")
    except Exception as e:
        raise ValueError(f"公式執行失敗: {str(e)}")

    return df
