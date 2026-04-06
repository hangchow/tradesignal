# tradesignal

一个最小的 `dual_momentum` 股票池信号通知项目。

它只做这几件事：

- 从本地 `kline_day/<code>/*.csv` 读取日线
- 运行 `dual_momentum` 策略
- 输出当前推荐目标或 `CASH`
- 可选通过 SMTP 发邮件

它不做这些事：

- 不连接 `futu`
- 不读取真实账户
- 不分析当前持仓
- 不自动下单

## 安装

```bash
python3 -m venv .venv
./.venv/bin/pip install -e .
```

## 配置

复制一份样例配置：

```bash
cp config/tradesignal.sample.json config/tradesignal.json
```

至少改这几项：

- `stock_pool.codes`
- `stock_pool.data_root`
- `notification.email.*`

如果不想发邮件，只想先看终端输出：

- 把 `notification.email.enabled` 改成 `false`

## 手动运行

```bash
./.venv/bin/python -m tradesignal --config config/tradesignal.json
```

只打印，不发邮件：

```bash
./.venv/bin/python -m tradesignal --config config/tradesignal.json --no-email
```

## 定时运行

最简单是用 `cron`。

例如美东开盘后每天跑一次：

```cron
35 21 * * 1-5 cd /Users/sean/workspace/tradesignal && /Users/sean/workspace/tradesignal/.venv/bin/python -m tradesignal --config config/tradesignal.json >> /tmp/tradesignal.log 2>&1
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
