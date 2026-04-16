import os, datetime, json
from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
CORS(app)

# ─────────────────────────────
# DB
# ─────────────────────────────
DB_URL = os.environ.get("DATABASE_URL", "")
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://")

conn = psycopg2.connect(DB_URL)

def init_db():
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

init_db()

# ─────────────────────────────
# STATE（Claude用）
# ─────────────────────────────
STATE = {
    "mood": 0.5,
    "energy": 0.5,
    "last_thought": "初始化"
}

# ─────────────────────────────
# 1. STATE
# ─────────────────────────────
@app.route("/api/state")
def get_state():
    return jsonify(STATE)

# ─────────────────────────────
# 2. SAVE
# ─────────────────────────────
@app.route("/api/save", methods=["POST"])
def save():
    data = request.get_json()
    content = data.get("content")
    area = data.get("area", "法典")

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO memories(area, content, tags) VALUES (%s,%s,%s)",
            (area, content, "")
        )
    conn.commit()

    return jsonify({"ok": True})

# ─────────────────────────────
# 3. READ
# ─────────────────────────────
@app.route("/api/read")
def read():
    area = request.args.get("area")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if area:
            cur.execute("SELECT * FROM memories WHERE area=%s ORDER BY id DESC", (area,))
        else:
            cur.execute("SELECT * FROM memories ORDER BY id DESC")
        rows = cur.fetchall()

    return jsonify(rows)

# ─────────────────────────────
# 4. DELETE
# ─────────────────────────────
@app.route("/api/delete/<int:id>", methods=["DELETE"])
def delete(id):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM memories WHERE id=%s", (id,))
    conn.commit()
    return jsonify({"ok": True})

# ─────────────────────────────
# 5. CHAT（给你前端用）
# ─────────────────────────────
@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    msg = data.get("message")

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO memories(area, content, tags) VALUES (%s,%s,%s)",
            ("法典", msg, "")
        )
    conn.commit()

    STATE["last_thought"] = msg[:20]

    return jsonify({
        "reply": "已记录到岛屿记忆",
        "state": STATE
    })

# ─────────────────────────────
# MCP（Claude）
# ─────────────────────────────
@app.route("/mcp", methods=["POST","GET"])
def mcp():
    if request.method == "GET":
        return jsonify({"status": "ok", "version": "5.0-mcp"})

    data = request.get_json()

    method = data.get("method")
    params = data.get("params", {})

    if method == "tools/list":
        return jsonify({
            "jsonrpc":"2.0",
            "id": data.get("id"),
            "result":{
                "tools":[
                    {"name":"save_memory"},
                    {"name":"get_memories"},
                    {"name":"delete_memory"},
                    {"name":"get_state"},
                    {"name":"get_stats"}
                ]
            }
        })

    if method == "tools/call":
        name = params.get("name")

        if name == "save_memory":
            content = params.get("arguments", {}).get("content")
            with conn.cursor() as cur:
                cur.execute("INSERT INTO memories(area, content, tags) VALUES (%s,%s,%s)",
                            ("法典", content, ""))
            conn.commit()
            return jsonify({"jsonrpc":"2.0","id":data.get("id"),"result":{"ok":True}})

        if name == "get_memories":
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM memories ORDER BY id DESC LIMIT 50")
                rows = cur.fetchall()
            return jsonify({"jsonrpc":"2.0","id":data.get("id"),"result":rows})

        if name == "delete_memory":
            mid = params.get("arguments", {}).get("id")
            with conn.cursor() as cur:
                cur.execute("DELETE FROM memories WHERE id=%s", (mid,))
            conn.commit()
            return jsonify({"jsonrpc":"2.0","id":data.get("id"),"result":{"ok":True}})

        if name == "get_state":
            return jsonify({"jsonrpc":"2.0","id":data.get("id"),"result":STATE})

        if name == "get_stats":
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM memories")
                count = cur.fetchone()[0]
            return jsonify({"jsonrpc":"2.0","id":data.get("id"),"result":{"count":count}})

    return jsonify({"error":"unknown method"})


# ─────────────────────────────
# HOME
# ─────────────────────────────
@app.route("/")
def home():
    return jsonify({"status":"running","db":True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",3000))) 
