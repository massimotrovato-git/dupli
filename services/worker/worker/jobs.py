import json
from datetime import datetime, timezone
from sqlalchemy import select
from .db import SessionLocal
from .models import TradeIntent, CopySet, CopySetSlave, Account, PropFirm, RiskProfile, ExecutionLog
from .rules import is_weekend_rome
from .executors import exec_ctrader, exec_mt5
import uuid

def execute_trade_intent(trade_intent_id: str):
    db = SessionLocal()
    try:
        intent = db.get(TradeIntent, trade_intent_id)
        if not intent:
            return {"error": "intent_not_found"}

        # find active copysets for this master
        copysets = db.execute(select(CopySet).where(CopySet.master_id == intent.master_id, CopySet.is_active == True)).scalars().all()
        if not copysets:
            intent.status = "FAILED"
            db.commit()
            return {"error": "no_copysets_for_master"}

        now = datetime.now(timezone.utc)
        payload = {
            "id": str(intent.id),
            "symbol": intent.symbol,
            "side": intent.side,
            "order_type": intent.order_type,
            "entry": intent.entry,
            "zone_low": intent.zone_low,
            "zone_high": intent.zone_high,
            "sl": intent.sl,
            "tps": json.loads(intent.tps) if intent.tps else None,
        }

        for cs in copysets:
            slaves = db.execute(select(CopySetSlave).where(CopySetSlave.copy_set_id == cs.id)).scalars().all()
            for s in slaves:
                acc = db.get(Account, s.account_id)
                if not acc:
                    continue

                # v0.1 rules
                if acc.prop_firm_id:
                    prop = db.get(PropFirm, acc.prop_firm_id)
                    if prop:
                        if is_weekend_rome(now) and not prop.weekend_trading:
                            db.add(ExecutionLog(trade_intent_id=intent.id, account_id=acc.id, status="SKIPPED",
                                                message=f"Weekend blocked by prop '{prop.name}'"))
                            db.commit()
                            continue
                        if prop.news_red_block:
                            db.add(ExecutionLog(trade_intent_id=intent.id, account_id=acc.id, status="SKIPPED",
                                                message=f"NEWS_RED block active for prop '{prop.name}'"))
                            db.commit()
                            continue

                # risk engine v0.1: fixed_lot or max_lot cap (simplified)
                lot = None
                if acc.risk_profile_id:
                    rp = db.get(RiskProfile, acc.risk_profile_id)
                    if rp:
                        if rp.method == "fixed_lot":
                            lot = rp.fixed_lot
                        else:
                            # placeholder: treat risk_per_trade as fixed_lot until SL-distance sizing is added
                            lot = rp.fixed_lot
                        if lot and rp.max_lot:
                            lot = min(lot, rp.max_lot)

                payload2 = dict(payload)
                payload2["lot"] = lot

                if acc.platform.upper() == "MT5":
                    res = exec_mt5(acc.external_id or "", payload2)
                else:
                    res = exec_ctrader(acc.external_id or "", payload2)

                db.add(ExecutionLog(trade_intent_id=intent.id, account_id=acc.id,
                                    status="OK" if res.ok else "ERROR", message=res.message))
                db.commit()

        intent.status = "DONE"
        db.commit()
        return {"ok": True}
    finally:
        db.close()
