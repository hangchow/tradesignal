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
