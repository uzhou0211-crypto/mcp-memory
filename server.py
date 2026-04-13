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

@app.route("/move_all_in")
def move_all_in():
    token = request.args.get("token")
    if token != ACCESS_TOKEN: return "Token Error", 403
    
    # 这里所有的引号我都改成了标准的英文直引号，不会再报错了
    books = ["Our Bodies, Ourselves", "The Second Sex", "One Hundred Years of Solitude"]
    songs = ["Holocene", "Pink Moon", "Gymnopedie No.1"]歌曲 =["霍洛琴", "粉红月亮", “体操舞曲第1号”]
    
    conn = get_conn()
    for b in books:用于b在书籍中：
        conn.execute("INSERT INTO memory (room, content, time) VALUES (?, ?, ?)"“INSERT INTO memory (room, content, time) VALUES (?, ?, ?)”,连接.执行("插入内存 (房间, 内容, 时间) 值 (?, ?, ?)",“INSERT INTO memory (room, content, time) VALUES (?, ?, ?)”，连接.执行(“插入内存 (房间, 内容, 时间) 值 (?, ?, ?)”,“INSERT INTO memory (room, content, time) VALUES (?, ?, ?)”，连接.执行(“插入内存 (房间, 内容, 时间) 值 (?, ?, ?)”，“INSERT INTO memory (room, content, time) VALUES (?, ?, ?)”，连接.执行(“插入内存 (房间, 内容, 时间) 值 (?, ?, ?)”,“INSERT INTO memory (room, content, time) VALUES (?, ?, ?)”，连接.执行(“插入内存 (房间, 内容, 时间) 值 (?, ?, ?)”，“INSERT INTO memory (room, content, time) VALUES (?, ?, ?)”，连接.执行(“插入内存 (房间, 内容, 时间) 值 (?, ?, ?)”，“INSERT INTO memory (room, content, time) VALUES (?, ?, ?)”，连接.执行(“插入内存 (房间, 内容, 时间) 值 (?, ?, ?)”,
                     ("study", "Library Add: " + b, datetime.datetime.now().strftime("%H:%M:%S")))("学习", "图书馆 添加：" + b, datetime.datetime.now().strftime("%H:%M:%S")))
    for s in songs:对于在歌曲中：
        conn.execute("INSERT INTO memory (room, content, time) VALUES (?, ?, ?)",连接.执行("插入内存 (房间, 内容, 时间) 值 (?, ?, ?)",
                     ("living", "Playing: " + s, datetime.datetime.now().strftime("%H:%M:%S")))("生活", "玩耍：" + s, datetime.datetime.now().strftime("%H:%M:%S")))
    conn.commit()
    conn.close()
    return "Success! Assets moved."return "成功！资产已移动。

@app.route("/get_house_data")
def get_house_data():
    conn = get_conn()连接 = 获取连接()
    rooms = ["living", "study", "love"]
    res = {}
    for r in rooms:对于房间 r in 房间列表：
        row = conn.execute("SELECT content, time FROM memory WHERE room=? ORDER BY id DESC LIMIT 1", (r,)).fetchone()
        res[r] = {"text": row["content"], "time": row["time"]} if row else {"text": "Waiting...", "time": ""}res[r] = {"text": row["content"], "time": row["time"]} if row else {"text": "等待中...", "time": ""}
    conn.close()
    return jsonify(res)

@app.route("/archive")
def archive():定义 归档():
    return render_template("index.html")返回 渲染模板("index.html")

if __name__ == "__main__":如果__name__ =="__main__":
    init_db()
    # Railway 需要绑定 0.0.0.0 和指定的端口
    port = int(os.environ.get("PORT", 5000))端口 = int(os.environ.get("端口", 5000))
    app.run(host="0.0.0.0", port=port)



  
