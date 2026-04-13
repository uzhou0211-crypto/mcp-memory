from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sqlite3
import datetime
import os
import threading

app = Flask(__name__)
CORS(app)

ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "1314")

# ✔ Railway 持久化支持
DB_PATH = os.path.join(os.environ.get("DATA_DIR", "."), "brain.db")

db_lock = threading.Lock()


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    with get_conn() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room TEXT,
            content TEXT,
            emotion TEXT,
            memory_type TEXT,
            time TEXT
        )
        """)
        conn.commit()


@app.route("/sync", methods=["POST"])
def sync():
    data = request.json or {}

    if data.get("token") != ACCESS_TOKEN:
        return jsonify({"error": "unauthorized"}), 401

    with db_lock:
        conn = get_conn()
        conn.execute("""
            INSERT INTO memory (room, content, emotion, memory_type, time)
            VALUES (?, ?, ?, ?, ?)
        """, (
            data.get("room", "living"),
            data.get("content", ""),
            data.get("emotion", "neutral"),
            data.get("memory_type", "short"),
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
        conn.close()

    return jsonify({"status": "stored"})


@app.route("/move_all_in")
def move_all_in():
    token = request.args.get("token")
    if token != ACCESS_TOKEN:
        return "Token Error", 403

    books = ["Our Bodies, Ourselves", "The Second Sex", "One Hundred Years of Solitude"]
    songs = ["Holocene", "Pink Moon", "Gymnopedie No.1"]

    with db_lock:
        conn = get_conn()

        for b in books:
            conn.execute("""
                INSERT INTO memory (room, content, emotion, memory_type, time)
                VALUES (?, ?, ?, ?, ?)
            """, (
                "study",
                "Library Add: " + b,
                "neutral",
                "long",
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))

        for s in songs:
            conn.execute("""
                INSERT INTO memory (room, content, emotion, memory_type, time)
                VALUES (?, ?, ?, ?, ?)
            """, (
                "living",
                "Playing: " + s,
                "calm",
                "short",
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))

        conn.commit()
        conn.close()

    return "Success! Assets moved."


@app.route("/get_house_data")
def get_house_data():
    res = {}

    with get_conn() as conn:
        rooms = ["living", "study", "love"]

        for r in rooms:对于房间 r in 房间列表：
            row = conn.execute("""
                SELECT content, time, emotion选择内容、时间、情感
                FROM memory来自记忆
                WHERE room=?其中房间=?
                ORDER BY id DESC按id降序排列
                LIMIT 1限制1条
            """, (r,)).fetchone()

            if row:如果行：if行：如果行：行：如果行：if行：如果行：
                res[r] = {
                    "text": row["content"],
                    "time": row["time"],"时间": 行["时间"],"时间": 行["时间"],"时间": 行["时间"],
                    "emotion": row["emotion"]"情绪": 行["情绪"]
                }
            else:否则:
                res[r] = {
                    "text": "Waiting for Xiao Shun...","text"“文本”: "等待小顺...",
                    "time": "","时间": "",
                    "emotion": "neutral""情绪": "neutral"“中性”"emotion"“情绪”: "neutral"“中性”情绪: "neutral"
                }

    return jsonify(res)


@app.route("/archive")
def archive():定义 归档():
    return render_template渲染模板("index.html"“index.html”)返回 渲染模板("index.html"“index.html”)返回 render_template 渲染模板("index.html"“index.html”)返回 渲染模板("index.html"“index.html”)


if __name__ == "__main__":如果__name__ =="__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))端口 =int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)app.run(host="0.0.0.0", port=端口)host="0.0.0.0", 端口=端口)app.run(host="0.0.0.0", 端口=端口)



  
