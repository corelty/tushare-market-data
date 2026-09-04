# Tushare 私有行情 JSON：零基础最小模板

这个项目会把你配置的 A 股股票池按以下流程自动更新：

```text
Tushare 基础日线 → GitHub Actions → data/latest.json + data/history_20d.json + data/history_60d.json + data/history_<pool_key>.json
```

- 工作日北京时间 **18:05 左右**自动运行，也可以随时手动运行。
- 只调用 Tushare `daily` 基础日线，不调用 `daily_basic`、估值、资金流等高积分接口。
- Tushare Token 只通过 GitHub Actions Secret 注入，项目中没有硬编码 Token。
- JSON 会提交回你的**私有仓库**，并同时保存为 30 天有效的私有 Actions 产物。
- 默认**没有 GitHub Pages，也没有公开数据网址**。

> 本项目用于个人研究和复盘，不构成投资建议。Tushare 权限、积分和许可条款可能调整，请以其当前页面为准。

## 你最终会得到什么

首次运行成功后，私有仓库中会出现：

| 文件 | 内容 | 典型用途 |
|---|---|---|
| `data/latest.json` | 全部股票池最近一个可用交易日 | 最新行情与当日横截面 |
| `data/history_20d.json` | 全部股票最近 20 个实际交易日 | ChatGPT 日度快速复盘、周内强弱和成交变化 |
| `data/history_60d.json` | 全部股票最近 60 个实际交易日总表 | 全市场周度、月度和跨池比较；保留以兼容现有流程 |
| `data/history_ai_hardware.json` | AI 硬件池最近 60 个实际交易日 | AI 硬件周度/月度复盘 |
| `data/history_chemicals_energy_materials.json` | 化工能源材料池最近 60 个实际交易日 | 化工、能源、材料专题复盘 |
| `data/history_energy_storage.json` | 储能池最近 60 个实际交易日 | 储能专题复盘 |
| `data/history_consumer_electronics.json` | 消费电子池最近 60 个实际交易日 | 消费电子专题复盘 |
| `data/history_frontier_materials_watchlist.json` | 前沿材料观察池最近 60 个实际交易日 | 前沿材料观察 |

按池文件名由 `config/stock_pools.yml` 的池 key 自动生成，格式为 `data/history_<pool_key>.json`。同一股票如果属于多个池，会在对应的多个池文件中各保留一份记录；行情请求本身仍只执行一次。

默认股票池位于 `config/stock_pools.yml`。行情字段只有：`open`、`high`、`low`、`close`、`pre_close`、`change`、`pct_chg`、`vol`、`amount`。其中 `vol` 单位为手，`amount` 单位为千元；行情为未复权数据。

---

## 第 1 步：注册 GitHub

