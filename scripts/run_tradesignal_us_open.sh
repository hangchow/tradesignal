#!/bin/zsh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
CONFIG_PATH="${HOME}/config/tradesignal_us.json"
STRATEGY_CONFIG_PATH="${PROJECT_ROOT}/config/strategy_config.dual_momentum.json"
GIT_PULL_LOCKDIR="/tmp/tradesignal-git-pull.lock"

cd "${PROJECT_ROOT}"

current_branch="$(git -C "${PROJECT_ROOT}" branch --show-current 2>/dev/null || true)"
if [[ "${current_branch}" == "main" ]]; then
  if mkdir "${GIT_PULL_LOCKDIR}" 2>/dev/null; then
    if ! git -C "${PROJECT_ROOT}" pull --ff-only origin main; then
      echo "git pull failed, continuing with existing local code" >&2
    fi
    rmdir "${GIT_PULL_LOCKDIR}"
  else
    echo "git pull skipped: lock is held by another tradesignal job" >&2
  fi
else
  echo "git pull skipped: current branch is '${current_branch:-unknown}', expected 'main'" >&2
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "python not found: ${PYTHON_BIN}" >&2
  exit 1
fi

if [[ ! -f "${CONFIG_PATH}" ]]; then
  echo "config not found: ${CONFIG_PATH}" >&2
  exit 1
fi

if [[ ! -f "${STRATEGY_CONFIG_PATH}" ]]; then
  echo "strategy config not found: ${STRATEGY_CONFIG_PATH}" >&2
  exit 1
fi

if ! "${PYTHON_BIN}" - <<'PY'
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import exchange_calendars as xcals

calendar = xcals.get_calendar("XNYS")
now_ny = datetime.now(ZoneInfo("America/New_York"))
session_date = now_ny.date()

if not calendar.is_session(session_date):
    raise SystemExit(1)

session_open = calendar.session_open(session_date).tz_convert("America/New_York").to_pydatetime()
window_end = session_open + timedelta(minutes=45)

if not (session_open <= now_ny < window_end):
    raise SystemExit(1)
PY
then
  exit 0
fi

exec "${PYTHON_BIN}" -m tradesignal --config "${CONFIG_PATH}" --strategy-config "${STRATEGY_CONFIG_PATH}"
