import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.utils import get_peer_id
from telethon.tl.types import Channel, Chat

API_ID = 20729275
API_HASH = "481067047f0834f399fda81576eb3c16"
SESSION = "1ApWapzMBuwad6WgE-PH-ZqlxY-d95_LrtWNjz7aS4geDf-XkMVULF2OlrvGw4GO_xSNaFAMjwqYsHvkO6BhDQFdasuvhCkh3by8SXRB2esrnQQSOtHimadt2C7XckJsEXt5Y-E7rsP2FkRvz0MdsWysu4Ai606i_b_JU8g5aPTlP5Vo7y8AjDiAG0ldq3w57UVhglPGYhO2XswsaKS8UenVpe5vCBUMnxuoXvnSAXzGuBjRM_OVPBdyYyyaSlYlYT9_8uNKDdQqiFfsDmfNs0OwOXwEdwZsVJ39D9ouakm4ZH4l7yNxqRPAUex3loaR3AKbLfAsnfQI9nHL3uqp3zBLLYYZFNYw="

with TelegramClient(StringSession(SESSION), API_ID, API_HASH) as client:
    for d in client.iter_dialogs():
        ent = d.entity
        if isinstance(ent, (Channel, Chat)):
            pid = get_peer_id(ent)              # e.g. -1002352183220
            uname = getattr(ent, "username", None)
            alias = ("@" + uname) if uname else ""
            print(f"{pid}\t{alias}\t{d.name}")