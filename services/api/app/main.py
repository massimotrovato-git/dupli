from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime, timezone

from .db import Base, engine, SessionLocal
from .models import PropFirm, RiskProfile, Account, Master, CopySet, CopySetSlave, TradeIntent, ExecutionLog
from .schemas import PropFirmIn, RiskProfileIn, AccountIn, MasterIn, CopySetIn, CopySetSlaveIn, TradeIntentOut
from .auth import get_user, require_role
from .queue import get_queue
from .rules import can_trade_now

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Dupli-Clone v0.1")

def db_dep():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    u = get_user(request)
    return f"""<html><body>
    <h2>Dupli-Clone v0.1</h2>
    <p>User: <b>{u.username}</b></p>
    <p>Roles: <b>{', '.join(sorted(u.roles))}</b></p>
    <ul>
      <li><a href="/docs">API Docs</a></li>
      <li><a href="/ui">Web UI (minimal)</a></li>
    </ul>
    </body></html>"""

@app.get("/ui", response_class=HTMLResponse)
def ui(request: Request, db: Session = Depends(db_dep)):
    u = get_user(request)
    props = db.execute(select(PropFirm).order_by(PropFirm.name)).scalars().all()
    masters = db.execute(select(Master).order_by(Master.created_at.desc())).scalars().all()
    intents = db.execute(select(TradeIntent).order_by(TradeIntent.created_at.desc()).limit(50)).scalars().all()
    def li(x): return "<li>" + x + "</li>"
    return f"""<html><body>
    <h2>Minimal UI</h2>
    <p>User: <b>{u.username}</b> | Roles: <b>{', '.join(sorted(u.roles))}</b></p>
    <h3>Props (news_red_block / weekend_trading)</h3>
    <ul>
      {''.join([li(f"{p.name} | weekend={p.weekend_trading} | news_red={p.news_red_block}") for p in props])}
    </ul>
    <h3>Masters</h3>
    <ul>
      {''.join([li(f"{m.name} | source={m.source} | active={m.is_active}") for m in masters])}
    </ul>
    <h3>Latest TradeIntents</h3>
    <ul>
      {''.join([li(f"{t.created_at} | {t.symbol} {t.side} {t.order_type} | status={t.status}") for t in intents])}
    </ul>
    <p>Use <a href="/docs">/docs</a> for full CRUD and actions.</p>
    </body></html>"""

# --- CRUD endpoints (Admin/Operator) ---
@app.post("/api/props", tags=["props"])
def create_prop(payload: PropFirmIn, request: Request, db: Session = Depends(db_dep)):
    u = get_user(request); require_role(u, "admin", "operator")
    obj = PropFirm(**payload.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return {"id": str(obj.id)}

@app.get("/api/props", tags=["props"])
def list_props(request: Request, db: Session = Depends(db_dep)):
    u = get_user(request); require_role(u, "admin", "operator", "viewer")
    items = db.execute(select(PropFirm).order_by(PropFirm.name)).scalars().all()
    return [{"id": str(p.id), "name": p.name, "weekend_trading": p.weekend_trading, "news_red_block": p.news_red_block} for p in items]

@app.post("/api/risk_profiles", tags=["risk"])
def create_risk(payload: RiskProfileIn, request: Request, db: Session = Depends(db_dep)):
    u = get_user(request); require_role(u, "admin", "operator")
    obj = RiskProfile(**payload.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return {"id": str(obj.id)}

@app.post("/api/accounts", tags=["accounts"])
def create_account(payload: AccountIn, request: Request, db: Session = Depends(db_dep)):
    u = get_user(request); require_role(u, "admin", "operator")
    obj = Account(**payload.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return {"id": str(obj.id)}

@app.get("/api/accounts", tags=["accounts"])
def list_accounts(request: Request, db: Session = Depends(db_dep)):
    u = get_user(request); require_role(u, "admin", "operator", "viewer")
    items = db.execute(select(Account).order_by(Account.created_at.desc())).scalars().all()
    return [{"id": str(a.id), "name": a.name, "platform": a.platform, "external_id": a.external_id,
             "prop_firm_id": str(a.prop_firm_id) if a.prop_firm_id else None,
             "risk_profile_id": str(a.risk_profile_id) if a.risk_profile_id else None} for a in items]

@app.post("/api/masters", tags=["masters"])
def create_master(payload: MasterIn, request: Request, db: Session = Depends(db_dep)):
    u = get_user(request); require_role(u, "admin", "operator")
    obj = Master(**payload.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return {"id": str(obj.id)}

@app.post("/api/copysets", tags=["copysets"])
def create_copyset(payload: CopySetIn, request: Request, db: Session = Depends(db_dep)):
    u = get_user(request); require_role(u, "admin", "operator")
    obj = CopySet(**payload.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return {"id": str(obj.id)}

@app.post("/api/copysets/slaves", tags=["copysets"])
def add_slave(payload: CopySetSlaveIn, request: Request, db: Session = Depends(db_dep)):
    u = get_user(request); require_role(u, "admin", "operator")
    obj = CopySetSlave(**payload.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return {"id": str(obj.id)}

@app.get("/api/trade_intents", tags=["trade"])
def list_trade_intents(request: Request, db: Session = Depends(db_dep)):
    u = get_user(request); require_role(u, "admin", "operator", "viewer")
    items = db.execute(select(TradeIntent).order_by(TradeIntent.created_at.desc()).limit(200)).scalars().all()
    return [TradeIntentOut(
        id=str(t.id), master_id=str(t.master_id), symbol=t.symbol, side=t.side, order_type=t.order_type,
        entry=t.entry, zone_low=t.zone_low, zone_high=t.zone_high, sl=t.sl, tps=t.tps, status=t.status,
        created_at=t.created_at
    ).model_dump() for t in items]

# --- Actions: queue execution ---
def _enqueue_execution(trade_intent_id: str):
    q = get_queue()
    job = q.enqueue("worker.jobs.execute_trade_intent", trade_intent_id)
    return job.id

@app.post("/api/trade_intents/{intent_id}/queue", tags=["trade"])
def queue_intent(intent_id: str, request: Request, db: Session = Depends(db_dep)):
    u = get_user(request); require_role(u, "admin", "operator")
    t = db.get(TradeIntent, intent_id)
    if not t:
        return {"error": "not_found"}
    t.status = "QUEUED"
    db.commit()
    job_id = _enqueue_execution(intent_id)
    return {"job_id": job_id}

@app.get("/api/health", tags=["system"])
def health(request: Request):
    u = get_user(request)
    return {"ok": True, "user": u.username, "roles": sorted(list(u.roles))}

