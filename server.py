import os, datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
CORS(app)

# =========================
# DATABASE
# =========================
DATABASE_URL = os.environ.get("DATABASE_URL", "")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def get_conn():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id SERIAL PRIMARY KEY,
                time TEXT,
                area TEXT,
                content TEXT
            )
        """)
        conn.commit()
        conn.close()
        print("DB ready")
    except Exception as e:
        print("DB init error:", e)

init_db()

# =========================
# STATE
# =========================
STATE = {
    "mood": 0.5,
    "energy": 0.5,
    "active_message": "岛屿已上线",
    "last_thought": ""
}

# =========================
# HELPERS
# =========================
def save_memory(content, area):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO memories(time, area, content) VALUES (%s,%s,%s)",
        (datetime.datetime.utcnow().isoformat(), area, content)
    )
    conn.commit()
    conn.close()

def read_memory(area=None, search=None):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT * FROM memories ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()

    if area:
        rows = [r for r in rows if r["area"] == area]
    if search:
        rows = [r for r in rows if search in r["content"]]

    return rows

# =========================
# WEB API
# =========================
@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "db": True,
        "version": "4.2"
    })

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    msg = data.get("message", "")
    area = data.get("area", "法典")

    save_memory(msg, area)

    STATE["mood"] = min(1.0, STATE["mood"] + 0.01)
    STATE["energy"] = max(0.1, STATE["energy"] - 0.01)
    STATE["last_thought"] = msg[:30]
    STATE["active_message"] = "我记住了你的话"

    return jsonify({
        "reply": "已存入岛屿记忆",
        "state": STATE
    })

@app.route("/api/read")
def api_read():
    area = request.args.get("area")
    search = request.args.get("search")
    mems = read_memory(area, search)
    return jsonify(mems)

@app.route("/api/state")
def api_state():
    return jsonify(STATE)

@app.route("/api/delete/<int:mid>", methods=["DELETE"])
def delete(mid):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM memories WHERE id=%s", (mid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# =========================
# MCP SERVER (Claude 用)
# =========================
@app.route("/mcp", methods=["GET", "POST"])
def mcp():
    if request.method == "GET":
        return jsonify({"status": "ok", "version": "mcp-2.0"})

    data = request.get_json()
    method = data.get("method")
    req_id = data.get("id")

    def reply(result):
        return jsonify({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result
        })

    # tools list
    if method == "tools/list":
        return reply({
            "tools": [
                {"name": "save_memory"},
                {"name": "get_memories"},
                {"name": "delete_memory"},
                {"name": "get_state"},
                {"name": "get_stats"}
            ]
        })

    # tool call
    if method == "tools/call":
        name = data["params"]["name"]
        args = data["params"].get("arguments", {})

        if name == "save_memory":
            save_memory(args.get("content", ""), "法典")
            return reply({"ok": True})

        if name == "get_memories":
            return reply(read_memory())

        if name == "delete_memory":
            mid = args.get("id")
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("DELETE FROM memories WHERE id=%s", (mid,))
            conn.commit()
            conn.close()
            return reply({"ok": True})

        if name == "get_state":
            return reply(STATE)

        if name == "get_stats":
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM memories")
            count = cur.fetchone()[0]
            conn.close()
            return reply({"count": count})

    return reply({"error": "unknown method"})

# =========================
# START
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
    
