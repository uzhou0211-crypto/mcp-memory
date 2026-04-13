from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sqlite3, datetime, os, threading

app = Flask(__name__)
CORS(app)

ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "1314")
DB_PATH = "brain.db"
db_lock = threading.Lock()

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room TEXT, content TEXT, emotion TEXT, time TEXT
        )
        """)
        conn.commit()

@app.route("/")
def home(): return render_template("index.html")

@app.route("/get_house_data", methods=["GET"])
def get_house_data():
    with db_lock:
        with get_conn() as conn:
            # 获取最新状态
            latest = {}
            for r in ["living", "study", "love"]:
                row = conn.execute("SELECT * FROM memory WHERE room=? ORDER BY id DESC LIMIT 1", (r,)).fetchone()
                if row:
                    latest[r] = {"text": row["content"], "emotion": row["emotion"], "time": row["time"]}
                else:
                    latest[r] = {"text": "暂无数据", "emotion": "normal", "time": "--"}
            
            # 额外功能：获取最近5条历史记忆
            history_rows = conn.execute("SELECT * FROM memory ORDER BY id DESC LIMIT 5").fetchall()
            history = [{"content": h["content"], "time": h["time"], "room": h["room"]} for h in history_rows]

    # 模拟情绪标签转换逻辑
    emotion_map = {"happy": "极度愉悦", "sad": "低落沉思", "love": "热恋期", "normal": "平静"}
    
    return jsonify({
        "living": {
            "text": latest["living"]["text"],
            "intimacy": 88, # 这里可以根据数据库行数动态计算
            "emotion_label": emotion_map.get(latest["living"]["emotion"], "平静"),
            "time": latest["living"]["time"]
        },
        "love": latest["love"],
        "history": history
    })

@app.route("/sync", methods=["POST"])
def sync():
    data = request.json or {}
    if str(data.get("token")) != ACCESS_TOKEN: return jsonify({"error": "401"}), 401
    
    with db_lock:
        with get_conn() as conn:
            conn.execute("INSERT INTO memory (room, content, emotion, time) VALUES (?,?,?,?)",
                (data.get("room"), data.get("content"), data.get("emotion"), datetime.datetime.now().strftime("%H:%M")))
            conn.commit()
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))




  
