from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

Base = declarative_base()

class Master(Base):
    __tablename__ = "masters"
    id = Column(UUID(as_uuid=True), primary_key=True)
    name = Column(String(200))
    source = Column(String(50))
    is_active = Column(Boolean)

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
