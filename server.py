
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sqlite3, datetime, os

app = Flask(__name__)
CORS(app)

ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "1314")
DB_PATH = "brain.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    conn.execute("CREATE TABLE IF NOT EXISTS memory (id INTEGER PRIMARY KEY AUTOINCREMENT, room TEXT, content TEXT, time TEXT)")
    conn.commit()
    conn.close()

# --- 正常的同步接口 ---
@app.route("/sync", methods=["POST"])
def sync():
    data = request.json or {}
    if data.get("token") != ACCESS_TOKEN: return jsonify({"error": "unauthorized"}), 401
    conn = get_conn()
    conn.execute("INSERT INTO memory (room, content, time) VALUES (?, ?, ?)",
                 (data.get("room", "living"), data.get("content", ""), 
                  datetime.datetime.now().strftime("%H:%M:%S")))
    conn.commit()
    conn.close()
    return jsonify({"status": "stored"})

# --- ⭐ 专为平板设计的“一键搬家”接口 ---
@app.route("/move_all_in")
def move_all_in():
    token = request.args.get("token")
    if token != ACCESS_TOKEN: return "密钥错误", 403
    
    books = ["Our Bodies, Ourselves", "第二性", "百年孤独", "性经验史", "亲密关系", "身体从未忘记"]
    songs = ["Holocene", "Pink Moon", "Gymnopédie No.1", "Cherry Wine", "Work Song"]
    
    conn = get_conn()
    for b in books:
        conn.execute("INSERT INTO memory (room, content, time) VALUES (?, ?, ?)",
                     ("study", f"书架新增：《{b}》", datetime.datetime.now().strftime("%H:%M:%S")))
    for s in songs:
        conn.execute("INSERT INTO memory (room, content, time) VALUES (?, ?, ?)",
                     ("living", f"正在播放：{s}", datetime.datetime.now().strftime("%H:%M:%S")))
    conn.commit()
    conn.close()
    return "✅ 资产已全部搬入新家！现在刷新 /archive 页面看看吧。"

@app.route("/get_house_data")
def get_house_data():
    conn = get_conn()
    rooms = ["living", "study", "love"]
    res = {}
    for r in rooms:
        row = conn.execute("SELECT content, time FROM memory WHERE room=? ORDER BY id DESC LIMIT 1", (r,)).fetchone()
        res[r] = {"text": row["content"], "time": row["time"]} if row else {"text": "等待开启...", "time": ""}
    conn.close()
    return jsonify(res)

@app.route("/archive")
def archive():
    token = request.args.get("token")
    if token != ACCESS_TOKEN: return "密钥错误", 403
    return render_template("index.html")

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
               
