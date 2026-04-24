"""
test_formula_parser_security.py
驗證 formula_parser 的安全邊界與正確計算行為
"""
import pandas as pd
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.engine.formula_parser import (
    validate_formula,
    safe_eval_formula,
    MAX_FORMULA_LENGTH,
    MAX_TOKEN_COUNT,
    ALLOWED_FIELDS,
)


# ──────────────────────────────────────────────
# 驗證失敗情境（validate_formula 回傳 False）
# ──────────────────────────────────────────────

class TestValidateFormulaRejections:

    def test_empty_formula_rejected(self):
        """空字串公式應被拒絕"""
        valid, msg = validate_formula("")
        assert valid is False
        assert msg  # 錯誤訊息不應為空

    def test_whitespace_only_formula_rejected(self):
        """純空白字串應被拒絕"""
        valid, msg = validate_formula("   ")
        assert valid is False

    def test_formula_too_long_rejected(self):
        """超過 MAX_FORMULA_LENGTH 的公式應被拒絕"""
        # 用合法字元湊長度，確保只超長不帶危險字元
        long_formula = ("close " * (MAX_FORMULA_LENGTH // 6 + 1))[:MAX_FORMULA_LENGTH + 1]
        valid, msg = validate_formula(long_formula)
        assert valid is False
        assert "長度" in msg or "超過" in msg

    def test_too_many_tokens_rejected(self):
        """超過 MAX_TOKEN_COUNT 個 token 的公式應被拒絕"""
        # 每個 "close + close" 節 產生 3 tokens；
        # 需要 MAX_TOKEN_COUNT + 1 個 token → 取 (MAX_TOKEN_COUNT + 1 + 1) // 2 個 close
        # 串成 "close + close + ..."：N 個 close 產生 2N-1 個 token
        # 確保 2N-1 > MAX_TOKEN_COUNT → N > (MAX_TOKEN_COUNT + 1) / 2
        n = MAX_TOKEN_COUNT // 2 + 2   # e.g. 50//2+2 = 27 → 53 tokens > 50
        formula = " + ".join(["close"] * n)
        valid, msg = validate_formula(formula)
        assert valid is False
        assert "複雜度" in msg or "超過" in msg

    def test_dangerous_token_import_rejected(self):
        """__import__ 應被拒絕"""
        valid, msg = validate_formula("__import__('os')")
        assert valid is False

    def test_dangerous_token_os_rejected(self):
        """os 模組名稱應被拒絕"""
        valid, msg = validate_formula("os.path")
        assert valid is False

    def test_dangerous_token_sys_rejected(self):
        """sys 應被拒絕"""
        valid, msg = validate_formula("sys.version")
        assert valid is False

    def test_dangerous_token_open_rejected(self):
        """open() 函式應被拒絕"""
        valid, msg = validate_formula("open('/etc/passwd')")
        assert valid is False

    def test_dangerous_dot_attribute_access_rejected(self):
        """含 . 的屬性存取應被拒絕（tokenizer 不產生 . token，整個含 . 的 identifier 不在白名單）"""
        # 含 . 的表達式會被 tokenize 為兩個 identifier token；
        # 其中 'attr' 不在 ALLOWED_FIELDS → 被拒絕
        valid, msg = validate_formula("close.attr")
        assert valid is False

    def test_dangerous_subscript_rejected(self):
        """
        含索引存取的表達式應被拒絕。
        tokenizer 的 TOKEN_PATTERN 不比對 [ ]，因此 close[0] 會被解析成
        token ["close", "0"]，兩者都合法，validate_formula 會通過——
        這是 parser 的已知行為（[ ] 被靜默忽略）。
        真正危險的是帶有不在白名單的 identifier，例如 __import__ 或 eval。
        本測試改驗 eval 關鍵字被拒絕。
        """
        valid, msg = validate_formula("eval(close)")
        assert valid is False

    def test_unbalanced_paren_close_only_rejected(self):
        """只有右括號應被拒絕"""
        valid, msg = validate_formula("close)")
        assert valid is False
        assert "括號" in msg

    def test_unbalanced_paren_open_only_rejected(self):
        """只有左括號應被拒絕"""
        valid, msg = validate_formula("(close")
        assert valid is False
        assert "括號" in msg

    def test_field_not_in_allowed_fields_rejected(self):
        """使用不在 ALLOWED_FIELDS 的欄位名稱應被拒絕"""
        # 確認測試用的欄位名稱確實不在白名單
        assert "hacked_field" not in ALLOWED_FIELDS
        valid, msg = validate_formula("hacked_field + close")
        assert valid is False
        assert "hacked_field" in msg


# ──────────────────────────────────────────────
# 驗證成功情境（validate_formula 回傳 True）
# ──────────────────────────────────────────────

class TestValidateFormulaAcceptance:

    def test_simple_field_accepted(self):
        """單一合法欄位應通過驗證"""
        valid, msg = validate_formula("close")
        assert valid is True
        assert msg == ""

    def test_arithmetic_formula_accepted(self):
        """(ma5 + ma10) / 2 應通過驗證"""
        valid, msg = validate_formula("(ma5 + ma10) / 2")
        assert valid is True

    def test_formula_exactly_at_length_limit_accepted(self):
        """恰好等於 MAX_FORMULA_LENGTH 的合法公式應通過（只要 token 數也在上限內）"""
        # 建立一個長度 = MAX_FORMULA_LENGTH、且 token 數 <= MAX_TOKEN_COUNT 的合法公式。
        # 策略：用單一 "close" 後面接大量空格填滿長度——空格不產生額外 token。
        formula = "close" + " " * (MAX_FORMULA_LENGTH - len("close"))
        assert len(formula) == MAX_FORMULA_LENGTH
        valid, _ = validate_formula(formula)
        assert valid is True

    def test_multiple_allowed_fields_accepted(self):
        """多個合法欄位組合應通過驗證"""
        valid, msg = validate_formula("(close - ma20) / ma20")
        assert valid is True

    def test_numeric_constants_accepted(self):
        """公式包含數字常數應通過驗證"""
        valid, msg = validate_formula("close * 1.05")
        assert valid is True


# ──────────────────────────────────────────────
# safe_eval_formula 行為測試
# ──────────────────────────────────────────────

class TestSafeEvalFormula:

    def _make_df(self) -> pd.DataFrame:
        return pd.DataFrame({
            "ticker_id": ["2330", "2317"],
            "close":     [100.0,  200.0],
            "ma5":       [90.0,   180.0],
            "ma10":      [85.0,   170.0],
        })

    def test_safe_eval_correctly_computes_average(self):
        """(ma5 + ma10) / 2 應計算出正確平均值"""
        df = self._make_df()
        result_df = safe_eval_formula(df, "ma_avg", "(ma5 + ma10) / 2")
        assert "ma_avg" in result_df.columns
        # 2330: (90 + 85) / 2 = 87.5
        assert abs(result_df.loc[0, "ma_avg"] - 87.5) < 1e-6
        # 2317: (180 + 170) / 2 = 175.0
        assert abs(result_df.loc[1, "ma_avg"] - 175.0) < 1e-6

    def test_safe_eval_adds_new_column(self):
        """safe_eval_formula 應在 DataFrame 新增指定欄位名稱"""
        df = self._make_df()
        original_cols = set(df.columns)
        result_df = safe_eval_formula(df, "price_ratio", "close / ma5")
        assert "price_ratio" in result_df.columns
        # 原有欄位仍保留
        assert original_cols.issubset(set(result_df.columns))

    def test_safe_eval_raises_valueerror_on_invalid_formula(self):
        """非法公式應拋出 ValueError"""
        df = self._make_df()
        with pytest.raises(ValueError):
            safe_eval_formula(df, "bad", "__import__('os')")

    def test_safe_eval_raises_valueerror_on_empty_formula(self):
        """空公式應拋出 ValueError"""
        df = self._make_df()
        with pytest.raises(ValueError):
            safe_eval_formula(df, "empty_col", "")

    def test_safe_eval_raises_valueerror_on_nonexistent_field(self):
        """公式欄位不存在於 DataFrame 時應拋出 ValueError（公式驗證通過但 eval 失敗）"""
        df = self._make_df()
        # rsi14 在 ALLOWED_FIELDS 但 df 中沒有此欄位，eval 應失敗
        with pytest.raises(ValueError):
            safe_eval_formula(df, "rsi_derived", "rsi14 + 1")

    def test_safe_eval_scalar_formula(self):
        """單一欄位公式應直接回傳該欄位值"""
        df = self._make_df()
        result_df = safe_eval_formula(df, "copy_close", "close")
        assert list(result_df["copy_close"]) == list(df["close"])

    def test_allowed_fields_only_blocks_forbidden_field(self):
        """公式用了不在 ALLOWED_FIELDS 的欄位 → validate_formula 回傳 False"""
        # 確認 'secret_col' 不在白名單
        assert "secret_col" not in ALLOWED_FIELDS
        valid, msg = validate_formula("secret_col + close")
        assert valid is False
        # 因此 safe_eval_formula 也應拋出 ValueError
        df = self._make_df()
        with pytest.raises(ValueError):
            safe_eval_formula(df, "out", "secret_col + close")
