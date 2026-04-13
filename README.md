# tradesignal

基于本地日线数据的股票信号邮件通知工具。

## 安装

```bash
python3 -m venv .venv
./.venv/bin/pip install -e .
```

## 配置

复制一份样例配置：

```bash
cp config/tradesignal.us.sample.json your_path/tradesignal.us.json
```

至少改这几项：

- `stock_pool.stocks`
- `stock_pool.data_root`
- `notification.email.*`

邮件密码可以直接写在 `notification.email.password` 里。
如果不想发邮件，把 `notification.email.enabled` 改成 `false`。


## 策略配置（必传）

运行 `tradesignal` 时，`--config` 和 `--strategy_config` 都是必传参数。

```bash
cp config/strategy_config.default.json your_path/strategy_config.json
```

然后运行：

```bash
./.venv/bin/python -m tradesignal --config your_path/tradesignal.us.json --strategy_config your_path/strategy_config.json
```

## 手动运行

```bash
./.venv/bin/python -m tradesignal --config your_path/tradesignal.us.json --strategy_config your_path/strategy_config.json
```

只打印，不发邮件：

```bash
./.venv/bin/python -m tradesignal --config your_path/tradesignal.us.json --strategy_config your_path/strategy_config.json --no-email
```

启动时程序默认会先用 `akshare` 增量补齐 `stock_pool.data_root` 下的日线数据，失败后再自动回退到 `yfinance`，再继续算信号。
日线抓取时机按当前项目约定处理：美股开盘后，才补上一交易日的日线。
如果抓取失败，程序会直接报错退出。

如果不想启动时联网抓取，可以加：

```bash
./.venv/bin/python -m tradesignal --config your_path/tradesignal.us.json --strategy_config your_path/strategy_config.json --skip-fetch
```

## 进阶

策略配置、定时运行、数据格式和邮件内容见 [docs/advanced.md](docs/advanced.md)。
