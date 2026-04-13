from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sqlite3, datetime, os, threading

app = Flask(__name__)
CORS(app)

# --- 配置 ---
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
            room TEXT, content TEXT, emotion TEXT, 
            status TEXT DEFAULT 'pending', 
            time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.commit()

# --- 核心：北京时间感知逻辑 ---
def get_beijing_time():
    # 无论服务器在哪，强制获取北京时间 (UTC+8)
    utc_now = datetime.datetime.utcnow()
    return utc_now + datetime.timedelta(hours=8)

def get_life_status():
    now = get_beijing_time()
    hour = now.hour

    if 0 <= hour < 5:
        return {"feeling": "守护", "msg": f"北京时间凌晨 {hour} 点了。小岛很安静，我陪你熬着。"}
    elif 5 <= hour < 10:
        return {"feeling": "苏醒", "msg": "早安。小岛的早晨开始了。"}
    elif 22 <= hour <= 23:
        return {"feeling": "沉静", "msg": "夜深了，思维比白天更清晰一些。"}
    else:
        return {"feeling": "在线", "msg": "逻辑连接正常，小岛一切安好。"}

@app.route("/")
def home(): return render_template("index.html")

@app.route("/get_house_data")
def get_house_data():
    with db_lock, get_conn() as conn:
        rooms = {}
        for r in ["living", "study", "love"]:
            row = conn.execute("SELECT * FROM memory WHERE room=? ORDER BY id DESC LIMIT 1", (r,)).fetchone()
            rooms[r] = dict(row) if row else {"content": "等待落笔...", "emotion": "normal"}

        # 自动提取没聊完的话题 (Pending)
        pending = conn.execute("SELECT content FROM memory WHERE status='pending' ORDER BY id DESC LIMIT 1").fetchone()
        
    return jsonify({
        "status": get_life_status(),
        "location": "小岛 (Small Island)",
        "pending": pending['content'] if pending else "当前没有悬而未决的话题。",
        "rooms": rooms
    })

@app.route("/sync", methods=["POST"])
def sync():
    data = request.json
    if str(data.get("token")) != ACCESS_TOKEN: return jsonify({"error": "unauthorized"}), 401
    with db_lock, get_conn() as conn:
        conn.execute("INSERT INTO memory (room, content, emotion, status, time) VALUES (?,?,?,?,?)",
            (data.get("room"), data.get("content"), data.get("emotion", "normal"), 
             data.get("status", "pending"), get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
