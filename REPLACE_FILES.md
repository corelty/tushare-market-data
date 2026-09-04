# 替换说明

把本目录中的文件按相同相对路径覆盖到 `corelty/tushare-market-data` 仓库：

1. `scripts/update_market_data.py`
2. `scripts/validate_output.py`
3. `.github/workflows/update-market-data.yml`
4. `README.md`
5. `data/README.md`

`config/stock_pools.yml`、`requirements.txt` 和已有 `data/latest.json`、`data/history_60d.json` 不需要手工修改或删除。

替换并提交后，在 GitHub Actions 中手动运行一次“更新 Tushare 行情 JSON”。工作流会继续保留并更新原来的两个文件，同时新增：

- `data/history_20d.json`
- `data/history_ai_hardware.json`
- `data/history_chemicals_energy_materials.json`
- `data/history_energy_storage.json`
- `data/history_consumer_electronics.json`
- `data/history_frontier_materials_watchlist.json`

以后若在 `stock_pools.yml` 中新增池，脚本会自动生成 `data/history_<pool_key>.json`，工作流的 `data/*.json` 规则会自动上传和提交它。
