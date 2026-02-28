# duplicated minimal models for worker (keep in sync for v0.1)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

Base = declarative_base()

class PropFirm(Base):
    __tablename__ = "prop_firms"
    id = Column(UUID(as_uuid=True), primary_key=True)
    name = Column(String(200))
    weekend_trading = Column(Boolean)
    news_red_block = Column(Boolean)

class RiskProfile(Base):
    __tablename__ = "risk_profiles"
    id = Column(UUID(as_uuid=True), primary_key=True)
    name = Column(String(200))
    method = Column(String(50))
    risk_percent = Column(Float)
    fixed_lot = Column(Float)
    max_lot = Column(Float)

class Account(Base):
    __tablename__ = "accounts"
    id = Column(UUID(as_uuid=True), primary_key=True)
    name = Column(String(200))
    platform = Column(String(20))
    prop_firm_id = Column(UUID(as_uuid=True), ForeignKey("prop_firms.id"))
    risk_profile_id = Column(UUID(as_uuid=True), ForeignKey("risk_profiles.id"))
    external_id = Column(String(200))

class Master(Base):
    __tablename__ = "masters"
    id = Column(UUID(as_uuid=True), primary_key=True)
    name = Column(String(200))
    source = Column(String(50))
    is_active = Column(Boolean)

class CopySet(Base):
    __tablename__ = "copy_sets"
    id = Column(UUID(as_uuid=True), primary_key=True)
    name = Column(String(200))
    master_id = Column(UUID(as_uuid=True), ForeignKey("masters.id"))
    is_active = Column(Boolean)

class CopySetSlave(Base):
    __tablename__ = "copy_set_slaves"
    id = Column(UUID(as_uuid=True), primary_key=True)
    copy_set_id = Column(UUID(as_uuid=True), ForeignKey("copy_sets.id"))
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"))

class TradeIntent(Base):
    __tablename__ = "trade_intents"
    id = Column(UUID(as_uuid=True), primary_key=True)
    master_id = Column(UUID(as_uuid=True), ForeignKey("masters.id"))
    symbol = Column(String(50))
    side = Column(String(10))
    order_type = Column(String(20))
    entry = Column(Float)
    zone_low = Column(Float)
    zone_high = Column(Float)
    sl = Column(Float)
    tps = Column(Text)
    raw_text = Column(Text)
    status = Column(String(20))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ExecutionLog(Base):
    __tablename__ = "execution_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trade_intent_id = Column(UUID(as_uuid=True), ForeignKey("trade_intents.id"))
    account_id = Column(UUID(as_uuid=True))
    status = Column(String(20))
    message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
