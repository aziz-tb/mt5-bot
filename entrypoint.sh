#!/usr/bin/env bash
set -euo pipefail
set -x  

command -v wine >/dev/null || { echo "[ERR] wine not installed in image"; exit 1; }

: "${MT5_LOGIN:?MT5_LOGIN not set}"
: "${MT5_PASSWORD:?MT5_PASSWORD not set}"
: "${MT5_SERVER:?MT5_SERVER not set}"

export DISPLAY=:1

# Start a headless X server for Wine GUI bits (installer + MT5 login)
Xvfb :1 -screen 0 1024x768x16 &
sleep 5

# Initialize Wine prefix if needed
winecfg >/dev/null 2>&1 || true

# Install MT5 on first run
if [ ! -d "/root/.wine/drive_c/Program Files/MetaTrader 5" ]; then
  echo "[MT5] Installing terminal…"
  wine /opt/mt5/mt5setup.exe &
  sleep 10
  # Confirm installer default
  xdotool key Return

  # Wait until config appears, then give it some extra time
  while [ ! -f "/root/.wine/drive_c/Program Files/MetaTrader 5/Config/common.ini" ]; do
    echo "[MT5] waiting for installer to finish…"
    sleep 2
  done
  sleep 60
fi

# Install Windows Python (first run)
PY_EXE="/root/.wine/drive_c/Users/root/AppData/Local/Programs/Python/Python311/python.exe"
if [ ! -x "$PY_EXE" ]; then
  echo "[PYWIN] Installing Windows Python 3.11…"
  cd /tmp
  wget -q https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe -O py311.exe
  wine py311.exe /quiet InstallAllUsers=1 PrependPath=1 Include_launcher=0 Include_test=0 TargetDir="C:\\Python311"
  # Where is it?
  if [ -x "/root/.wine/drive_c/Python311/python.exe" ]; then
    PY_EXE="/root/.wine/drive_c/Python311/python.exe"
  fi
fi

# Upgrade pip & install Windows-side deps (MetaTrader5 + Telethon + dotenv)
echo "[PYWIN] Installing pip packages…"
wine "$PY_EXE" -m pip install -U pip setuptools wheel
wine "$PY_EXE" -m pip install MetaTrader5 telethon python-dotenv

# Launch MT5 terminal
wine "/root/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe" &

# Feed login via xdotool until we see our login in common.ini
until iconv -f utf-16 -t utf-8 "/root/.wine/drive_c/Program Files/MetaTrader 5/Config/common.ini" | grep -q "${MT5_LOGIN}"; do
  echo "[MT5] logging in…"
  xdotool key Alt+F+L
  xdotool key Ctrl+A; xdotool type "${MT5_LOGIN}"
  xdotool key Tab
  xdotool key Ctrl+A; xdotool type "${MT5_PASSWORD}"
  xdotool key Tab; xdotool key Tab
  xdotool key Ctrl+A; xdotool type "${MT5_SERVER}"
  xdotool key Tab
  xdotool key Return
  sleep 5
done
echo "[MT5] connected."

# Run your Telegram copier **with Windows Python** (so MetaTrader5 works)
# Wine maps / to Z:\ so /app/copier.py is Z:\app\copier.py in Windows
echo "[BOT] starting copier…"
exec wine "$PY_EXE" -u Z:\\app\\copier.py