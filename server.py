import os
import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool

app = Flask(__name__)
CORS(app)

# =========================
# DB SETUP
# =========================
DB_URL = os.environ.get("DATABASE_URL", "")

if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

db_pool = None

def init_db_pool():
    global db_pool
    try:
        if not DB_URL:
            raise Exception("DATABASE_URL not set")

        db_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=DB_URL,
            sslmode="require"
        )
        print("✅ DB connected")

    except Exception as e:
        print("❌ DB init failed:", e)
        db_pool = None


def get_conn():
    return db_pool.getconn()

def put_conn(conn):
    if db_pool:
        db_pool.putconn(conn)


# =========================
# INIT DB TABLE
# =========================
def init_table():
    if not db_pool:
        return

    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        conn.commit()
        print("✅ table ready")

    except Exception as e:
        print("❌ table init failed:", e)
        if conn:
            conn.rollback()

    finally:
        if conn:
            put_conn(conn)


# =========================
# MEMORY FUNCTIONS
# =========================
def save_memory(content):
    if not db_pool:
        return False

    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO memories(content) VALUES (%s)",
            (content,)
        )
        conn.commit()
        return True

    except Exception as e:
        print("save error:", e)
        if conn:
            conn.rollback()
        return False

    finally:
        if conn:
            put_conn(conn)


def read_memory(limit=20):
    if not db_pool:
        return []

    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT * FROM memories ORDER BY id DESC LIMIT %s",
            (limit,)
        )
        return cur.fetchall()

    except Exception as e:
        print("read error:", e)
        return []

    finally:
        if conn:
            put_conn(conn)


# =========================
# MCP TOOLS
# =========================
TOOLS = [
    {
        "name": "save_memory",
        "description": "Save a memory",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"}
            },
            "required": ["content"]
        }
    },
    {
        "name": "get_memories",
        "description": "Get memory list",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]


# =========================
# MCP ENDPOINT
# =========================
@app.route("/mcp", methods=["POST"])
def mcp():
    data = request.get_json(force=True)
    method = data.get("method")
    req_id = data.get("id")

    def ok(result):
        return jsonify({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result
        })

    # -------- initialize --------
    if method == "initialize":
        return ok({
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": "island-memory",
                "version": "1.0"
            },
            "capabilities": {
                "tools": {}
            }
        })

    # -------- tools/list --------
    if method == "tools/list":
        return ok({
            "tools": TOOLS
        })

    # -------- tools/call --------
    if method == "tools/call":
        params = data.get("params", {})
        name = params.get("name")
        args = params.get("arguments", {})

        if name == "save_memory":
            save_memory(args.get("content", ""))
            return ok({"content": "saved"})

        if name == "get_memories":
            return ok({"content": read_memory()})

        return ok({"error": "unknown tool"})

    return ok({"error": "unknown method"})


# =========================
# HEALTH CHECK
# =========================
@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "db": db_pool is not None
    })


# =========================
# STARTUP
# =========================
if __name__ == "__main__":
    init_db_pool()
    init_table()

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 3000))
    )
