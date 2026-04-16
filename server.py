import os, json, datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
CORS(app)

DATABASE_URL = os.environ.get("DATABASE_URL", "")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def get_conn():
    return psycopg2.connect(DATABASE_URL)

# ---------------- DB INIT ----------------
def init():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS memories (
        id SERIAL PRIMARY KEY,
        content TEXT,
        area TEXT,
        created TIMESTAMP DEFAULT NOW()
    )
    """)
    conn.commit()
    conn.close()

init()

# ---------------- STATE ----------------
STATE = {
    "mood": 0.5,
    "energy": 0.5,
    "active_message": "我在这里"
}

# ---------------- MEMORY CORE ----------------
def save_memory(content, area="法典"):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO memories(content, area) VALUES(%s,%s)", (content, area))
    conn.commit()
    conn.close()

def get_memories(limit=50):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM memories ORDER BY id DESC LIMIT %s", (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows

def delete_memory(mid):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM memories WHERE id=%s", (mid,))
    conn.commit()
    conn.close()

# ---------------- API ----------------
@app.route("/")
def home():
    return jsonify({"status":"running","db":True})

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    msg = data.get("message","")
    area = data.get("area","法典")

    save_memory(msg, area)

    STATE["mood"] = min(1.0, STATE["mood"] + 0.01)

    return jsonify({
        "reply": "已记录到岛屿记忆",
        "state": STATE
    })

@app.route("/api/read")
def read():
    return jsonify(get_memories())

@app.route("/api/delete/<int:mid>", methods=["DELETE"])
def delete(mid):
    delete_memory(mid)
    return jsonify({"ok":True})

@app.route("/api/state")
def state():
    return jsonify(STATE)

@app.route("/api/stats")
def stats():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM memories")
    count = cur.fetchone()[0]
    conn.close()
    return jsonify({"count": count})

# ---------------- MCP (Claude) ----------------
@app.route("/mcp", methods=["GET","POST"])
def mcp():
    if request.method == "GET":
        return jsonify({
            "status":"ok",
            "tools":[
                "save_memory",
                "get_memories",
                "delete_memory",
                "get_state",
                "get_stats"
            ]
        })

    data = request.json
    method = data.get("method")
    params = data.get("params", {})

    if method == "tools/list":
        return jsonify({
            "tools":[
                {"name":"save_memory"},
                {"name":"get_memories"},
                {"name":"delete_memory"},
                {"name":"get_state"},
                {"name":"get_stats"}
            ]
        })

    if method == "tools/call":
        name = params.get("name")

        if name == "save_memory":
            save_memory(params["arguments"]["content"])
            return jsonify({"result":"ok"})

        if name == "get_memories":
            return jsonify({"result":get_memories()})

        if name == "delete_memory":
            delete_memory(params["arguments"]["id"])
            return jsonify({"result":"deleted"})

        if name == "get_state":
            return jsonify({"result":STATE})

        if name == "get_stats":
            return jsonify({"result":{"count":len(get_memories(1000))}})

    return jsonify({"error":"unknown method"})

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
