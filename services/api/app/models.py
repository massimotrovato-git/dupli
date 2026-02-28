from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from .db import Base

class PropFirm(Base):
    __tablename__ = "prop_firms"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), unique=True, nullable=False)
    weekend_trading = Column(Boolean, default=False)
    news_red_block = Column(Boolean, default=False)  # manual switch in v0.1
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class RiskProfile(Base):
    __tablename__ = "risk_profiles"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    method = Column(String(50), nullable=False, default="risk_per_trade")  # fixed_lot | percent_equity | risk_per_trade
    risk_percent = Column(Float, default=1.0)  # for percent_equity
    fixed_lot = Column(Float, default=0.01)
    max_lot = Column(Float, default=10.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Account(Base):
    __tablename__ = "accounts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    platform = Column(String(20), nullable=False)  # CTRADER | MT5
    prop_firm_id = Column(UUID(as_uuid=True), ForeignKey("prop_firms.id"), nullable=True)
    risk_profile_id = Column(UUID(as_uuid=True), ForeignKey("risk_profiles.id"), nullable=True)

    # platform identifiers
    external_id = Column(String(200), nullable=True)  # e.g., cTrader accountId or MT5 login
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    prop_firm = relationship("PropFirm")
    risk_profile = relationship("RiskProfile")

class Master(Base):
    __tablename__ = "masters"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    source = Column(String(50), nullable=False)  # telegram | ctrader | manual
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class CopySet(Base):
    __tablename__ = "copy_sets"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    master_id = Column(UUID(as_uuid=True), ForeignKey("masters.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    master = relationship("Master")

class CopySetSlave(Base):
    __tablename__ = "copy_set_slaves"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    copy_set_id = Column(UUID(as_uuid=True), ForeignKey("copy_sets.id"), nullable=False)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)

    copy_set = relationship("CopySet")
    account = relationship("Account")

class TradeIntent(Base):
    __tablename__ = "trade_intents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    master_id = Column(UUID(as_uuid=True), ForeignKey("masters.id"), nullable=False)

    symbol = Column(String(50), nullable=False)
    side = Column(String(10), nullable=False)  # BUY|SELL
    order_type = Column(String(20), nullable=False)  # MARKET|LIMIT|STOP|ZONE
    entry = Column(Float, nullable=True)
    zone_low = Column(Float, nullable=True)
    zone_high = Column(Float, nullable=True)
    sl = Column(Float, nullable=True)
    tps = Column(Text, nullable=True)  # JSON string v0.1

    raw_text = Column(Text, nullable=True)
    status = Column(String(20), default="NEW")  # NEW|QUEUED|DONE|FAILED|BLOCKED
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    master = relationship("Master")

class ExecutionLog(Base):
    __tablename__ = "execution_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trade_intent_id = Column(UUID(as_uuid=True), ForeignKey("trade_intents.id"), nullable=False)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    status = Column(String(20), nullable=False)  # OK|ERROR|SKIPPED
    message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
