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
./.venv/bin/python -m tradesignal --config your_path/tradesignal.json --strategy_config your_path/strategy_config.json
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
35 21 * * 1-5 cd your_project_path && your_project_path/.venv/bin/python -m tradesignal --config your_path/tradesignal.json --strategy_config your_path/strategy_config.json >> /tmp/tradesignal.log 2>&1
```

上面这个时间是按机器本地时区写的，实际部署时请按你的机器时区自行调整。

如果你在 macOS 上长期运行，推荐用 `launchd`，这样开机后也能自动按计划触发。

例如项目目录是 `/Volumes/workspace/workspace/tradesignal`，配置文件是 `~/config/tradesignal_us.json`，可以直接使用仓库里的这两个文件：

- `scripts/run_tradesignal_us_open.sh`
- `deploy/com.tradesignal.us.open.plist`

这个脚本会用 `America/New_York` 判断是否真的是纽交所交易日开盘后，因此会自动跨夏令时，也会跳过美股休市日。

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
