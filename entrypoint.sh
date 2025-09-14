#!/usr/bin/env bash
set -euo pipefail
set -x

# --- sanity ---
command -v wine >/dev/null || { echo "[ERR] wine not installed in image"; exit 1; }
: "${MT5_LOGIN:?MT5_LOGIN not set}"
: "${MT5_PASSWORD:?MT5_PASSWORD not set}"
: "${MT5_SERVER:?MT5_SERVER not set}"

# --- headless X for Wine/MT5 ---
export DISPLAY=:1
Xvfb :1 -screen 0 1024x768x16 &
sleep 3

# --- make Wine non-interactive on first run ---
export WINEPREFIX="${WINEPREFIX:-/root/.wine}"
export WINEDEBUG=-all
export WINEDLLOVERRIDES="mscoree,mshtml="   # disable Mono/Gecko prompts

# Initialize/upgrade prefix without opening winecfg UI
wineboot -u
# wait for wineserver to finish any pending init
wineserver -w || true

# --- install MT5 (first run only) ---
MT5_DIR="$WINEPREFIX/drive_c/Program Files/MetaTrader 5"
MT5_INI="$MT5_DIR/Config/common.ini"

if [ ! -d "$MT5_DIR" ]; then
  echo "[MT5] Installing terminal…"
  wine /opt/mt5/mt5setup.exe &

  # give the installer a default "Next"
  sleep 10
  xdotool key Return || true

  # wait up to ~10 minutes for common.ini to appear
  for i in $(seq 1 300); do
    if [ -f "$MT5_INI" ]; then break; fi
    echo "[MT5] waiting for installer to finish… ($i)"
    sleep 2
  done

  if [ ! -f "$MT5_INI" ]; then
    echo "[ERR] MT5 installer did not produce $MT5_INI"
    exit 1
  fi
fi

# --- ensure Windows Python exists and MetaTrader5 is available ---
PY_EXE="$WINEPREFIX/drive_c/Python311/python.exe"
if [ ! -x "$PY_EXE" ]; then
  echo "[PYWIN] Installing Windows Python 3.11…"
  cd /tmp
  wget -q https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe -O py311.exe
  wine py311.exe /quiet InstallAllUsers=1 PrependPath=1 Include_launcher=0 Include_test=0 TargetDir="C:\\Python311"

  # normalize path (older installers sometimes go to AppData)
  if [ ! -x "$PY_EXE" ] && [ -x "$WINEPREFIX/drive_c/Users/root/AppData/Local/Programs/Python/Python311/python.exe" ]; then
    PY_EXE="$WINEPREFIX/drive_c/Users/root/AppData/Local/Programs/Python/Python311/python.exe"
  fi
fi

echo "[PYWIN] Installing pip packages…"
wine "$PY_EXE" -m pip install -U pip setuptools wheel
wine "$PY_EXE" -m pip install MetaTrader5 telethon python-dotenv

# --- launch MT5 ---
wine "$MT5_DIR/terminal64.exe" &

# bring MT5 window to the foreground before sending keystrokes
for i in $(seq 1 120); do
  WID="$(xdotool search --name 'MetaTrader 5' | head -n1 || true)"
  [ -n "$WID" ] && { xdotool windowactivate --sync "$WID"; break; }
  sleep 1
done

# login loop until we see our account in the config
until iconv -f utf-16 -t utf-8 "$MT5_INI" 2>/dev/null | grep -q "${MT5_LOGIN}"; do
  echo "[MT5] logging in…"
  xdotool key Alt+F+L
  xdotool key Ctrl+A; xdotool type --delay 1 "${MT5_LOGIN}"
  xdotool key Tab
  xdotool key Ctrl+A; xdotool type --delay 1 "${MT5_PASSWORD}"
  xdotool key Tab; xdotool key Tab
  xdotool key Ctrl+A; xdotool type --delay 1 "${MT5_SERVER}"
  xdotool key Tab
  xdotool key Return
  sleep 5
done
echo "[MT5] connected."

# --- run your Telegram copier under Windows Python (so MetaTrader5 works) ---
echo "[BOT] starting copier…"
exec wine "$PY_EXE" -u Z:\\app\\copier.py