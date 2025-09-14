# src/copier_simple.py
import os, re, math, sys
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from dotenv import load_dotenv
import MetaTrader5 as mt5

load_dotenv()

# --- Telegram ---
API_ID  = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION  = os.getenv("TELETHON_STRING_SESSION", "")
CHANNEL_ID = int(os.getenv("SIGNAL_CHANNEL_ID", "0"))  # e.g. -1001234567890

# --- MT5 login ---
LOGIN    = int(os.getenv("MT5_LOGIN", "0"))
PASSWORD = os.getenv("MT5_PASSWORD", "")
SERVER   = os.getenv("MT5_SERVER", "")

# --- Trading knobs (simple) ---
TOTAL_LOT   = float(os.getenv("LOT_TOTAL", "0.10"))  # equally split across 3 TPs
MAX_SLIPPAGE = int(os.getenv("MAX_SLIPPAGE", "20"))
SYMBOL_HINT  = os.getenv("MT5_SYMBOL_HINT", "XAUUSD")  # will resolve wildcards like XAUUSD*

# ---------- parsing (STRICT to your format) ----------

PAIR_RE  = re.compile(r"(?im)^\s*Pair:\s*(XAUUSD)\s*$")
TYPE_RE  = re.compile(r"(?im)^\s*Type:\s*(Buy|Sell)\s*$")
ENTRY_RE = re.compile(r"(?im)^\s*Entry\s*Zone:\s*\$?([0-9]+(?:\.[0-9]+)?)\s*$")
TP1_RE   = re.compile(r"(?im)^\s*TP1:\s*\$?([0-9]+(?:\.[0-9]+)?)\s*$")
TP2_RE   = re.compile(r"(?im)^\s*TP2:\s*\$?([0-9]+(?:\.[0-9]+)?)\s*$")
TP3_RE   = re.compile(r"(?im)^\s*TP3:\s*\$?([0-9]+(?:\.[0-9]+)?)\s*$")
SL_RE    = re.compile(r"(?im)^\s*SL:\s*\$?([0-9]+(?:\.[0-9]+)?)\s*$")

def parse_gold_signal(text: str):
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    s = "\n".join(lines)

    m_pair  = PAIR_RE.search(s)
    m_type  = TYPE_RE.search(s)
    m_entry = ENTRY_RE.search(s)
    m_tp1   = TP1_RE.search(s)
    m_tp2   = TP2_RE.search(s)
    m_tp3   = TP3_RE.search(s)
    m_sl    = SL_RE.search(s)

    if not all([m_pair, m_type, m_entry, m_tp1, m_tp2, m_tp3, m_sl]):
        return None

    return {
        "pair":  "XAUUSD",
        "side":  m_type.group(1),  # Buy | Sell
        "entry": float(m_entry.group(1)),
        "tp1":   float(m_tp1.group(1)),
        "tp2":   float(m_tp2.group(1)),
        "tp3":   float(m_tp3.group(1)),
        "sl":    float(m_sl.group(1)),
    }

# ---------- MT5 helpers ----------

def mt5_init_or_die():
    ok = mt5.initialize(login=LOGIN, password=PASSWORD, server=SERVER) if LOGIN else mt5.initialize()
    if not ok:
        print("[MT5] init failed:", mt5.last_error()); sys.exit(1)
    print("[MT5] connected")

def resolve_symbol(hint: str) -> str:
    # exact first
    if mt5.symbol_select(hint, True):
        return hint
    # try wildcards (handles XAUUSD.m, .pro etc)
    for pat in (hint + "*", "*" + hint + "*"):
        found = mt5.symbols_get(pat)
        if found:
            name = found[0].name
            mt5.symbol_select(name, True)
            print(f"[MT5] resolved {hint} -> {name}")
            return name
    # last resort
    mt5.symbol_select(hint, True)
    return hint

def round_volume(sym: str, vol: float) -> float:
    info = mt5.symbol_info(sym)
    step = info.volume_step or 0.01
    vmin = info.volume_min or 0.01
    vmax = info.volume_max or 100.0
    # floor to step and clip into [min,max]
    rounded = math.floor(vol / step) * step
    if rounded < vmin: rounded = vmin
    if rounded > vmax: rounded = vmax
    return round(rounded, 2)

def pending_type(side: str, entry: float, bid: float, ask: float):
    if side == "Buy":
        return mt5.ORDER_TYPE_BUY_STOP if entry > ask else mt5.ORDER_TYPE_BUY_LIMIT
    else:
        return mt5.ORDER_TYPE_SELL_STOP if entry < bid else mt5.ORDER_TYPE_SELL_LIMIT

def place_orders(sig):
    sym = resolve_symbol(SYMBOL_HINT)
    info = mt5.symbol_info(sym)
    tick = mt5.symbol_info_tick(sym)
    if not info or not tick:
        print("[MT5] no symbol info/tick"); return

    # Equal split in 3
    one = TOTAL_LOT / 3.0
    vols = [round_volume(sym, one), round_volume(sym, one), round_volume(sym, one)]
    # small adjustment so sum equals TOTAL_LOT (optional; harmless if slightly off)
    sdiff = TOTAL_LOT - sum(vols)
    if abs(sdiff) >= (info.volume_step or 0.01):
        vols[-1] = round_volume(sym, vols[-1] + sdiff)

    otype = pending_type(sig["side"], sig["entry"], tick.bid, tick.ask)
    tps = [sig["tp1"], sig["tp2"], sig["tp3"]]

    for v, tp in zip(vols, tps):
        req = {
            "action":   mt5.TRADE_ACTION_PENDING,
            "symbol":   sym,
            "volume":   v,
            "type":     otype,
            "price":    sig["entry"],
            "sl":       sig["sl"],
            "tp":       tp,
            "deviation": MAX_SLIPPAGE,
            "type_time": mt5.ORDER_TIME_GTC,
            "comment":  "gold-copier",
        }
        if sig["side"] == "Buy":
            # for safety, no market sends here—only pending
            pass
        res = mt5.order_send(req)
        print("[MT5] order_send:", res)

# ---------- Telethon ----------

def tg_client():
    if not API_ID or not API_HASH or not CHANNEL_ID:
        print("[CFG] set API_ID, API_HASH, TELETHON_STRING_SESSION and SIGNAL_CHANNEL_ID"); sys.exit(1)
    return TelegramClient(StringSession(SESSION), API_ID, API_HASH)

async def on_message(event):
    txt = (event.raw_text or "").strip()
    sig = parse_gold_signal(txt)
    if not sig:
        return
    if sig["pair"].upper() != "XAUUSD":
        return
    print("[SIG] parsed:", sig)
    place_orders(sig)

def main():
    mt5_init_or_die()
    client = tg_client()
    with client:
        client.loop.run_until_complete(client.connect())
        client.add_event_handler(on_message, events.NewMessage(chats=[CHANNEL_ID]))
        print(f"[RUN] listening channel {CHANNEL_ID} for GOLD signals…")
        client.run_until_disconnected()

if __name__ == "__main__":
    main()