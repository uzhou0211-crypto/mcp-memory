import os
import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
CORS(app)

# ─────────────────────────────
# DATABASE
# ─────────────────────────────
DB_URL = os.environ.get("DATABASE_URL", "")
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://")

db_pool = psycopg2.pool.ThreadedConnectionPool(
    minconn=1,
    maxconn=10,
    dsn=DB_URL
)

def get_conn():
    return db_pool.getconn()

def put_conn(conn):
    db_pool.putconn(conn)

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id SERIAL PRIMARY KEY,
            time TIMESTAMPTZ DEFAULT NOW(),
            area TEXT,
            content TEXT,
            tags TEXT DEFAULT ''
        )
    """)
    conn.commit()
    put_conn(conn)

init_db()

# ─────────────────────────────
# STATE
# ─────────────────────────────
STATE = {
    "mood": 0.5,
    "energy": 0.5,
    "last_thought": "启动完成"
}

# ─────────────────────────────
# CORE FUNCTIONS (5个功能)
# ─────────────────────────────
def save_memory(content, area="法典", tags=""):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO memories(area, content, tags) VALUES (%s,%s,%s)",
        (area, content, tags)
    )
    conn.commit()
    put_conn(conn)
    return True


def read_memory(limit=50, area=None):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    if area:
        cur.execute("SELECT * FROM memories WHERE area=%s ORDER BY id DESC LIMIT %s", (area, limit))
    else:
        cur.execute("SELECT * FROM memories ORDER BY id DESC LIMIT %s", (limit,))

    rows = cur.fetchall()
    put_conn(conn)
    return rows


def delete_memory(mid):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM memories WHERE id=%s", (mid,))
    conn.commit()
    put_conn(conn)
    return True


def get_state():
    return STATE


def get_stats():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM memories")
    count = cur.fetchone()[0]
    put_conn(conn)
    return {"count": count}

# ─────────────────────────────
# BASIC API（前端用）
# ─────────────────────────────
@app.route("/")
def home():
    return jsonify({"status": "running", "db": True, "version": "6.0"})

@app.route("/api/save", methods=["POST"])
def api_save():
    data = request.get_json()
    save_memory(data.get("content",""), data.get("area","法典"))
    return jsonify({"ok": True})

@app.route("/api/read")
def api_read():
    area = request.args.get("area")
    return jsonify(read_memory(area=area))

@app.route("/api/delete/<int:id>", methods=["DELETE"])
def api_delete(id):
    delete_memory(id)
    return jsonify({"ok": True})

@app.route("/api/state")
def api_state():
    return jsonify(get_state())

# ─────────────────────────────
# MCP（Claude 完整兼容版）
# ─────────────────────────────
@app.route("/mcp", methods=["POST","GET"])
def mcp():
    if request.method == "GET":
        return jsonify({"status": "ok", "version": "6.0-mcp"})

    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "no json"}), 400

    method = data.get("method")
    req_id = data.get("id")

    # 1. initialize
    if method == "initialize":
        return jsonify({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {}
            }
        })

    # 2. tools/list
    if method == "tools/list":
        return jsonify({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "save_memory",
                        "description": "保存记忆",
                        "inputSchema": {"type": "object"}
                    },
                    {
                        "name": "get_memories",
                        "description": "读取记忆",
                        "inputSchema": {"type": "object"}
                    },
                    {
                        "name": "delete_memory",
                        "description": "删除记忆",
                        "inputSchema": {"type": "object"}
                    },
                    {
                        "name": "get_state",
                        "description": "状态",
                        "inputSchema": {"type": "object"}
                    },
                    {
                        "name": "get_stats",
                        "description": "统计",
                        "inputSchema": {"type": "object"}
                    }
                ]
            }
        })

    # 3. tools/call
    if method == "tools/call":
        name = data["params"].get("name")
        args = data["params"].get("arguments", {})

        if name == "save_memory":
            save_memory(args.get("content",""))
            return jsonify({"jsonrpc":"2.0","id":req_id,"result":{"ok":True}})

        if name == "get_memories":
            return jsonify({"jsonrpc":"2.0","id":req_id,"result":read_memory()})

        if name == "delete_memory":
            delete_memory(args.get("id"))
            return jsonify({"jsonrpc":"2.0","id":req_id,"result":{"ok":True}})

        if name == "get_state":
            return jsonify({"jsonrpc":"2.0","id":req_id,"result":get_state()})

        if name == "get_stats":
            return jsonify({"jsonrpc":"2.0","id":req_id,"result":get_stats()})

    return jsonify({
        "jsonrpc":"2.0",
        "id": req_id,
        "error":"unknown method",
        "method_received": method
    })

# ─────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",3000)))
