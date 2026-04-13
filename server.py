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

        for r in rooms:  # 对于房间 r in 房间列表
            row = conn.execute("""
                SELECT content, time, emotion
                FROM memory
                WHERE room=?
                ORDER BY id DESC
                LIMIT 1
            """, (r,)).fetchone()

            if row:
                res[r] = {
                    "text": row["content"],
                    "time": row["time"],
                    "emotion": row["emotion"]
                }
            else:
                res[r] = {
                    "text": "Waiting for Xiao Shun...",
                    "time": "",
                    "emotion": "neutral"
                }

    return jsonify(res)


@app.route("/archive")
def archive():
    return render_template("index.html")


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)



  
