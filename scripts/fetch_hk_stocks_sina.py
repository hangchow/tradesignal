#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_URL = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHKStockData"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://finance.sina.com.cn/",
}


def fetch_page(page: int, page_size: int = 200, *, node: str = "qbgg_hk") -> list[dict[str, str]]:
    params = {
        "page": str(page),
        "num": str(page_size),
        "sort": "symbol",
        "asc": "1",
        "node": node,
        "symbol": "",
        "_s_r_a": "page",
    }
    url = f"{API_URL}?{urlencode(params)}"
    request = Request(url, headers=DEFAULT_HEADERS)
    with urlopen(request, timeout=20) as response:
        payload = response.read().decode("utf-8", errors="replace").strip()

    if payload in {"", "null"}:
        return []
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        data = _parse_nonstandard_json(payload)
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _parse_nonstandard_json(payload: str) -> list[dict[str, str]]:
    fixed = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', payload)
    data = json.loads(fixed)
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def normalize_code(symbol: str) -> str | None:
    digits = "".join(ch for ch in symbol if ch.isdigit())
    if not digits:
        return None
    return f"HK.{int(digits):05d}"


def fetch_all(page_size: int = 200, sleep_seconds: float = 0.1, *, node: str = "qbgg_hk") -> dict[str, str]:
    result: dict[str, str] = {}
    page = 1
    while True:
        rows = fetch_page(page=page, page_size=page_size, node=node)
        if not rows:
            break
        for row in rows:
            code = normalize_code(str(row.get("symbol", "")).strip())
            name = str(row.get("name", "")).strip()
            if not code or not name:
                continue
            result[code] = name
        if len(rows) < page_size:
            break
        page += 1
        time.sleep(sleep_seconds)
    return result


def write_csv(path: Path, code_names: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["code", "name"])
        for code, name in sorted(code_names.items()):
            writer.writerow([code, name])


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch HK stock code/name list from Sina Finance.")
    parser.add_argument(
        "--output",
        default="config/hk_stocks.csv",
        help="Output CSV path. Defaults to config/hk_stocks.csv",
    )
    parser.add_argument("--page-size", type=int, default=200, help="Rows per page requested from Sina API.")
    parser.add_argument("--node", default="qbgg_hk", help="Sina market node, defaults to qbgg_hk.")
    args = parser.parse_args()

    mapping = fetch_all(page_size=args.page_size, node=args.node)
    output = Path(args.output)
    write_csv(output, mapping)
    print(f"WROTE rows={len(mapping)} file={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