1. 打开 [GitHub 注册页](https://github.com/signup)。
2. 使用邮箱注册，设置用户名和强密码；也可以按页面提示使用 Google 或 Apple 登录。
3. 打开 GitHub 发来的验证邮件并完成邮箱验证。未验证邮箱时，部分基础功能（包括创建仓库）可能不可用。
4. 建议在账号设置中开启双重验证（2FA），并妥善保存恢复码。

个人免费账号即可创建私有仓库。GitHub 的当前官方流程见：[创建 GitHub 账号](https://docs.github.com/en/account-and-profile/how-tos/account-management/creating-an-account-on-github)。

## 第 2 步：注册 Tushare 并取得 Token

1. 打开 [Tushare Pro](https://tushare.pro/) 并选择注册。
2. 按当前页面提示完成账号和必要信息。注册方式、初始积分和权限以 Tushare 页面当时显示为准。
3. 登录后进入“个人中心”，找到 Token 页面；常用入口是 [Tushare Token 页面](https://tushare.pro/user/token)。
4. 复制 Token，临时保存在密码管理器中。**不要**把它粘贴到 README、代码、聊天、Issue、公开网页或 JSON 文件里。

本模板只使用 [Tushare A 股日线 `daily` 接口](https://tushare.pro/document/2?doc_id=27)。该接口当前说明包含开高低收、涨跌幅、成交量和成交额等字段，并在交易日收盘后更新。若新账号运行时提示权限不足，请查看接口页和个人中心显示的当前基础积分要求；模板本身没有调用付费的 `daily_basic`。

## 第 3 步：新建私有仓库并上传模板

### 3.1 下载并解压

下载本项目 ZIP，解压后应看到 `README.md`、`requirements.txt`、`scripts`、`config`、`data` 等内容。

`.github` 和 `.gitignore` 是隐藏名称。上传后务必按 `UPLOAD_CHECKLIST.txt` 核对，尤其要确认下面这个文件存在：

```text
.github/workflows/update-market-data.yml
```

### 3.2 创建私有仓库

1. 登录 GitHub，打开 [新建仓库](https://github.com/new)。
2. Repository name 填写，例如 `tushare-market-data`。
3. Visibility 必须选择 **Private**。
4. 不要勾选自动创建 README、`.gitignore` 或 License，避免与本模板同名文件冲突。
5. 点击 **Create repository**。

GitHub 官方说明：[创建新仓库](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository)。

### 3.3 用网页上传（最适合第一次使用）

1. 在新仓库的空白页面选择 **uploading an existing file**；如果仓库已有文件，选择 **Add file → Upload files**。
2. 把解压后文件夹中的**全部内容**拖到上传区域。不要只上传 ZIP，GitHub 不会替你解压。
3. 等待文件列表加载完成，确认包含 `.github/workflows/update-market-data.yml`。
4. 页面底部保留默认提交说明，点击 **Commit changes**。

如果网页没有上传隐藏的 `.github` 目录，可改用 GitHub Desktop，或在仓库网页中依次创建 `.github/workflows/update-market-data.yml` 并粘贴模板中的同名文件内容。

## 第 4 步：设置 Actions Secret

1. 打开你的私有仓库。
2. 依次进入 **Settings → Secrets and variables → Actions**。
3. 点击 **New repository secret**。
4. Name 必须填写：

   ```text
   TUSHARE_TOKEN
   ```

5. Secret 粘贴你从 Tushare 个人中心复制的 Token。
6. 点击 **Add secret**。

Secret 保存后只会显示名称，不会再次显示原值。工作流通过 `${{ secrets.TUSHARE_TOKEN }}` 把它作为环境变量交给脚本；GitHub 官方说明见：[在 Actions 中使用 Secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)。

### 允许工作流提交 JSON

工作流需要把更新后的全部 JSON 提交回私有仓库：

1. 进入 **Settings → Actions → General**。
2. 找到 **Workflow permissions**。
3. 选择 **Read and write permissions**，然后保存。

如果你的账号或组织策略不允许写权限，行情仍可在 Actions 产物中生成和下载，但最后的 `git push` 步骤会失败；此时需要仓库管理员调整权限，或删除工作流最后的“提交更新后的 JSON”步骤，仅保留私有产物。

## 第 5 步：第一次手动运行工作流

1. 打开仓库的 **Actions** 标签页。
2. 左侧选择 **更新 Tushare 行情 JSON**。
3. 点击右侧 **Run workflow**。
4. Branch 选择默认的 `main`，再次点击绿色 **Run workflow**。
5. 等待约 1～3 分钟。运行前是黄色，成功后会变成绿色对勾。

只有含 `workflow_dispatch` 的工作流才会显示 Run workflow 按钮，本模板已经配置。GitHub 官方步骤见：[手动运行工作流](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)。

之后会在工作日北京时间 18:05 自动运行。GitHub 计划任务偶尔会排队延迟，因此这里使用 18:05 而不是整点；当前工作流已明确使用 `Asia/Shanghai` 时区。

## 第 6 步：验证输出文件

### 方法 A：查看私有仓库文件

运行成功后回到仓库的 **Code** 页面，打开：

```text
data/latest.json
data/history_20d.json
data/history_60d.json
data/history_ai_hardware.json
data/history_chemicals_energy_materials.json
data/history_energy_storage.json
data/history_consumer_electronics.json
data/history_frontier_materials_watchlist.json
```

重点检查：

- `meta.latest_trade_date` 是最近一个交易日；周末或节假日不一定等于当天。
- 60 日文件的 `meta.history_trade_days_actual` 通常为 `60`，快速文件通常为 `20`。
- 每个按池文件都有 `meta.pool_key`、`meta.pool_name`、`meta.stock_count`，并保留 `source`、`fields` 和 `units`。
- `meta.free_basic_fields_only` 为 `true`。
- `data` 不是空列表，记录中包含股票代码、名称、全部板块标签和基础日线字段。
- 文件中绝不能出现你的 Tushare Token。

### 方法 B：下载私有 Actions 产物

1. 进入 **Actions**，打开刚才成功的运行记录。
2. 在页面下方 **Artifacts** 区域下载 `tushare-market-data-运行编号`。
3. 解压后应看到全部生成的 JSON。

Actions 产物不是公开网址；只有登录 GitHub 且对私有仓库有读取权限的人才能下载。GitHub 官方说明：[下载工作流产物](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts)。

## 第 7 步：怎样让 ChatGPT 读取

推荐按复盘范围选择最小数据集，减少上传体积和读取失败：

- **日度快速复盘**：读取 `data/latest.json + data/history_20d.json`。
- **某个板块的周度/月度复盘**：读取 `data/latest.json +` 对应的 `data/history_<pool_key>.json`。
- **跨板块周度/月度复盘**：按需读取多个池文件；只有需要全池统一计算时才读取 `data/history_60d.json`。

### 方式 A：上传文件

从 Actions 下载产物，把需要的 JSON 直接上传到 ChatGPT 对话。日度复盘可输入：

```text
请使用我上传的 latest.json 和 history_20d.json 做日度快速复盘。说明数据截至哪个交易日，并列出股票池强弱、涨跌幅、成交额变化和异常波动。不要把结果当成投资建议。
```

板块周度/月度复盘可输入：

```text
请使用我上传的 latest.json 和 history_ai_hardware.json，对 AI 硬件池做周度/月度复盘。请使用 meta 中的池名称、交易日数量和单位，并保留跨池股票的全部标签。
```

### 方式 B：连接已授权的 GitHub 应用

如果你的 ChatGPT 或 Codex 环境提供 GitHub 应用/连接器，可以授权它读取这个私有仓库，然后提供所需文件地址，例如：

```text
https://github.com/你的用户名/你的仓库名/blob/main/data/latest.json
https://github.com/你的用户名/你的仓库名/blob/main/data/history_20d.json
https://github.com/你的用户名/你的仓库名/blob/main/data/history_ai_hardware.json
```

只粘贴链接、但没有授权 GitHub 访问时，ChatGPT 通常不能读取私有内容。授权时尽量只开放这一个仓库。

### 方式 C：后续增加自有只读接口（适合全自动复盘）

以后可以把私有 JSON 放在你控制的服务后面，提供带认证的只读 HTTPS 接口，例如：

```text
GET https://data.example.com/market/latest
GET https://data.example.com/market/history?days=20
GET https://data.example.com/market/history?pool=ai_hardware&days=60
```

认证信息应放在请求头或连接器的安全配置中，不要把密钥拼在 URL 查询参数里。ChatGPT/Codex 可以通过经授权的 GitHub 集成，或你后续搭建的只读 MCP/应用来获取数据。

## 为什么默认不启用 GitHub Pages

GitHub Pages 的用途是公开发布网页或文件，不是私有数据交换。Tushare 数据及其上游数据可能涉及使用范围、账号授权和再分发约束，而且相关条款会更新。因此本模板采取保守默认：

- 仓库必须是 Private。
- Token 只放 GitHub Secret。
- 数据只保存到私有仓库和私有 Actions 产物。
- 项目中没有 Pages 配置。
- 公开发布、商业使用或向第三方持续分发前，应重新阅读 [Tushare 用户协议](https://tushare.pro/document/1?doc_id=409) 和 [Tushare 数据服务协议](https://tushare.pro/document/1?doc_id=405)，必要时向 Tushare 确认授权范围。

这不是法律意见，而是减少意外公开分发风险的工程默认值。

## 修改或扩展股票池

编辑 `config/stock_pools.yml`。在对应板块的 `stocks` 下复制一项：

```yaml
- ts_code: 600000.SH
  name: 浦发银行
  note: 示例说明
```

代码格式：上海 `600000.SH`、深圳 `000001.SZ`、北交所 `920xxx.BJ`（以 Tushare 当前代码为准）。

同一股票可以出现在多个股票池中。脚本只请求一次行情，并在输出的 `pool_keys`、`pool_names` 中保留全部分类，同时把该股票写入每个所属池的历史文件。修改后提交文件，再手动运行一次工作流验证。

新增股票池时，只要池 key 符合小写字母、数字和下划线规则，脚本就会自动生成 `data/history_<pool_key>.json`，不需要再修改 Python 代码或工作流。

默认每批最多 50 只股票，以控制单次数据量。若股票池扩展到很多只，脚本会自动分批。Tushare `daily` 的单次记录上限和调用频率可能变化，请以接口页面为准。

## JSON 结构示例

按池文件会在原有元数据上增加池范围信息：

```json
{
  "meta": {
    "source": "Tushare Pro / daily",
    "latest_trade_date": "20260818",
    "history_trade_days_actual": 60,
    "scope": "stock_pool",
    "pool_key": "ai_hardware",
    "pool_name": "AI硬件",
    "stock_count": 89,
    "fields": ["ts_code", "trade_date", "open", "high", "low", "close"],
    "units": {"pct_chg": "%", "vol": "手", "amount": "千元"}
  },
  "data": [
    {
      "ts_code": "300308.SZ",
      "name": "中际旭创",
      "pool_keys": ["ai_hardware"],
      "pool_names": ["AI硬件"],
      "trade_date": "20260818",
      "open": 0.0,
      "high": 0.0,
      "low": 0.0,
      "close": 0.0,
      "pre_close": 0.0,
      "change": 0.0,
      "pct_chg": 0.0,
      "vol": 0.0,
      "amount": 0.0
    }
  ]
}
```

上面的 `0.0` 只是结构占位，不是行情。

## 可选：在自己的电脑本地运行

需要 Python 3.11 或更新版本。在项目目录执行：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export TUSHARE_TOKEN="你的Token"
python scripts/update_market_data.py
python scripts/validate_output.py
```

Windows PowerShell 设置环境变量可使用：

```powershell
$env:TUSHARE_TOKEN="你的Token"
python scripts/update_market_data.py
python scripts/validate_output.py
```

不要把含 Token 的终端截图或 `.env` 文件上传到 GitHub。

## 常见问题

### Actions 页面没有这个工作流

检查 `.github/workflows/update-market-data.yml` 是否真的上传到了默认分支。`.github` 是隐藏目录，最容易在网页上传时漏掉。

### 报错“缺少环境变量 TUSHARE_TOKEN”

Secret 名称必须完全是 `TUSHARE_TOKEN`，并且要建在当前仓库的 **Repository secrets** 中。

### 报错“没有访问该接口权限”

登录 Tushare，查看 `daily` 接口当前要求和账号积分。这个模板没有请求 `daily_basic`；不要为了修复权限错误把 Token 写进代码。

### JSON 生成成功，但提交步骤失败

先检查 **Settings → Actions → General → Workflow permissions** 是否为 **Read and write permissions**。若组织策略禁止写入，可以从本次运行的 Artifacts 下载 JSON。

### 最新日期不是今天

周末、法定节假日、收盘数据尚未入库或整个股票池当日没有数据时，`latest_trade_date` 会停留在最近可用交易日，这是预期行为。

### 自动任务没有严格在 18:05 开始

GitHub 计划任务可能排队或延迟。只要运行最终成功且 `latest_trade_date` 正确，通常不影响晚间复盘；也可以手动点击 Run workflow。

### 私有 GitHub 链接发给 ChatGPT 后仍打不开

这是权限问题，不是链接格式问题。请上传 JSON 文件、连接并授权 GitHub 应用，或后续使用带认证的只读接口。不要把仓库改成公开来绕过认证。

## 项目文件说明

```text
.
├── .github/workflows/update-market-data.yml  # 定时、校验、上传与自动提交全部 JSON
├── config/stock_pools.yml                    # 可扩展股票池
├── data/README.md                            # 输出文件与推荐读取组合
├── scripts/update_market_data.py             # 拉取、整理、生成总表和拆分文件
├── scripts/validate_output.py                 # 离线校验全部输出及跨池完整性
├── .gitignore                                # 忽略本地秘密和临时文件
├── requirements.txt                          # Python 依赖
└── UPLOAD_CHECKLIST.txt                      # 网页上传核对表
```

## 安全检查清单

- [ ] 仓库显示为 **Private**。
- [ ] `TUSHARE_TOKEN` 只存在于 Repository Secret。
- [ ] 代码、README、日志和 JSON 中没有 Token。
- [ ] GitHub Pages 未启用。
- [ ] 只给确实需要的账号或应用授予私有仓库权限。
- [ ] 对外发布数据前重新核对 Tushare 当前许可条款。
