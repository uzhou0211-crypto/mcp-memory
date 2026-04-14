import os, sqlite3, datetime, hmac
from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
from zoneinfo import ZoneInfo

app = Flask(__name__)
app.secret_key = "shun_island_v8_stable"
CORS(app)

ACCESS_PASSWORD = "1314"
ENCRYPT_KEY = "1314"
DB_PATH = "./data/shun_island_final.db"

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    return conn

# 初始化：分区结构完全不动，确保包含 thought_archive
with get_db() as c:
    c.execute("""CREATE TABLE IF NOT EXISTS island_v8 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT, 
        content TEXT, 
        thought_archive TEXT,  -- 自动打包功能：存放原始思维流转
        area TEXT,           -- 保持：实验室/图书馆/唱片行/信箱/上传区
        color_code TEXT
    )""")

@app.route("/api/sync", methods=["POST"])
def sync():
    token = request.args.get("token") or request.headers.get("X-Island-Token")
    if token != ENCRYPT_KEY:
        return jsonify({"ok": False}), 401
    
    data = request.json
    beijing_now = datetime.datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
    
    with get_db() as c:
        c.execute("""INSERT INTO island_v8 (timestamp, content, thought_archive, area, color_code) 
                     VALUES (?,?,?,?,?)""",
            (beijing_now, data.get("content"), data.get("thought"), data.get("area"), data.get("color", "#4a9ead")))
    return jsonify({"ok": True, "time": beijing_now})

@app.route("/api/read")
def read():
    with get_db() as c:
        rows = c.execute("SELECT timestamp, content, thought_archive, area, color_code FROM island_v8 ORDER BY id DESC LIMIT 100").fetchall()
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

