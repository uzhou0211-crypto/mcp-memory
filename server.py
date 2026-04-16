import os
import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2

app = Flask(__name__)
CORS(app)

# =========================
# DATABASE
# =========================
DATABASE_URL = os.environ.get("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL, sslmode="require")
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

# =========================
# STATE
# =========================
STATE = {
    "mood": 0.5,
    "energy": 0.5,
    "active_message": "我在岛屿中",
    "last_thought": "启动完成"
}

# =========================
# HOME
# =========================
@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "db": True,
        "version": "4.2"
    })

# =========================
# STATE API
# =========================
@app.route("/api/state")
def get_state():
    return jsonify(STATE)

# =========================
# CHAT API
# =========================
@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json() or {}
    message = data.get("message", "")
    area = data.get("area", "法典")

    cur.execute(
        "INSERT INTO memories(area, content) VALUES (%s, %s)",
        (area, message)
    )
    conn.commit()

    STATE["last_thought"] = message[:30]

    return jsonify({
        "reply": "已保存到记忆岛",
        "state": STATE
    })

# =========================
# READ MEMORIES
# =========================
@app.route("/api/read")
def read():
    limit = int(request.args.get("limit", 60))

    cur.execute(
        "SELECT * FROM memories ORDER BY id DESC LIMIT %s",
        (limit,)
    )
    rows = cur.fetchall()

    result = []
    for r in rows:
        result.append({
            "id": r[0],
            "time": str(r[1]),
            "area": r[2],
            "content": r[3]
        })

    return jsonify(result)

# =========================
# DELETE MEMORY
# =========================
@app.route("/api/delete/<int:mid>", methods=["DELETE"])
def delete(mid):
    cur.execute("DELETE FROM memories WHERE id=%s", (mid,))
    conn.commit()
    return jsonify({"ok": True})

# =========================
# UPLOAD CHUNKS
# =========================
@app.route("/api/upload_chunks", methods=["POST"])
def upload_chunks():
    data = request.get_json() or {}
    chunks = data.get("chunks", [])
    area = data.get("area", "法典")

    for c in chunks:
        cur.execute(
            "INSERT INTO memories(area, content) VALUES (%s, %s)",
            (area, c)
        )

    conn.commit()

    return jsonify({
        "saved": len(chunks)
    })

# =========================
# BACKUP
# =========================
@app.route("/api/backup")
def backup():
    cur.execute("SELECT * FROM memories")
    rows = cur.fetchall()

    data = []
    for r in rows:
        data.append({
            "id": r[0],
            "time": str(r[1]),
            "area": r[2],
            "content": r[3]
        })

    return jsonify(data)

# =========================
# RESTORE
# =========================
@app.route("/api/restore", methods=["POST"])
def restore():
    data = request.get_json() or []data = request.get_json() 或 []

    if not isinstance(data, list):如果 不是  isinstance(data, list):数据，列表):
        return返回 jsonify({"error"“错误”返回jsonify({"error"“错误”“错误”“错误”: "bad format"“格式错误”“格式错误”}), 400返回 jsonify({"error"“错误”“错误”: "格式错误"}), 400

    for item in data:
        cur.execute(
            "INSERT INTO memories(area, content) VALUES (%s, %s)",
            (item.get("area", "法典"), item.get("content", ""))
        )

    conn.commit()连接。提交()连接。提交()连接。提交()

    return返回 jsonify({"restored"“已恢复”: len(data)})数据)})返回jsonify({"restored"“已恢复”:len(data)})数据)})返回 jsonify({"恢复成功": len(数据)})

# =========================
# RUN# 运行
# =========================
if __name__ == "__main__":如果__name__ =="__main__":如果__name__ =="__main__":如果__name__ =="__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
