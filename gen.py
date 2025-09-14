from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = int(input("API_ID: ").strip())
api_hash = input("API_HASH: ").strip()
phone = input("Phone (international format, e.g. +12025550123): ").strip()

with TelegramClient(StringSession(), api_id, api_hash) as client:
    client.connect()
    if not client.is_user_authorized():
        # send login code
        client.send_code_request(phone)
        code = input("Login code (from Telegram): ").strip()
        try:
            client.sign_in(phone=phone, code=code)
        except Exception as e:
            # 2FA enabled? ask password
            if "SESSION_PASSWORD_NEEDED" in str(e).upper():
                pwd = input("Two-factor password: ").strip()
                client.sign_in(password=pwd)
            else:
                raise
    print("\n>>> Copy this value into your .env as TELETHON_STRING_SESSION <<<\n")
    print(client.session.save())