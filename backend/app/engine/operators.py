"""
Operators — 運算子定義 (含 CROSS_UP / CROSS_DOWN)
向量化 Pandas 運算，用於篩選引擎
"""
import pandas as pd
from typing import Union


def compare_gt(series_a: pd.Series, target: Union[pd.Series, float]) -> pd.Series:
    """大於"""
    return series_a > target


def compare_lt(series_a: pd.Series, target: Union[pd.Series, float]) -> pd.Series:
    """小於"""
    return series_a < target


def compare_eq(series_a: pd.Series, target: Union[pd.Series, float]) -> pd.Series:
    """等於"""
    return series_a == target


def compare_gte(series_a: pd.Series, target: Union[pd.Series, float]) -> pd.Series:
    """大於等於"""
    return series_a >= target


def compare_lte(series_a: pd.Series, target: Union[pd.Series, float]) -> pd.Series:
    """小於等於"""
    return series_a <= target


def cross_up(
    df: pd.DataFrame,
    field: str,
    target: Union[str, float],
) -> pd.Series:
    """
    黃金交叉：前日 field < target 且今日 field >= target

    如果 target 是字串，視為另一個欄位名稱。
    不會修改原始 DataFrame。
    """
    prev_field = df.groupby("ticker_id")[field].shift(1)

    if isinstance(target, str):
        prev_target = df.groupby("ticker_id")[target].shift(1)
        mask = (prev_field < prev_target) & (df[field] >= df[target])
    else:
        mask = (prev_field < target) & (df[field] >= target)

    return mask.fillna(False)


def cross_down(
    df: pd.DataFrame,
    field: str,
    target: Union[str, float],
) -> pd.Series:
    """
    死亡交叉：前日 field > target 且今日 field <= target

    如果 target 是字串，視為另一個欄位名稱。
    不會修改原始 DataFrame。
    """
    prev_field = df.groupby("ticker_id")[field].shift(1)

    if isinstance(target, str):
        prev_target = df.groupby("ticker_id")[target].shift(1)
        mask = (prev_field > prev_target) & (df[field] <= df[target])
    else:
        mask = (prev_field > target) & (df[field] <= target)

    return mask.fillna(False)


# 運算子映射表
OPERATOR_MAP = {
    ">": compare_gt,
    "<": compare_lt,
    "=": compare_eq,
    ">=": compare_gte,
    "<=": compare_lte,
}

# 需要特殊處理的交叉運算子
CROSS_OPERATORS = {"CROSS_UP": cross_up, "CROSS_DOWN": cross_down}
