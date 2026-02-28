from pydantic import BaseModel
from typing import Optional, Any

class PropFirmIn(BaseModel):
    name: str
    weekend_trading: bool = False
    news_red_block: bool = False

class RiskProfileIn(BaseModel):
    name: str
    method: str = "risk_per_trade"
    risk_percent: float = 1.0
    fixed_lot: float = 0.01
    max_lot: float = 10.0

class AccountIn(BaseModel):
    name: str
    platform: str
    prop_firm_id: Optional[str] = None
    risk_profile_id: Optional[str] = None
    external_id: Optional[str] = None

class MasterIn(BaseModel):
    name: str
    source: str
    is_active: bool = True

class CopySetIn(BaseModel):
    name: str
    master_id: str
    is_active: bool = True

class CopySetSlaveIn(BaseModel):
    copy_set_id: str
    account_id: str

class TradeIntentOut(BaseModel):
    id: str
    master_id: str
    symbol: str
    side: str
    order_type: str
    entry: Optional[float]
    zone_low: Optional[float]
    zone_high: Optional[float]
    sl: Optional[float]
    tps: Optional[str]
    status: str
    created_at: Any
