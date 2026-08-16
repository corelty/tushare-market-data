#!/usr/bin/env python3
"""Fetch basic A-share daily prices from Tushare and write review-ready JSON."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import pandas as pd
import tushare as ts
import yaml


BEIJING_TZ = ZoneInfo("Asia/Shanghai")
BASIC_DAILY_FIELDS = (
    "ts_code",
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
)
TS_CODE_PATTERN = re.compile(r"^\d{6}\.(SH|SZ|BJ)$")
POOL_KEY_PATTERN = re.compile(r"^[a-z0-9_]+$")
LOGGER = logging.getLogger("tushare-market-data")


class ConfigError(ValueError):
    """Raised when the stock pool configuration is invalid."""


@dataclass(frozen=True)
class Settings:
    history_trade_days: int
    lookback_calendar_days: int
    request_chunk_size: int
    retry_attempts: int
    retry_base_seconds: float


@dataclass(frozen=True)
class ProjectConfig:
    settings: Settings
    stocks: dict[str, dict[str, Any]]
    pool_definitions: list[dict[str, Any]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="生成 data/latest.json 与 data/history_60d.json"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/stock_pools.yml"),
        help="股票池配置文件路径",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data"),
        help="JSON 输出目录",
    )
    parser.add_argument(
        "--as-of",
        help="查询截止日，格式 YYYYMMDD；默认使用北京时间当天",
    )
    return parser.parse_args()


def require_int(value: Any, name: str, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{name} 必须是整数") from exc
    if not minimum <= parsed <= maximum:
        raise ConfigError(f"{name} 必须在 {minimum} 到 {maximum} 之间")
    return parsed


def require_float(value: Any, name: str, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{name} 必须是数字") from exc
    if not minimum <= parsed <= maximum:
        raise ConfigError(f"{name} 必须在 {minimum} 到 {maximum} 之间")
    return parsed


def load_config(path: Path) -> ProjectConfig:
    if not path.is_file():
        raise ConfigError(f"找不到配置文件：{path}")

    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    if not isinstance(raw, dict):
        raise ConfigError("配置文件顶层必须是一个对象")

    raw_settings = raw.get("settings", {})
    if not isinstance(raw_settings, dict):
        raise ConfigError("settings 必须是一个对象")

    settings = Settings(
        history_trade_days=require_int(
            raw_settings.get("history_trade_days", 60),
            "settings.history_trade_days",
            5,
            250,
        ),
        lookback_calendar_days=require_int(
            raw_settings.get("lookback_calendar_days", 120),
            "settings.lookback_calendar_days",
            30,
            730,
        ),
        request_chunk_size=require_int(
            raw_settings.get("request_chunk_size", 50),
            "settings.request_chunk_size",
            1,
            100,
        ),
        retry_attempts=require_int(
            raw_settings.get("retry_attempts", 3),
            "settings.retry_attempts",
            1,
            8,
        ),
        retry_base_seconds=require_float(
            raw_settings.get("retry_base_seconds", 2),
            "settings.retry_base_seconds",
            0,
            60,
        ),
    )

    if settings.lookback_calendar_days < settings.history_trade_days:
        raise ConfigError(
            "lookback_calendar_days 不应小于 history_trade_days；建议 60 个交易日回看 120 个自然日"
        )

    pools = raw.get("pools")
    if not isinstance(pools, dict) or not pools:
        raise ConfigError("pools 必须是非空对象")

    stocks: dict[str, dict[str, Any]] = {}
    pool_definitions: list[dict[str, Any]] = []

    for pool_key, pool in pools.items():
        if not isinstance(pool_key, str) or not POOL_KEY_PATTERN.fullmatch(pool_key):
            raise ConfigError(
                f"股票池键 {pool_key!r} 只能包含小写字母、数字和下划线"
            )
        if not isinstance(pool, dict):
            raise ConfigError(f"pools.{pool_key} 必须是一个对象")

        display_name = str(pool.get("display_name", "")).strip()
        description = str(pool.get("description", "")).strip()
        raw_stocks = pool.get("stocks")
        if not display_name:
            raise ConfigError(f"pools.{pool_key}.display_name 不能为空")
        if not isinstance(raw_stocks, list) or not raw_stocks:
            raise ConfigError(f"pools.{pool_key}.stocks 必须是非空列表")

        seen_in_pool: set[str] = set()
        for index, item in enumerate(raw_stocks):
            location = f"pools.{pool_key}.stocks[{index}]"
            if not isinstance(item, dict):
                raise ConfigError(f"{location} 必须是一个对象")

            ts_code = str(item.get("ts_code", "")).strip().upper()
            name = str(item.get("name", "")).strip()
            note = str(item.get("note", "")).strip()

            if not TS_CODE_PATTERN.fullmatch(ts_code):
                raise ConfigError(
                    f"{location}.ts_code 格式错误：{ts_code!r}；示例 300750.SZ"
                )
            if not name:
                raise ConfigError(f"{location}.name 不能为空")
            if ts_code in seen_in_pool:
                raise ConfigError(f"{pool_key} 中重复出现 {ts_code}")
            seen_in_pool.add(ts_code)

            if ts_code not in stocks:
                stocks[ts_code] = {
                    "ts_code": ts_code,
                    "name": name,
                    "pool_keys": [],
                    "pool_names": [],
                    "pool_notes": {},
                }
            elif stocks[ts_code]["name"] != name:
                raise ConfigError(
                    f"{ts_code} 在不同股票池中的名称不一致："
                    f"{stocks[ts_code]['name']!r} 与 {name!r}"
                )

            stocks[ts_code]["pool_keys"].append(pool_key)
            stocks[ts_code]["pool_names"].append(display_name)
            if note:
                stocks[ts_code]["pool_notes"][pool_key] = note

        pool_definitions.append(
            {
                "key": pool_key,
                "name": display_name,
                "description": description,
                "stock_count": len(raw_stocks),
            }
        )

    return ProjectConfig(
        settings=settings,
        stocks=stocks,
        pool_definitions=pool_definitions,
    )


def chunked(items: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def safe_error_message(error: Exception, token: str) -> str:
    message = str(error).strip() or error.__class__.__name__
    return message.replace(token, "***") if token else message


def fetch_chunk(
    pro: Any,
    codes: list[str],
    start_date: str,
    end_date: str,
    settings: Settings,
    token: str,
) -> pd.DataFrame:
    for attempt in range(1, settings.retry_attempts + 1):
        try:
            frame = pro.daily(
                ts_code=",".join(codes),
                start_date=start_date,
                end_date=end_date,
                fields=",".join(BASIC_DAILY_FIELDS),
            )
            if frame is None:
                return pd.DataFrame(columns=BASIC_DAILY_FIELDS)
            return frame
        except Exception as exc:  # Tushare exposes several transport/API exceptions.
            message = safe_error_message(exc, token)
            if attempt >= settings.retry_attempts:
                raise RuntimeError(
                    f"Tushare 请求连续失败 {settings.retry_attempts} 次：{message}"
                ) from exc
            delay = settings.retry_base_seconds * (2 ** (attempt - 1))
            LOGGER.warning(
                "第 %s 次请求失败（%s）；%.1f 秒后重试",
                attempt,
                message,
                delay,
            )
            time.sleep(delay)

    raise AssertionError("unreachable")


def fetch_market_data(
    config: ProjectConfig,
    token: str,
    as_of: date,
) -> tuple[pd.DataFrame, str, str]:
    end_date = as_of.strftime("%Y%m%d")
    start_date = (as_of - timedelta(days=config.settings.lookback_calendar_days)).strftime(
        "%Y%m%d"
    )
    codes = sorted(config.stocks)
    pro = ts.pro_api(token)
    frames: list[pd.DataFrame] = []

    total_chunks = (len(codes) + config.settings.request_chunk_size - 1) // config.settings.request_chunk_size
    for chunk_index, code_chunk in enumerate(
        chunked(codes, config.settings.request_chunk_size), start=1
    ):
        LOGGER.info(
            "读取第 %s/%s 组（%s 只股票，%s 至 %s）",
            chunk_index,
            total_chunks,
            len(code_chunk),
            start_date,
            end_date,
        )
        frame = fetch_chunk(
            pro,
            code_chunk,
            start_date,
            end_date,
            config.settings,
            token,
        )
        if not frame.empty:
            frames.append(frame)

    if not frames:
        raise RuntimeError(
            "Tushare 没有返回任何日线数据。请检查 Token 权限、股票代码和查询日期。"
        )

    combined = pd.concat(frames, ignore_index=True)
    missing_columns = set(BASIC_DAILY_FIELDS) - set(combined.columns)
    if missing_columns:
        raise RuntimeError(
            "Tushare 返回结果缺少字段：" + ", ".join(sorted(missing_columns))
        )

    combined = combined.loc[:, list(BASIC_DAILY_FIELDS)].copy()
    combined["ts_code"] = combined["ts_code"].astype(str).str.upper()
    combined["trade_date"] = combined["trade_date"].astype(str)
    combined = combined[combined["ts_code"].isin(config.stocks)]
    combined = combined.drop_duplicates(
        subset=["ts_code", "trade_date"], keep="last"
    )
    combined = combined.sort_values(
        by=["trade_date", "ts_code"], ascending=[True, True]
    ).reset_index(drop=True)
    return combined, start_date, end_date


def frame_to_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    # Pandas handles NaN -> null and NumPy scalar conversion reliably here.
    return json.loads(frame.to_json(orient="records", force_ascii=False))


def enrich_records(
    raw_records: list[dict[str, Any]], stocks: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for raw in raw_records:
        stock = stocks[raw["ts_code"]]
        record: dict[str, Any] = {
            "ts_code": raw["ts_code"],
            "name": stock["name"],
            "pool_keys": stock["pool_keys"],
            "pool_names": stock["pool_names"],
        }
        if stock["pool_notes"]:
            record["pool_notes"] = stock["pool_notes"]
        for field in BASIC_DAILY_FIELDS:
            if field != "ts_code":
                record[field] = raw.get(field)
        enriched.append(record)
    return enriched


def build_payloads(
    frame: pd.DataFrame,
    config: ProjectConfig,
    query_start: str,
    query_end: str,
    generated_at: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    trade_dates = sorted(frame["trade_date"].dropna().astype(str).unique().tolist())
    if not trade_dates:
        raise RuntimeError("返回数据中没有有效交易日")

    selected_dates = trade_dates[-config.settings.history_trade_days :]
    history = frame[frame["trade_date"].isin(selected_dates)].copy()
    latest_trade_date = selected_dates[-1]
    latest = history[history["trade_date"] == latest_trade_date].copy()

    history_codes = set(history["ts_code"].tolist())
    latest_codes = set(latest["ts_code"].tolist())
    configured_codes = set(config.stocks)

    metadata: dict[str, Any] = {
        "source": "Tushare Pro / daily",
        "source_url": "https://tushare.pro/document/2?doc_id=27",
        "generated_at_beijing": generated_at,
        "query_start_date": query_start,
        "query_end_date": query_end,
        "latest_trade_date": latest_trade_date,
        "history_start_date": selected_dates[0],
        "history_end_date": selected_dates[-1],
        "history_trade_days_requested": config.settings.history_trade_days,
        "history_trade_days_actual": len(selected_dates),
        "configured_stock_count": len(config.stocks),
        "stocks_with_history_data": len(history_codes),
        "stocks_with_latest_data": len(latest_codes),
        "missing_stock_codes_in_history": sorted(configured_codes - history_codes),
        "missing_stock_codes_on_latest_trade_date": sorted(
            configured_codes - latest_codes
        ),
        "endpoint": "daily",
        "fields": list(BASIC_DAILY_FIELDS),
        "units": {
            "pct_chg": "%",
            "vol": "手",
            "amount": "千元",
        },
        "price_adjustment": "未复权",
        "free_basic_fields_only": True,
        "stock_pools": config.pool_definitions,
        "notice": (
            "仅供个人研究和复盘，不构成投资建议。公开分发前请重新核对 Tushare 最新许可条款。"
        ),
    }

    latest_payload = {
        "meta": metadata,
        "data": enrich_records(frame_to_records(latest), config.stocks),
    }
    history_payload = {
        "meta": metadata,
        "data": enrich_records(frame_to_records(history), config.stocks),
    }
    return latest_payload, history_payload


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(
            payload,
            handle,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        handle.write("\n")
    os.replace(temp_path, path)


def parse_as_of(value: str | None) -> date:
    if not value:
        return datetime.now(BEIJING_TZ).date()
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError as exc:
        raise ValueError("--as-of 必须使用 YYYYMMDD 格式") from exc


def run() -> None:
    args = parse_args()
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "缺少环境变量 TUSHARE_TOKEN。请在 GitHub Actions Secret 中设置它，切勿写进代码。"
        )

    config = load_config(args.config)
    as_of = parse_as_of(args.as_of)
    generated_at = datetime.now(BEIJING_TZ).isoformat(timespec="seconds")
    frame, query_start, query_end = fetch_market_data(config, token, as_of)
    latest_payload, history_payload = build_payloads(
        frame,
        config,
        query_start,
        query_end,
        generated_at,
    )

    latest_path = args.output_dir / "latest.json"
    history_path = args.output_dir / "history_60d.json"
    atomic_write_json(latest_path, latest_payload)
    atomic_write_json(history_path, history_payload)

    LOGGER.info(
        "完成：最新交易日 %s，历史 %s 个交易日，%s 条记录",
        latest_payload["meta"]["latest_trade_date"],
        history_payload["meta"]["history_trade_days_actual"],
        len(history_payload["data"]),
    )
    LOGGER.info("输出：%s；%s", latest_path, history_path)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        run()
    except (ConfigError, RuntimeError, ValueError) as exc:
        LOGGER.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
