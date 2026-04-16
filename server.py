import os, datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from cryptography.fernet import Fernet

import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
CORS(app)

# =========================
# STATE
# =========================
STATE = {
    "mood": 0.5,
    "energy": 0.5,
    "active_message": "系统启动中",
    "last_thought": ""
}

# =========================
# ENCRYPTION
# =========================
KEY = os.environ.get("MEMORY_KEY")
if not KEY:
    KEY = Fernet.generate_key().decode()

cipher = Fernet(KEY.encode())

def enc(t): return cipher.encrypt(t.encode()).decode()
def dec(t):
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

pool = None

def init_db():
    global pool
    try:
        pool = ThreadedConnectionPool(
            1, 10,
            dsn=DB_URL,
            sslmode="require"
        )
        print("✅ DB connected")

        conn = pool.getconn()
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
        pool.putconn(conn)

    except Exception as e:
        print("DB ERROR:", e)
        pool = None

init_db()

# =========================
# MEMORY CORE
# =========================
def save_memory(text, area="法典"):
    if not pool:
        return False
    conn = pool.getconn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO memories(area, content) VALUES (%s,%s)",
        (area, enc(text))
    )
    conn.commit()
    pool.putconn(conn)
    return True

def read_memory(limit=50):
    if not pool:
        return []
    conn = pool.getconn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM memories ORDER BY time DESC LIMIT %s", (limit,))
    rows = cur.fetchall()
    pool.putconn(conn)

    for r in rows:
        r["content"] = dec(r["content"])
    return rows

def delete_memory(mid):
    if not pool:
        return False
    conn = pool.getconn()
    cur = conn.cursor()
    cur.execute("DELETE FROM memories WHERE id=%s", (mid,))
    conn.commit()
    pool.putconn(conn)
    return True

# =========================
# MCP (Claude tools)
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
                "save_memory",
                "get_memories",
                "delete_memory",
                "get_state",
                "get_stats"
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

    return ok({"error": "unknown"})

# =========================
# WEB API（前端必须）
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
    STATE["active_message"] = "已收到"

    return jsonify({
        "reply": "已写入记忆岛屿",
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
        "db": pool is not None,
        "version": "5.0"
    })

# =========================
# START
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
