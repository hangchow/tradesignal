# tradesignal 进阶说明

## 策略配置

默认策略配置文件是 `config/strategy_config.default.json`。
不传 `--strategy_config` 时，程序会直接读取这个文件。
如果这个文件不存在，程序启动会报错。

如果你想自定义策略参数，可以先复制一份：

```bash
cp config/strategy_config.default.json your_path/strategy_config.json
```

运行时传入：

```bash
./.venv/bin/python -m tradesignal --config your_path/tradesignal.us.json --strategy_config your_path/strategy_config.json
```

你自己的策略配置文件会以 `config/strategy_config.default.json` 为基础，同名参数会覆盖默认值。
如果只想改少数几个参数，只保留这些参数也可以。

例如只改 `top_n`：

```json
{
  "params": {
    "top_n": 3
  }
}
```

## 定时运行

最简单是用 `cron`。

例如美东开盘后每天跑一次：

```cron
35 21 * * 1-5 cd your_project_path && your_project_path/.venv/bin/python -m tradesignal --config your_path/tradesignal.us.json --strategy_config your_path/strategy_config.json >> /tmp/tradesignal.log 2>&1
```

上面这个时间是按机器本地时区写的，实际部署时请按你的机器时区自行调整。

如果你在 macOS 上长期运行，推荐用 `launchd`，这样开机后也能自动按计划触发。

例如项目目录是 `/Volumes/workspace/workspace/tradesignal`，配置文件是 `~/config/tradesignal_us.json`，可以直接使用仓库里的这两个文件：

- `scripts/run_tradesignal_us_open.sh`
- `deploy/com.tradesignal.us.open.plist`

这个脚本会用 `America/New_York` 判断是否真的是纽交所交易日开盘后，因此会自动跨夏令时，也会跳过美股休市日。
脚本启动后会先执行一次 `git pull --ff-only origin main`，然后再运行策略。

以 2026 年为例：

- 2026-03-09 到 2026-10-30，对应上海时间 `21:35`
- 2026-11-02 到 2027-03-12，对应上海时间 `22:35`

安装方式：

```bash
mkdir -p ~/Library/LaunchAgents
cp deploy/com.tradesignal.us.open.plist ~/Library/LaunchAgents/
launchctl unload ~/Library/LaunchAgents/com.tradesignal.us.open.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.tradesignal.us.open.plist
launchctl start com.tradesignal.us.open
```

查看日志：

```bash
tail -f /tmp/tradesignal-us-open.stdout.log
tail -f /tmp/tradesignal-us-open.stderr.log
```

如果是港股开盘后运行，可以使用：

- `scripts/run_tradesignal_hk_open.sh`
- `deploy/com.tradesignal.hk.open.plist`

这套配置会在机器本地时间 `09:35` 触发，再由脚本用 `XHKG` 交易日历判断是否是港股交易日，因此周末和香港休市日会自动跳过。
脚本启动后会先执行一次 `git pull --ff-only origin main`，然后再运行策略。

## 复盘某一天“加权动量”具体数字

如果你要追溯邮件里的具体数值（例如 `US.GLD` 在 `2026-04-08` 的 `20.4%`），可直接运行：

```bash
python scripts/explain_weighted_momentum.py \
  --config /path/to/tradesignal.json \
  --strategy-config /path/to/strategy_config.json \
  --date 2026-04-08 \
  --code US.GLD
```

脚本会输出：

- 当日收盘、90 日前收盘、180 日前收盘
- 当日成交量、过去 20 日均量
- 短周期动量、长周期动量、综合动量
- 量比、量能加权因子
- 最终加权动量（原始值、百分比、通知展示值）

这样你可以直接看到“20.4%”的每一个中间数字，不需要自己手工推导。
如果目标日期之前历史数据不足（例如不够 180 个交易日），脚本会直接提示并退出，避免给出误导结果。

## 数据格式

每个股票一个目录：

```text
kline_day/
  US.MSFT/
    US.MSFT_2026-03-30.csv
    US.MSFT_2026-04-06.csv
  US.NVDA/
    US.NVDA_2026-03-30.csv
```

CSV 至少要有这些列：

- `time_key`
- `close`
- `volume`

## 代码名称映射

推荐在 `stock_pool.stocks` 中直接配置 `code` + `cn_name`：

- `code`（如 `HK.00700`）
- `cn_name`（如 `腾讯控股`）

## 邮件内容

当前邮件会包含：

- 已完成交易日
- 股票池
- 推荐目标
- 备选候选
- 风险状态
- 总仓位倍率

当前不会包含：

- “你当前该卖出谁”
- “你当前该买多少股”

因为这个项目不读取你的真实持仓。

## dual_momentum 的“加权动量”怎么算

通知里提到的“加权动量 20.4%”，对应的是策略里 `weighted_momentum` 的结果。计算分三步：

1. **短周期动量（默认 90 日）**
   \[
   short\_momentum = \frac{P_t}{P_{t-90}} - 1
   \]

2. **长周期动量（默认 180 日）并合成综合动量**
   \[
   long\_momentum = \frac{P_t}{P_{t-180}} - 1
   \]
   \[
   blended\_momentum = short\_momentum \times (1-0.25) + long\_momentum \times 0.25
   \]

3. **成交量加权（只对正动量生效）**
   - 先算量比：`relative_volume = 当日成交量 / 过去20日均量`
   - 再算放大因子 `volume_boost`：
     - 若量比 `< 1.3`，放大因子 = `1.0`
     - 若量比 `>= 1.3`，放大因子 = `min(量比, 1.5) / 1.3`
   - 最终：
     \[
     weighted\_momentum =
     \begin{cases}
     blended\_momentum \times volume\_boost, & blended\_momentum > 0 \\
     \text{不参与候选（视为 NaN）}, & blended\_momentum \le 0
     \end{cases}
     \]

所以“20.4%”就是该标的在当日的 `weighted_momentum`（四舍五入到 1 位小数）；
如果当日量比没超过阈值 1.3x，那么它基本等于综合动量；如果超过阈值，则会被放大（最多按 1.5/1.3 倍放大）。
