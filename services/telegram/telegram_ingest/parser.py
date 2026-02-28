import re, json
from dataclasses import dataclass
from typing import Optional

@dataclass
class ParsedSignal:
    symbol: str
    side: str
    order_type: str
    entry: Optional[float]
    zone_low: Optional[float]
    zone_high: Optional[float]
    sl: Optional[float]
    tps_json: Optional[str]

# v0.1 parser expects a fairly standard format like:
# "XAUUSD SELL ZONE 5187.5-5190 SL 5205 TP1 5170 TP2 5150"
ZONE_RE = re.compile(r"(?P<sym>[A-Z0-9/_-]+)\s+(?P<side>BUY|SELL)\s+(?P<otype>ZONE|LIMIT|STOP|MARKET|NOW)\s*(?P<zone>\d+(?:\.\d+)?(?:\s*[-–]\s*\d+(?:\.\d+)?)?)?", re.I)
SL_RE = re.compile(r"\bSL\b\s*(?P<sl>\d+(?:\.\d+)?)", re.I)
TP_RE = re.compile(r"\bTP(?P<n>\d+)\b\s*(?P<tp>\d+(?:\.\d+)?)", re.I)

def parse(text: str) -> Optional[ParsedSignal]:
    t = " ".join(text.strip().split())
    m = ZONE_RE.search(t)
    if not m:
        return None
    sym = m.group("sym").upper()
    side = m.group("side").upper()
    otype_raw = m.group("otype").upper()
    order_type = "MARKET" if otype_raw in ("NOW","MARKET") else otype_raw
    entry = None
    zone_low = None
    zone_high = None
    zone = m.group("zone")
    if zone:
        if "-" in zone or "–" in zone:
            parts = re.split(r"[-–]", zone)
            zone_low = float(parts[0].strip())
            zone_high = float(parts[1].strip())
        else:
            entry = float(zone.strip())

    sl = None
    msl = SL_RE.search(t)
    if msl:
        sl = float(msl.group("sl"))

    tps = []
    for mtp in TP_RE.finditer(t):
        tps.append({"n": int(mtp.group("n")), "price": float(mtp.group("tp"))})
    tps_json = json.dumps(sorted(tps, key=lambda x: x["n"])) if tps else None

    return ParsedSignal(sym, side, order_type, entry, zone_low, zone_high, sl, tps_json)
