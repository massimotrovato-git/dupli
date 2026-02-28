# MT5 Gateway (Windows)
This is a lightweight HTTP gateway that receives orders from CORE and forwards them to MT5 terminals via EA bridge.
In v0.1 this is a **protocol skeleton**. You must implement the EA bridge side.

## Run (dev)
```powershell
py -m pip install flask waitress
py -m mt5_gateway.app
```

## Endpoints
- POST /v1/orders
  Body: { "account_external_id": "123456", "intent": {...} }

## Security
Put this behind Windows Firewall allow-list to only accept CORE server IP.
