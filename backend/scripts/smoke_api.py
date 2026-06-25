"""Smoke-test a running FastAPI service over HTTP.

This script intentionally uses stdlib urllib instead of TestClient so startup,
static-file serving, middleware, routing, and JSON serialization are exercised
through the same path a browser or frontend uses.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


JsonCheck = Callable[[Any], None]
BodyCheck = Callable[[bytes, str], None]


@dataclass
class Result:
    name: str
    method: str
    path: str
    status: int | None = None
    ok: bool = False
    elapsed_ms: int = 0
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class SmokeFailure(AssertionError):
    pass


def _url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + path


def _request(
    base_url: str,
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout: float,
) -> tuple[int, bytes, str]:
    data = None
    headers = {"Accept": "application/json, text/html;q=0.9, */*;q=0.8"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = Request(_url(base_url, path), data=data, headers=headers, method=method)
    with urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read(), resp.headers.get("Content-Type", "")


def _json(body: bytes, content_type: str) -> Any:
    if "json" not in content_type.lower():
        raise SmokeFailure(f"expected JSON content-type, got {content_type!r}")
    return json.loads(body.decode("utf-8"))


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def _check_health(data: Any) -> None:
    _expect(isinstance(data, dict), "health response is not an object")
    _expect(data.get("status") == "healthy", "health status is not healthy")


def _check_status(data: Any) -> None:
    _expect(isinstance(data, dict), "status response is not an object")
    _expect(data.get("status") == "running", "api status is not running")
    _expect(bool(data.get("version")), "api version missing")


def _check_success_wrapper(data: Any) -> None:
    _expect(isinstance(data, dict), "response is not an object")
    _expect(data.get("success") is True, "success wrapper is not true")


def _check_object(data: Any) -> None:
    _expect(isinstance(data, dict), "response is not an object")


def _check_list(data: Any) -> None:
    _expect(isinstance(data, list), "response is not a list")


def _check_nonempty_tickers(data: Any) -> None:
    _check_list(data)
    _expect(len(data) > 0, "ticker list is empty")
    _expect("ticker_id" in data[0], "ticker item missing ticker_id")


def _check_screen(data: Any) -> None:
    _expect(isinstance(data, dict), "screen response is not an object")
    _expect(isinstance(data.get("matched_count"), int), "matched_count missing")
    _expect(isinstance(data.get("data"), list), "screen data missing")
    _expect("warnings" in data, "screen warnings field missing")


def _check_screen_no_warnings(data: Any) -> None:
    _check_screen(data)
    _expect(not data.get("warnings"), f"screen warnings present: {data.get('warnings')}")


def _check_kline(data: Any) -> None:
    _expect(isinstance(data, dict), "kline response is not an object")
    _expect(isinstance(data.get("candles"), list), "candles missing")
    _expect(len(data["candles"]) > 0, "candles empty")
    first = data["candles"][0]
    _expect("date" in first and "close" in first, "candle shape invalid")


def _check_export_json(data: Any) -> None:
    _expect(isinstance(data, list), "export JSON is not a list")


def _check_csv(body: bytes, content_type: str) -> None:
    _expect("csv" in content_type.lower(), f"expected CSV content-type, got {content_type!r}")
    _expect(len(body) > 0, "CSV body is empty")


def _check_excel(body: bytes, content_type: str) -> None:
    _expect("spreadsheet" in content_type.lower(), f"expected Excel content-type, got {content_type!r}")
    _expect(len(body) > 0, "Excel body is empty")


def _run_step(
    *,
    base_url: str,
    name: str,
    method: str,
    path: str,
    timeout: float,
    payload: dict[str, Any] | None = None,
    expected_status: int = 200,
    check_json: JsonCheck | None = None,
    check_html: Callable[[str], None] | None = None,
    check_body: BodyCheck | None = None,
) -> Result:
    started = time.perf_counter()
    result = Result(name=name, method=method, path=path)
    try:
        status, body, content_type = _request(
            base_url, method, path, payload=payload, timeout=timeout
        )
        result.status = status
        _expect(status == expected_status, f"expected {expected_status}, got {status}")
        if check_json is not None:
            data = _json(body, content_type)
            check_json(data)
            result.details["json_type"] = type(data).__name__
            if isinstance(data, dict):
                result.details["keys"] = sorted(data.keys())[:20]
            elif isinstance(data, list):
                result.details["items"] = len(data)
        if check_html is not None:
            text = body.decode("utf-8", errors="replace")
            check_html(text)
            result.details["bytes"] = len(body)
        if check_body is not None:
            check_body(body, content_type)
            result.details["bytes"] = len(body)
            result.details["content_type"] = content_type
        result.ok = True
    except HTTPError as exc:
        result.status = exc.code
        result.error = f"HTTPError: {exc.code} {exc.reason}"
    except (URLError, TimeoutError, OSError, SmokeFailure, json.JSONDecodeError) as exc:
        result.error = f"{type(exc).__name__}: {exc}"
    finally:
        result.elapsed_ms = int((time.perf_counter() - started) * 1000)
    return result


def _spa_check(html: str) -> None:
    lowered = html.lower()
    _expect("<html" in lowered or "<!doctype" in lowered, "root did not return HTML")
    _expect("root" in lowered, "SPA root marker missing")


def _query(path: str, params: dict[str, Any]) -> str:
    return path + "?" + urlencode(params)


def run(base_url: str, timeout: float) -> list[Result]:
    screen_payload = {
        "logic": "AND",
        "rules": [
            {
                "type": "indicator",
                "field": "close",
                "operator": ">",
                "target_type": "value",
                "target_value": 0,
            }
        ],
        "custom_formulas": [],
    }
    pullback_fields = [
        "ma_bull_pullback_low_high_1_3",
        "ma_bull_pullback_low_high_2_3",
        "ma_bull_pullback_breakout_1_3",
        "ma_bull_pullback_breakout_2_3",
    ]

    steps = [
        ("health", "GET", "/api/health", None, _check_health, None, None),
        ("status", "GET", "/api/status", None, _check_status, None, None),
        ("spa-root", "GET", "/", None, None, _spa_check, None),
        (
            "legacy-stock-filter",
            "GET",
            _query(
                "/api/stocks/filter",
                {
                    "page": 1,
                    "page_size": 5,
                    "change_min": -100,
                    "change_max": 100,
                    "volume_min": 0,
                    "exclude_etf": "true",
                },
            ),
            None,
            _check_success_wrapper,
            None,
            None,
        ),
        ("legacy-stock-detail", "GET", "/api/stocks/2330", None, _check_success_wrapper, None, None),
        ("legacy-stock-history", "GET", "/api/stocks/2330/history?days=10", None, _check_success_wrapper, None, None),
        ("legacy-stock-indicators", "GET", "/api/stocks/2330/indicators?days=60", None, _check_success_wrapper, None, None),
        ("legacy-stock-kline", "GET", "/api/stocks/2330/kline?period=day&years=1", None, _check_success_wrapper, None, None),
        ("legacy-industries", "GET", "/api/stocks/industries", None, _check_success_wrapper, None, None),
        ("analysis-industries", "GET", "/api/industries", None, _check_success_wrapper, None, None),
        ("analysis-trading-date", "GET", "/api/trading-date", None, _check_success_wrapper, None, None),
        ("legacy-cache-stats", "GET", "/api/cache/stats", None, _check_success_wrapper, None, None),
        ("legacy-history", "GET", "/api/history", None, _check_success_wrapper, None, None),
        ("legacy-favorites", "GET", "/api/favorites", None, _check_success_wrapper, None, None),
        ("legacy-watchlist", "GET", "/api/watchlist", None, _check_success_wrapper, None, None),
        ("legacy-backtest-history", "GET", "/api/backtest/history?limit=5", None, _check_success_wrapper, None, None),
        ("legacy-export-json", "GET", _query("/api/export/json", {"change_min": -100, "change_max": 100, "volume_min": 0}), None, _check_export_json, None, None),
        ("legacy-export-csv", "GET", _query("/api/export/csv", {"change_min": -100, "change_max": 100, "volume_min": 0}), None, None, None, _check_csv),
        ("legacy-export-excel", "GET", _query("/api/export/excel", {"change_min": -100, "change_max": 100, "volume_min": 0}), None, None, None, _check_excel),
        ("turnover-top20", "GET", "/api/turnover/top20", None, _check_success_wrapper, None, None),
        ("turnover-limit-up", "GET", "/api/turnover/limit-up", None, _check_success_wrapper, None, None),
        ("turnover-stats", "GET", "/api/turnover/limit-up/stats", None, _check_object, None, None),
        ("turnover-history", "GET", "/api/turnover/history?days=5&min_occurrence=1", None, _check_success_wrapper, None, None),
        ("turnover-symbol-history", "GET", "/api/turnover/2330/history?days=10", None, _check_success_wrapper, None, None),
        ("turnover-preset-strong-retail", "GET", "/api/turnover/presets/strong-retail", None, _check_success_wrapper, None, None),
        ("v1-tickers", "GET", "/api/v1/tickers?limit=5", None, _check_nonempty_tickers, None, None),
        ("v1-screen", "POST", "/api/v1/screen", screen_payload, _check_screen, None, None),
        *[
            (
                f"v1-screen-{field}",
                "POST",
                "/api/v1/screen",
                {
                    "logic": "AND",
                    "rules": [
                        {
                            "type": "indicator",
                            "field": field,
                            "operator": "=",
                            "target_type": "value",
                            "target_value": 1,
                        }
                    ],
                    "custom_formulas": [],
                },
                _check_screen_no_warnings,
                None,
                None,
            )
            for field in pullback_fields
        ],
        ("v1-chart-2330", "GET", "/api/v1/chart/2330/kline?period=daily&limit=30", None, _check_kline, None, None),
        ("v1-strategies", "GET", "/api/v1/strategies", None, _check_list, None, None),
    ]

    results: list[Result] = []
    for name, method, path, payload, check_json, check_html, check_body in steps:
        results.append(
            _run_step(
                base_url=base_url,
                name=name,
                method=method,
                path=path,
                timeout=timeout,
                payload=payload,
                check_json=check_json,
                check_html=check_html,
                check_body=check_body,
            )
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--json", dest="json_path", help="Write result JSON to path")
    args = parser.parse_args()

    results = run(args.base_url, args.timeout)
    payload = {
        "base_url": args.base_url,
        "passed": sum(1 for item in results if item.ok),
        "failed": sum(1 for item in results if not item.ok),
        "results": [item.__dict__ for item in results],
    }

    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    for item in results:
        marker = "PASS" if item.ok else "FAIL"
        print(f"[{marker}] {item.method} {item.path} {item.elapsed_ms}ms")
        if item.error:
            print(f"        {item.error}")

    return 0 if payload["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
