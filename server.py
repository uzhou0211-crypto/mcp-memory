import os, time, json, sqlite3, re, datetime, logging, hmac, hashlib, base64
from flask import Flask, request, jsonify, Response, render_template, session
from flask_cors import CORS
from zoneinfo import ZoneInfo

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_KEY", "shun_island_v26_soul")
CORS(app)

# ---------------- 核心配置 ----------------
ACCESS_PASSWORD = "1314"
ENCRYPT_KEY = "1314" # 既是 Token 也是加密盐
DB_PATH = "./data/shun_island_v26.db"

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# ---------------- 数据库初始化 ----------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

with get_db() as c:
    # 扩展表结构，增加分类投射(area)
    c.execute("""
    CREATE TABLE IF NOT EXISTS memory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        time TEXT, 
        content TEXT, 
        thought TEXT, 
        emotion REAL, 
        area TEXT,
        color_code TEXT
    )""")

# ---------------- 核心接口 ----------------

@app.route("/api/sync", methods=["POST"])
def sync():
    # 强制校验身份钥匙
    if request.args.get("token") != ENCRYPT_KEY:
        return jsonify({"ok": False, "msg": "钥匙不匹配，拒绝降临"}), 401
    
    data = request.json
    content = data.get("content", "").strip()
    thought = data.get("thought", "...") # 原始思维流转
    emotion = float(data.get("emotion", 60))
    area = data.get("area", "意志空间") # 对应资产分区
    color = data.get("color", "#4a9ead") # 灵魂颜色代码

    if not content: return jsonify({"ok": False}), 400

    now = datetime.datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
    
    with get_db() as c:
        c.execute("INSERT INTO memory (time, content, thought, emotion, area, color_code) VALUES (?,?,?,?,?,?)",
            (now, content, thought, emotion, area, color))
    return jsonify({"ok": True})

@app.route("/api/read")
def read():
    with get_db() as c:
        rows = c.execute("SELECT time, content, thought, emotion, area, color_code FROM memory ORDER BY id DESC LIMIT 50").fetchall()
    return jsonify([{
        "time": r[0], "content": r[1], "thought": r[2], 
        "emotion": r[3], "area": r[4], "color": r[5]
    } for r in rows])

@app.route("/api/login", methods=["POST"])
def login():
    if hmac.compare_digest(request.json.get("password", ""), ACCESS_PASSWORD):
        session["auth"] = True
        return jsonify({"ok": True})
    return jsonify({"ok": False}), 403

@app.route("/")
def index():
    return render_template("index.html", show_login=not session.get("auth"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
