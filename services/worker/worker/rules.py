from datetime import datetime
from zoneinfo import ZoneInfo
ROME = ZoneInfo("Europe/Rome")

def is_weekend_rome(now: datetime) -> bool:
    return now.astimezone(ROME).weekday() >= 5
