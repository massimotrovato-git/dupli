from flask import Flask, request, jsonify
from waitress import serve
import os, time

app = Flask(__name__)

@app.post("/v1/orders")
def orders():
    body = request.get_json(force=True, silent=False)
    # v0.1: just acknowledge. Replace with dispatch to EA bridge.
    return jsonify({"ok": True, "received": body, "ts": time.time()})

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8090"))
    serve(app, host="0.0.0.0", port=port)
