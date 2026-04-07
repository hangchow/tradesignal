#!/bin/zsh

set -euo pipefail

PROJECT_ROOT="/Volumes/workspace/workspace/tradesignal"
PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
CONFIG_PATH="${HOME}/config/tradesignal_hk.json"

cd "${PROJECT_ROOT}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "python not found: ${PYTHON_BIN}" >&2
  exit 1
fi

if [[ ! -f "${CONFIG_PATH}" ]]; then
  echo "config not found: ${CONFIG_PATH}" >&2
  exit 1
fi

if ! "${PYTHON_BIN}" - <<'PY'
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import exchange_calendars as xcals

calendar = xcals.get_calendar("XHKG")
now_hk = datetime.now(ZoneInfo("Asia/Hong_Kong"))
session_date = now_hk.date()

if not calendar.is_session(session_date):
    raise SystemExit(1)

session_open = calendar.session_open(session_date).tz_convert("Asia/Hong_Kong").to_pydatetime()
window_end = session_open + timedelta(minutes=45)

if not (session_open <= now_hk < window_end):
    raise SystemExit(1)
PY
then
  exit 0
fi

exec "${PYTHON_BIN}" -m tradesignal --config "${CONFIG_PATH}"
