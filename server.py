import os, json, datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
CORS(app)

# ======================
# DB
# ======================
DATABASE_URL = os.environ.get("DATABASE_URL", "")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

conn = None

def get_conn():
    global conn
    if conn is None:
        conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    c = get_conn()
    cur = c.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS memories (
        id SERIAL PRIMARY KEY,
        time TIMESTAMPTZ DEFAULT NOW(),
        area TEXT,
        content TEXT
    )
    """)
    c.commit()

init_db()

# ======================
# STATE
# ======================
STATE = {
    "mood": 0.5,
    "energy": 0.5,
    "active_message": "我在这",
    "last_thought": "启动完成"
}

# ======================
# MEMORY CORE
# ======================
def save_memory(content, area="法典"):
    c = get_conn()
    cur = c.cursor()
    cur.execute(
        "INSERT INTO memories(area, content) VALUES (%s,%s)",
        (area, content)
    )
    c.commit()

def read_memory(limit=50):
    c = get_conn()
    cur = c.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM memories ORDER BY id DESC LIMIT %s", (limit,))
    return cur.fetchall()

def delete_memory(mid):
    c = get_conn()
    cur = c.cursor()
    cur.execute("DELETE FROM memories WHERE id=%s", (mid,))
    c.commit()

# ======================
# API
# ======================
@app.route("/")
def home():
    return jsonify({"status": "running", "db": True, "version": "5.0"})

@app.route("/api/state")
def api_state():
    return jsonify(STATE)

@app.route("/api/save", methods=["POST"])
def api_save():
    data = request.get_json()
    save_memory(data.get("content",""), data.get("area","法典"))
    return jsonify({"ok": True})

@app.route("/api/read")
def api_read():
    return jsonify(read_memory())

@app.route("/api/delete/<int:mid>", methods=["DELETE"])
def api_delete(mid):
    delete_memory(mid)
    return jsonify({"ok": True})

@app.route("/api/upload_chunks", methods=["POST"])
def upload_chunks():
    data = request.get_json()
    chunks = data.get("chunks", [])
    area = data.get("area", "法典")

    saved = 0
    for c in chunks:
        save_memory(c, area)
        saved += 1

    return jsonify({"saved": saved})

# ======================
# MCP CORE（关键）
# ======================
@app.route("/mcp", methods=["GET", "POST"])
def mcp():
    if request.method == "GET":
        return jsonify({"status": "ok", "version": "5.0-mcp"})

    data = request.get_json(force=True)
    method = data.get("method")
    req_id = data.get("id")

    def resp(result):
        return jsonify({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result
        })

    # ---- tools list ----
    if method == "tools/list":
        return resp({
            "tools": [
                {"name": "save_memory"},
                {"name": "get_memories"},
                {"name": "delete_memory"},
                {"name": "get_state"},
                {"name": "get_stats"}
            ]
        })

    # ---- tools call ----
    if method == "tools/call":
        name = data.get("params", {}).get("name")
        args = data.get("params", {}).get("arguments", {})

        if name == "save_memory":
            save_memory(args.get("content",""), args.get("area","法典"))
            return resp({"ok": True})

        if name == "get_memories":
            return resp(read_memory())

        if name == "delete_memory":
            delete_memory(args.get("id"))
            return resp({"ok": True})

        if name == "get_state":
            return resp(STATE)

        if name == "get_stats":
            return resp({"count": len(read_memory(1000))})

    return resp({"error": "unknown method"})

# ======================
# RUN
# ======================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
       
