"""
小顺的岛屿记忆库 v4.1（稳定修复版）
══════════════════════════════════════════════
修复内容：
- Railway PostgreSQL 连接失败 crash
- DATABASE_URL 兼容问题
- init_db 导致服务崩溃
- SSL / pool 初始化错误
══════════════════════════════════════════════
"""

import os, json, datetime, threading, time
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from cryptography.fernet import Fernet, InvalidToken
from functools import wraps

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# ═══════════════════════════════════════
# 加密
# ═══════════════════════════════════════
def load_cipher():
    key = os.environ.get("MEMORY_KEY", "").strip()
    if not key:
        key = Fernet.generate_key().decode()
        print("⚠️ 未设置 MEMORY_KEY，已生成临时 key：")
        print(key)
    try:
        return Fernet(key.encode())
    except Exception:
        new_key = Fernet.generate_key()
        return Fernet(new_key)

cipher = load_cipher()

def encrypt(text: str) -> str:
    return cipher.encrypt(text.encode()).decode()

def decrypt(token: str) -> str:
    try:
        return cipher.decrypt(token.encode()).decode()
    except Exception:
        return token

# ═══════════════════════════════════════
# API Token
# ═══════════════════════════════════════
API_TOKEN = os.environ.get("API_TOKEN", "").strip()

def require_token(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not API_TOKEN:
            return f(*args, **kwargs)
        if request.headers.get("X-Token") != API_TOKEN:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return wrapper

# ═══════════════════════════════════════
# PostgreSQL（修复版）
# ═══════════════════════════════════════
DB_URL = os.environ.get("DATABASE_URL", "")

if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

db_pool = None

def init_db_pool():
    global db_pool
    try:
        if not DB_URL:
            raise Exception("DATABASE_URL 未设置")

        db_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=DB_URL,
            sslmode="require"
        )

        print("✅ PostgreSQL 连接成功")

    except Exception as e:
        print(f"❌ PostgreSQL 初始化失败: {e}")
        db_pool = None

def get_conn():
    if db_pool is None:
        raise Exception("数据库未连接（pool为空）")
    return db_pool.getconn()

def put_conn(conn):
    if db_pool:
        db_pool.putconn(conn)

# ═══════════════════════════════════════
# DB init（不会再 crash）
# ═══════════════════════════════════════
def init_db():
    if db_pool is None:
        print("⚠️ 数据库未连接，跳过 init_db")
        return

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id SERIAL PRIMARY KEY,
                    time TIMESTAMPTZ DEFAULT NOW(),
                    area TEXT DEFAULT '法典',
                    content TEXT NOT NULL,
                    tags TEXT DEFAULT '',
                    encrypted BOOLEAN DEFAULT TRUE
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_area ON memories(area)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_time ON memories(time DESC)")

        conn.commit()
        print("✅ 数据库初始化完成")

    except Exception as e:
        print(f"❌ init_db失败: {e}")
        if conn:
            conn.rollback()

    finally:
        if conn:
            put_conn(conn)

# ═══════════════════════════════════════
# Safe startup（关键）
# ═══════════════════════════════════════
init_db_pool()
init_db()

# ═══════════════════════════════════════
# State
# ═══════════════════════════════════════
STATE = {
    "mood": 0.5,
    "energy": 0.5,
    "summary": "",
    "last_thought": "启动中",
    "active_message": "我在这。"
}

# ═══════════════════════════════════════
# Memory core
# ═══════════════════════════════════════
def save_memory(content, area="法典", tags=""):
    if db_pool is None:
        return False

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO memories(time, area, content, tags, encrypted) VALUES (%s,%s,%s,%s,%s)",
                (datetime.datetime.utcnow(), area, encrypt(content), tags, True)
            )
        conn.commit()
        return True
    except Exception as e:
        print("save失败:", e)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            put_conn(conn)

def read_memory(limit=50):
    if db_pool is None:
        return []

    conn = None
    try:
        conn = get_conn()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM memories ORDER BY time DESC LIMIT %s", (limit,))
            rows = cur.fetchall()

        result = []
        for r in rows:
            d = dict(r)
            d["content"] = decrypt(d["content"])
            result.append(d)

        return result

    except Exception as e:
        print("read失败:", e)
        return []

    finally:
        if conn:
            put_conn(conn)

# ═══════════════════════════════════════
# MCP（简化稳定版）
# ═══════════════════════════════════════
@app.route("/mcp", methods=["POST","GET"])
def mcp():
    if request.method == "GET":
        return jsonify({"status": "ok", "version": "4.1"})

    data = request.get_json(force=True, silent=True)

    if not data:
        return jsonify({"error": "invalid json"}), 400

    method = data.get("method")
    params = data.get("params", {})
    req_id = data.get("id")

    def ok(result):
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    if method == "tools/call":
        name = params.get("name")

        if name == "save_memory":
            ok_flag = save_memory(params.get("arguments", {}).get("content",""))
            return jsonify(ok({"text": "saved" if ok_flag else "failed"}))

        if name == "get_memories":
            mem = read_memory()
            return jsonify(ok(mem))

    return jsonify(ok({"status": "unknown"}))

# ═══════════════════════════════════════
# API
# ═══════════════════════════════════════
@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "db": db_pool is not None,
        "version": "4.1"
    })

@app.route("/api/save", methods=["POST"])
@require_token
def api_save():
    data = request.get_json(force=True)
    save_memory(data.get("content",""))
    return jsonify({"ok": True})

@app.route("/api/read")
@require_token
def api_read():
    return jsonify(read_memory())

# ═══════════════════════════════════════
# RUN
# ═══════════════════════════════════════
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
