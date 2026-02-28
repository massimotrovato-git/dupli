import os, requests
from dataclasses import dataclass

@dataclass
class ExecResult:
    ok: bool
    message: str

def exec_ctrader(account_external_id: str, intent: dict) -> ExecResult:
    # v0.1 stub - implement cTrader Open API calls here
    return ExecResult(ok=False, message="cTrader executor not implemented in v0.1")

def exec_mt5(account_external_id: str, intent: dict) -> ExecResult:
    url = os.getenv("MT5_GATEWAY_URL", "").rstrip("/")
    if not url:
        return ExecResult(ok=False, message="MT5_GATEWAY_URL not set")
    try:
        r = requests.post(url + "/v1/orders", json={"account_external_id": account_external_id, "intent": intent}, timeout=10)
        if r.status_code == 200:
            return ExecResult(ok=True, message=r.text)
        return ExecResult(ok=False, message=f"HTTP {r.status_code}: {r.text}")
    except Exception as e:
        return ExecResult(ok=False, message=str(e))
