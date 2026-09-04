# 自动生成的数据目录

首次成功运行 GitHub Actions 后，这里会出现：

- `latest.json`：全部股票池最近一个可用交易日的数据。
- `history_20d.json`：全部股票最近 20 个实际交易日的数据，适合日度快速复盘。
- `history_60d.json`：全部股票最近 60 个实际交易日的总表，保留以兼容现有流程。
- `history_<pool_key>.json`：对应股票池最近 60 个实际交易日的数据。

当前配置会生成这些按池文件：

- `history_ai_hardware.json`
- `history_chemicals_energy_materials.json`
- `history_energy_storage.json`
- `history_consumer_electronics.json`
- `history_frontier_materials_watchlist.json`

同一股票属于多个池时，会出现在对应的多个按池文件中。每个按池文件的 `meta` 都包含 `pool_key`、`pool_name`、`stock_count`、`history_trade_days_actual`、`latest_trade_date`、`source`、`fields` 和 `units`。

推荐读取组合：

- ChatGPT 日度复盘：`latest.json + history_20d.json`
- 单板块周度/月度复盘：`latest.json + history_<pool_key>.json`
- 全池或跨池复盘：按需读取多个按池文件；需要统一总表时读取 `history_60d.json`

这些文件由工作流自动写入，请不要手工修改，也不要把 Tushare Token 放进任何 JSON。
