#!/usr/bin/env python3
"""Validate generated JSON files without making network requests."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


QUICK_HISTORY_TRADE_DAYS = 20
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
REQUIRED_META_FIELDS = {
    "source",
    "latest_trade_date",
    "history_trade_days_actual",
    "fields",
    "units",
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


def validate_meta(meta: dict[str, Any], filename: str) -> None:
    missing = REQUIRED_META_FIELDS - set(meta)
    if missing:
        raise ValueError(f"{filename} meta 缺少字段：{', '.join(sorted(missing))}")
    if not str(meta.get("source", "")).strip():
        raise ValueError(f"{filename} meta.source 不能为空")
    if not isinstance(meta.get("fields"), list) or not meta["fields"]:
        raise ValueError(f"{filename} meta.fields 必须是非空列表")
    if not isinstance(meta.get("units"), dict) or not meta["units"]:
        raise ValueError(f"{filename} meta.units 必须是非空对象")


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


def record_keys(records: list[dict[str, Any]]) -> set[tuple[str, str]]:
    return {
        (str(record["ts_code"]), str(record["trade_date"]))
        for record in records
    }


def history_dates(payload: dict[str, Any], filename: str) -> list[str]:
    dates = sorted({str(record["trade_date"]) for record in payload["data"]})
    actual_days = int(payload["meta"].get("history_trade_days_actual", 0))
    requested_days = int(payload["meta"].get("history_trade_days_requested", 0))
    if len(dates) != actual_days:
        raise ValueError(
            f"{filename} 的 history_trade_days_actual 与实际交易日数量不一致"
        )
    if not 1 <= actual_days <= requested_days:
        raise ValueError(f"{filename} 的历史交易日数量超出预期")
    return dates


def parse_pool_definitions(history: dict[str, Any]) -> list[dict[str, Any]]:
    raw_pools = history["meta"].get("stock_pools")
    if not isinstance(raw_pools, list) or not raw_pools:
        raise ValueError("history_60d.json meta.stock_pools 必须是非空列表")

    pools: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for index, pool in enumerate(raw_pools):
        if not isinstance(pool, dict):
            raise ValueError(f"stock_pools[{index}] 不是对象")
        key = str(pool.get("key", "")).strip()
        name = str(pool.get("name", "")).strip()
        stock_count = int(pool.get("stock_count", 0))
        if not key or not name or stock_count < 1:
            raise ValueError(
                f"stock_pools[{index}] 必须包含有效的 key、name、stock_count"
            )
        if key in seen_keys:
            raise ValueError(f"meta.stock_pools 重复出现 {key}")
        seen_keys.add(key)
        pools.append(pool)
    return pools


def run() -> None:
    args = parse_args()
    latest = load_json(args.data_dir / "latest.json")
    history = load_json(args.data_dir / "history_60d.json")
    quick = load_json(args.data_dir / "history_20d.json")

    core_payloads = {
        "latest.json": latest,
        "history_60d.json": history,
        "history_20d.json": quick,
    }
    for filename, payload in core_payloads.items():
        validate_meta(payload["meta"], filename)
        validate_records(payload["data"], filename)

    latest_date = str(latest["meta"].get("latest_trade_date", ""))
    history_latest_date = str(history["meta"].get("latest_trade_date", ""))
    quick_latest_date = str(quick["meta"].get("latest_trade_date", ""))
    if not latest_date or len({latest_date, history_latest_date, quick_latest_date}) != 1:
        raise ValueError("latest、history_20d、history_60d 的 latest_trade_date 不一致")
    if any(str(record["trade_date"]) != latest_date for record in latest["data"]):
        raise ValueError("latest.json 含有非最新交易日记录")

    full_dates = history_dates(history, "history_60d.json")
    quick_dates = history_dates(quick, "history_20d.json")
    if full_dates[-1] != latest_date:
        raise ValueError("history_60d.json 最后交易日与 latest.json 不一致")
    expected_quick_dates = full_dates[-QUICK_HISTORY_TRADE_DAYS:]
    if quick_dates != expected_quick_dates:
        raise ValueError("history_20d.json 不是 history_60d.json 的最近 20 个交易日")

    latest_keys = record_keys(latest["data"])
    history_keys = record_keys(history["data"])
    quick_keys = record_keys(quick["data"])
    if not latest_keys.issubset(history_keys):
        raise ValueError("latest.json 不是 history_60d.json 的最新日子集")
    if not quick_keys.issubset(history_keys):
        raise ValueError("history_20d.json 不是 history_60d.json 的子集")

    pool_definitions = parse_pool_definitions(history)
    pool_payloads: dict[str, dict[str, Any]] = {}
    for definition in pool_definitions:
        pool_key = str(definition["key"])
        pool_name = str(definition["name"])
        filename = f"history_{pool_key}.json"
        payload = load_json(args.data_dir / filename)
        pool_payloads[pool_key] = payload
        validate_meta(payload["meta"], filename)
        validate_records(payload["data"], filename)

        meta = payload["meta"]
        if str(meta.get("scope", "")) != "stock_pool":
            raise ValueError(f"{filename} meta.scope 必须是 stock_pool")
        if str(meta.get("pool_key", "")) != pool_key:
            raise ValueError(f"{filename} meta.pool_key 不匹配")
        if str(meta.get("pool_name", "")) != pool_name:
            raise ValueError(f"{filename} meta.pool_name 不匹配")
        if int(meta.get("stock_count", 0)) != int(definition["stock_count"]):
            raise ValueError(f"{filename} meta.stock_count 不匹配")
        if str(meta.get("latest_trade_date", "")) != latest_date:
            raise ValueError(f"{filename} latest_trade_date 与总表不一致")

        history_dates(payload, filename)
        actual_pool_keys = record_keys(payload["data"])
        expected_pool_keys = {
            (str(record["ts_code"]), str(record["trade_date"]))
            for record in history["data"]
            if pool_key in record.get("pool_keys", [])
        }
        if actual_pool_keys != expected_pool_keys:
            raise ValueError(f"{filename} 没有完整覆盖总表中属于 {pool_key} 的记录")
        if any(pool_key not in record.get("pool_keys", []) for record in payload["data"]):
            raise ValueError(f"{filename} 含有不属于 {pool_key} 的记录")

    all_payloads = [latest, history, quick, *pool_payloads.values()]
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if token:
        serialized = json.dumps(all_payloads, ensure_ascii=False)
        if token in serialized:
            raise ValueError("输出文件意外包含 TUSHARE_TOKEN")

    print(
        "校验通过："
        f"最新交易日 {latest_date}，"
        f"最新 {len(latest['data'])} 条，"
        f"快速表 {len(quick_dates)} 个交易日 / {len(quick['data'])} 条，"
        f"总表 {len(full_dates)} 个交易日 / {len(history['data'])} 条，"
        f"股票池文件 {len(pool_payloads)} 个。"
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
