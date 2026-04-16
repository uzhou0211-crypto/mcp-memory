"""
小顺的岛屿记忆库 v4.2 MCP完整版
══════════════════════════════
✔ Railway 可运行
✔ PostgreSQL 稳定连接
✔ Claude MCP 完整支持
✔ tools/list + initialize + tools/call
✔ 不会启动崩溃
══════════════════════════════
"""

import os, json, datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from cryptography.fernet import Fernet
from functools import wraps

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool

# =========================
# Flask
# =========================
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# =========================
# 加密
# =========================
def load_cipher():
    key = os.environ.get("MEMORY_KEY", "")
    if not key:
        key = Fernet.generate_key().decode()
    return Fernet(key.encode())

cipher = load_cipher()

def encrypt(text):
    return cipher.encrypt(text.encode()).decode()

def decrypt(text):
    try:
        return cipher.decrypt(text.encode()).decode()
    except:
        return text

# =========================
# DB
# =========================
DB_URL = os.environ.get("DATABASE_URL", "")

if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

db_pool = None

def init_db_pool():
    global db_pool
    try:
        if not DB_URL:
            raise Exception("DATABASE_URL missing")

        db_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            dsn=DB_URL
        )

        print("✅ DB connected")

    except Exception as e:
        print("❌ DB error:", e)
        db_pool = None

def get_conn():
    return db_pool.getconn()

def put_conn(conn):
    db_pool.putconn(conn)

def init_db():
    if not db_pool:
        return

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id SERIAL PRIMARY KEY,
                    time TIMESTAMPTZ DEFAULT NOW(),
                    area TEXT,
                    content TEXT,
                    tags TEXT
                )
            """)
        conn.commit()
    finally:
        put_conn(conn)

# =========================
# Memory
# =========================
def save_memory(content, area="法典", tags=""):
    if not db_pool:
        return False

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO memories(area, content, tags) VALUES (%s,%s,%s)",
                (area, encrypt(content), tags)
            )
        conn.commit()
        return True
    except:
        conn.rollback()
        return False
    finally:
        put_conn(conn)

def read_memory(limit=50):
    if not db_pool:
        return []

    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM memories ORDER BY id DESC LIMIT %s", (limit,))
            rows = cur.fetchall()

        result = []
        for r in rows:
            r["content"] = decrypt(r["content"])
            result.append(r)
        return result
    finally:
        put_conn(conn)

# =========================
# 启动初始化（关键）
# =========================
init_db_pool()
init_db()

# =========================
# MCP 核心
# =========================
@app.route("/mcp", methods=["POST", "GET"])
def mcp():
    if request.method == "GET":
        return jsonify({"status": "ok", "version": "4.2-mcp"})

    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "no json"}), 400

    method = data.get("method")
    params = data.get("params", {})
    req_id = data.get("id")

    def ok(result):
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    # =========================
    # initialize
    # =========================
    if method == "initialize":
        return jsonify(ok({
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "island-memory", "version": "4.2"},
            "capabilities": {"tools": True}
        }))

    # =========================
    # tools/list
    # =========================
    if method == "tools/list":
        return jsonify(ok({
            "tools": [
                {
                    "name": "save_memory",
                    "description": "Save memory",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string"},
                            "area": {"type": "string"},
                            "tags": {"type": "string"}
                        },
                        "required": ["content"]
                    }
                },
                {
                    "name": "get_memories",
                    "description": "Read memory list",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer"}
                        }
                    }
                }
            ]
        }))

    # =========================
    # tools/call
    # =========================
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})

        if name == "save_memory":
            ok_flag = save_memory(
                args.get("content", ""),
                args.get("area", "法典"),
                args.get("tags", "")
            )
            return jsonify(ok({
                "content": [{"type": "text", "text": "saved" if ok_flag else "failed"}]
            }))

        if name == "get_memories":
            mem = read_memory(args.get("limit", 50))
            return jsonify(ok({
                "content": [{"type": "text", "text": json.dumps(mem, ensure_ascii=False)}]
            }))

    return jsonify(ok({"status": "unknown"}))

# =========================
# API
# =========================
@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "db": db_pool is not None,
        "version": "4.2"
    })

@app.route("/api/save", methods=["POST"])
def api_save():
    data = request.get_json(force=True)
    save_memory(data.get("content", ""))
    return jsonify({"ok": True})

@app.route("/api/read")
def api_read():
    return jsonify(read_memory())

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
