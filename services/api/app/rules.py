from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from .models import Account, PropFirm

ROME = ZoneInfo("Europe/Rome")

def is_weekend_rome(now: datetime) -> bool:
    wd = now.astimezone(ROME).weekday()  # 0=Mon ... 6=Sun
    return wd >= 5

def can_trade_now(db: Session, account: Account, now: datetime) -> tuple[bool, str]:
    # v0.1:
    # - weekend block unless prop allows weekend_trading
    # - news_red_block is a manual toggle on the PropFirm
    prop: PropFirm | None = account.prop_firm
    if prop:
        if is_weekend_rome(now) and not prop.weekend_trading:
            return False, f"Weekend trading blocked by prop '{prop.name}'"
        if prop.news_red_block:
            return False, f"NEWS_RED block is active for prop '{prop.name}'"
    return True, "OK"
