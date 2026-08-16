#!/usr/bin/env python3
"""Validate generated JSON files without making network requests."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


REQUIRED_MARKET_FIELDS = {
    "ts_code",
    "name",
    "pool_keys",
    "pool_names",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "pre_close",
    "change",
    "pct_chg",
    "vol",
    "amount",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="校验行情 JSON")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    return parser.parse_args()


def reject_nonfinite(value: str) -> None:
    raise ValueError(f"JSON 中不允许出现 {value}")


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"找不到文件：{path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle, parse_constant=reject_nonfinite)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} 顶层必须是对象")
    if not isinstance(payload.get("meta"), dict):
        raise ValueError(f"{path} 缺少 meta 对象")
    if not isinstance(payload.get("data"), list):
        raise ValueError(f"{path} 缺少 data 列表")
    return payload


def validate_records(records: list[Any], filename: str) -> None:
    if not records:
        raise ValueError(f"{filename} 的 data 为空")
    seen: set[tuple[str, str]] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"{filename} data[{index}] 不是对象")
        missing = REQUIRED_MARKET_FIELDS - set(record)
        if missing:
            raise ValueError(
                f"{filename} data[{index}] 缺少字段：{', '.join(sorted(missing))}"
            )
        key = (str(record["ts_code"]), str(record["trade_date"]))
        if key in seen:
            raise ValueError(f"{filename} 存在重复记录：{key[0]} / {key[1]}")
        seen.add(key)


def run() -> None:
    args = parse_args()
    latest = load_json(args.data_dir / "latest.json")
    history = load_json(args.data_dir / "history_60d.json")
    validate_records(latest["data"], "latest.json")
    validate_records(history["data"], "history_60d.json")

    latest_date = str(latest["meta"].get("latest_trade_date", ""))
    history_latest_date = str(history["meta"].get("latest_trade_date", ""))
    if not latest_date or latest_date != history_latest_date:
        raise ValueError("两份文件的 latest_trade_date 不一致")
    if any(str(record["trade_date"]) != latest_date for record in latest["data"]):
        raise ValueError("latest.json 含有非最新交易日记录")

    history_dates = sorted({str(record["trade_date"]) for record in history["data"]})
    actual_days = int(history["meta"].get("history_trade_days_actual", 0))
    requested_days = int(history["meta"].get("history_trade_days_requested", 0))
    if len(history_dates) != actual_days:
        raise ValueError("history_trade_days_actual 与实际交易日数量不一致")
    if not 1 <= actual_days <= requested_days:
        raise ValueError("历史交易日数量超出预期")
    if history_dates[-1] != latest_date:
        raise ValueError("历史数据最后交易日与 latest.json 不一致")

    latest_keys = {
        (str(record["ts_code"]), str(record["trade_date"]))
        for record in latest["data"]
    }
    history_keys = {
        (str(record["ts_code"]), str(record["trade_date"]))
        for record in history["data"]
    }
    if not latest_keys.issubset(history_keys):
        raise ValueError("latest.json 不是 history_60d.json 的最新日子集")

    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if token:
        serialized = json.dumps([latest, history], ensure_ascii=False)
        if token in serialized:
            raise ValueError("输出文件意外包含 TUSHARE_TOKEN")

    print(
        "校验通过："
        f"最新交易日 {latest_date}，"
        f"最新 {len(latest['data'])} 条，"
        f"历史 {actual_days} 个交易日 / {len(history['data'])} 条。"
    )


def main() -> int:
    try:
        run()
    except (OSError, ValueError, TypeError) as exc:
        print(f"校验失败：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
