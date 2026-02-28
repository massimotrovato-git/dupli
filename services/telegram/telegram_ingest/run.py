import os, sys, uuid, asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from sqlalchemy import select
from .db import SessionLocal
from .models import Master, TradeIntent
from .parser import parse


def _require_env(name: str) -> str:
    """Return env var value or exit with a clear error (no interactive prompt)."""
    value = os.getenv(name, "").strip()
    if not value:
        print(f"FATAL: environment variable {name} is required but not set. Exiting.", flush=True)
        sys.exit(1)
    return value


async def main():
    api_id_raw = _require_env("TELEGRAM_API_ID")
    api_hash = _require_env("TELEGRAM_API_HASH")
    session_string = _require_env("TELEGRAM_SESSION_STRING")
    chat_id = int(os.getenv("TELEGRAM_SOURCE_CHAT_ID", "0"))

    try:
        api_id = int(api_id_raw)
    except ValueError:
        print(f"FATAL: TELEGRAM_API_ID must be an integer, got: {api_id_raw!r}", flush=True)
        sys.exit(1)

    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        print("FATAL: session string is invalid or expired. Generate a new one.", flush=True)
        sys.exit(1)
    print("Telegram client connected (user session).", flush=True)

    # pick or create a Master source=telegram
    db = SessionLocal()
    try:
        m = db.execute(select(Master).where(Master.source == "telegram")).scalars().first()
        if not m:
            # relies on masters table already created by API container
            print("No telegram master found. Create one via API: POST /api/masters {name, source:'telegram'}")
        else:
            print(f"Using master: {m.name} ({m.id})")
    finally:
        db.close()

    @client.on(events.NewMessage(chats=chat_id if chat_id != 0 else None))
    async def handler(event):
        text = event.raw_text or ""
        ps = parse(text)
        if not ps:
            return
        db = SessionLocal()
        try:
            m = db.execute(select(Master).where(Master.source == "telegram", Master.is_active == True)).scalars().first()
            if not m:
                return
            ti = TradeIntent(
                id=uuid.uuid4(),
                master_id=m.id,
                symbol=ps.symbol,
                side=ps.side,
                order_type=ps.order_type,
                entry=ps.entry,
                zone_low=ps.zone_low,
                zone_high=ps.zone_high,
                sl=ps.sl,
                tps=ps.tps_json,
                raw_text=text,
                status="NEW",
            )
            db.add(ti); db.commit()
            print(f"Saved TradeIntent {ti.id} {ti.symbol} {ti.side} {ti.order_type}")
        finally:
            db.close()

    print("Telegram ingest running...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
