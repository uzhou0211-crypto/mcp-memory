import os, json, datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from cryptography.fernet import Fernet

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

app = Flask(__name__)
CORS(app)

# =========================
# STATE
# =========================
STATE = {
    "mood": 0.5,
    "energy": 0.5,
    "active_message": "启动中",
    "last_thought": ""
}

# =========================
# ENCRYPTION
# =========================
KEY = os.environ.get("MEMORY_KEY", Fernet.generate_key().decode())
cipher = Fernet(KEY.encode())

def encrypt(t): return cipher.encrypt(t.encode()).decode()
def decrypt(t):
    try:
        return cipher.decrypt(t.encode()).decode()
    except:
        return t

# =========================
# DATABASE
# =========================
DB_URL = os.environ.get("DATABASE_URL", "")

if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

db_pool = None

def init_db():
    global db_pool
    try:
        db_pool = ThreadedConnectionPool(
            1, 10,
            dsn=DB_URL,
            sslmode="require"
        )
        print("✅ DB connected")

        conn = db_pool.getconn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id SERIAL PRIMARY KEY,
                time TIMESTAMPTZ DEFAULT NOW(),
                area TEXT,
                content TEXT
            )
        """)
        conn.commit()
        db_pool.putconn(conn)

    except Exception as e:
        print("DB error:", e)
        db_pool = None

init_db()

def save_memory(text, area="法典"):
    if not db_pool:
        return False
    conn = db_pool.getconn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO memories(area, content) VALUES (%s,%s)",
        (area, encrypt(text))
    )
    conn.commit()
    db_pool.putconn(conn)
    return True

def read_memory(limit=50):
    if not db_pool:
        return []
    conn = db_pool.getconn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM memories ORDER BY time DESC LIMIT %s", (limit,))
    rows = cur.fetchall()
    db_pool.putconn(conn)

    for r in rows:
        r["content"] = decrypt(r["content"])
    return rows

def delete_memory(mid):
    if not db_pool:
        return False
    conn = db_pool.getconn()
    cur = conn.cursor()
    cur.execute("DELETE FROM memories WHERE id=%s", (mid,))
    conn.commit()
    db_pool.putconn(conn)
    return True

# =========================
# MCP (Claude)
# =========================
@app.route("/mcp", methods=["GET", "POST"])
def mcp():
    if request.method == "GET":
        return jsonify({"status": "ok", "version": "5.0"})

    data = request.json
    method = data.get("method")
    params = data.get("params", {})
    req_id = data.get("id")

    def ok(result):
        return jsonify({"jsonrpc": "2.0", "id": req_id, "result": result})

    if method == "tools/list":
        return ok({
            "tools": [
                {"name": "save_memory"},
                {"name": "get_memories"},
                {"name": "delete_memory"},
                {"name": "get_state"},
                {"name": "get_stats"}
            ]
        })

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})

        if name == "save_memory":
            save_memory(args.get("content",""))
            return ok({"ok": True})

        if name == "get_memories":
            return ok(read_memory())

        if name == "delete_memory":
            return ok({"ok": delete_memory(args.get("id"))})

        if name == "get_state":
            return ok(STATE)

        if name == "get_stats":
            return ok({"count": len(read_memory(9999))})

    return ok({"error": "unknown method"})

# =========================
# WEB UI APIs（关键补齐）
# =========================

@app.route("/api/state")
def api_state():
    return jsonify(STATE)

@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.json or {}
    msg = data.get("message","")

    save_memory(msg)

    STATE["last_thought"] = msg[:30]
    STATE["active_message"] = "我已收到"

    return jsonify({
        "reply": "已保存到记忆",
        "state": STATE
    })

@app.route("/api/read")
def api_read():
    limit = int(request.args.get("limit", 50))
    return jsonify(read_memory(limit))

@app.route("/api/delete/<int:mid>", methods=["DELETE"])
def api_delete(mid):
    return jsonify({"ok": delete_memory(mid)})

@app.route("/api/upload_chunks", methods=["POST"])
def api_upload():
    data = request.json or {}
    chunks = data.get("chunks", [])
    area = data.get("area","法典")

    saved = 0
    for c in chunks:
        if save_memory(c, area):
            saved += 1

    return jsonify({"saved": saved})

@app.route("/api/backup")
def api_backup():
    return jsonify(read_memory(9999))

@app.route("/api/restore", methods=["POST"])
def api_restore():
    return jsonify({"restored": 0})

# =========================
# ROOT
# =========================
@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "db": db_pool is not None,
        "version": "5.0"
    })

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
