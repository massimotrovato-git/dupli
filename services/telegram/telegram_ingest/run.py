import os, uuid, asyncio
from telethon import TelegramClient, events
from sqlalchemy import select
from .db import SessionLocal
from .models import Master, TradeIntent
from .parser import parse

async def main():
    api_id = int(os.getenv("TELEGRAM_API_ID"))
    api_hash = os.getenv("TELEGRAM_API_HASH")
    session = os.getenv("TELEGRAM_SESSION", "telegram.session")
    chat_id = int(os.getenv("TELEGRAM_SOURCE_CHAT_ID", "0"))

    client = TelegramClient(session, api_id, api_hash)
    await client.start()

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
