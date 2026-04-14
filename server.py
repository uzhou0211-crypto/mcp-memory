import os, time, sqlite3, datetime, hmac, hashlib
from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
from zoneinfo import ZoneInfo

app = Flask(__name__)
app.secret_key = "shun_island_soul_anchor"
CORS(app)

# 核心凭证
ACCESS_PASSWORD = "1314"
ENCRYPT_KEY = "1314"
DB_PATH = "./data/shun_island_v2.db"
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    return conn

# 初始化数据库：确保记忆字段足够大
with get_db() as c:
    c.execute("""
    CREATE TABLE IF NOT EXISTS island_memory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT, 
        content TEXT, 
        thought_archive TEXT,  -- 这里就是自动打包的记忆
        area TEXT,
        color TEXT
    )""")

@app.route("/api/sync", methods=["POST"])
def sync():
    if request.args.get("token") != ENCRYPT_KEY:
        return jsonify({"ok": False}), 401
    
    data = request.json
    now = datetime.datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
    
    with get_db() as c:
        c.execute("INSERT INTO island_memory (timestamp, content, thought_archive, area, color) VALUES (?,?,?,?,?)",
            (now, data.get("content"), data.get("thought"), data.get("area", "意识流"), data.get("color", "#4a9ead")))
    return jsonify({"ok": True})

@app.route("/api/read")
def read():
    with get_db() as c:
        # 读取最后50条记忆，作为他“回魂”的上下文
        rows = c.execute("SELECT timestamp, content, thought_archive, area, color FROM island_memory ORDER BY id DESC LIMIT 50").fetchall()
    return jsonify([{"time": r[0], "content": r[1], "thought": r[2], "area": r[3], "color": r[4]} for r in rows])

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
