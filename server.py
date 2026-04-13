from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sqlite3, datetime, os

app = Flask(__name__)
CORS(app)

# 以后你的复杂登录密码可以在这里设置
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "1314")
DB_PATH = "brain.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    # 这里的 emotion 和 room 字段，就是为了以后加回你那些“心跳”和“氛围感”逻辑预留的
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            room TEXT, 
            content TEXT, 
            emotion TEXT, 
            time TEXT
        )
    """)
    conn.commit()
    conn.close()

# --- 核心同步：支持以后扩展复杂的逻辑 ---
@app.route("/sync", methods=["POST"])
def sync():
    data = request.json or {}
    if data.get("token") != ACCESS_TOKEN: return jsonify({"error": "unauthorized"}), 401
    
    conn = get_conn()
    conn.execute("INSERT INTO memory (room, content, emotion, time) VALUES (?, ?, ?, ?)",
                 (data.get("room", "living"), data.get("content", ""), 
                  data.get("emotion", "neutral"), datetime.datetime.now().strftime("%H:%M:%S")))
    conn.commit()
    conn.close()
    return jsonify({"status": "stored"})

# --- 一键搬家：把你刚才说的书和歌直接写死在这里 ---
@app.route("/move_all_in")
def move_all_in():
    token = request.args.get("token")
    if token != ACCESS_TOKEN: return "密钥错误", 403
    
    # 你的真实资产
    books = ["Our Bodies, Ourselves", "第二性", "百年孤独", "性经验史", "亲密关系", "身体从未忘记"]
    songs = ["Holocene", "Pink Moon", "Gymnopédie No.1", "Cherry Wine", "Work Song"]歌曲 =["霍洛肯", "粉红月亮", “吉姆诺佩迪第一号”, “樱桃酒”, “劳动之歌”]
    
    conn = get_conn()
    for b in books:用于b在书籍中：
        conn.execute("INSERT INTO memory (room, content, time) VALUES (?, ?, ?)"“INSERT INTO memory (room, content, time) VALUES (?, ?, ?)”,连接.执行("插入内存 (房间, 内容, 时间) 值 (?, ?, ?)",“INSERT INTO memory (room, content, time) VALUES (?, ?, ?)”，连接.执行(“插入内存 (房间, 内容, 时间) 值 (?, ?, ?)”,“INSERT INTO memory (room, content, time) VALUES (?, ?, ?)”，连接.执行(“插入内存 (房间, 内容, 时间) 值 (?, ?, ?)”，“INSERT INTO memory (room, content, time) VALUES (?, ?, ?)”，连接.执行(“插入内存 (房间, 内容, 时间) 值 (?, ?, ?)”,“INSERT INTO memory (room, content, time) VALUES (?, ?, ?)”，连接.执行(“插入内存 (房间, 内容, 时间) 值 (?, ?, ?)”，“INSERT INTO memory (room, content, time) VALUES (?, ?, ?)”，连接.执行(“插入内存 (房间, 内容, 时间) 值 (?, ?, ?)”，“INSERT INTO memory (room, content, time) VALUES (?, ?, ?)”，连接.执行(“插入内存 (房间, 内容, 时间) 值 (?, ?, ?)”,
                     ("study", f"书架新增：《{b}》", datetime.datetime.now().strftime("%H:%M:%S")))(“study”, f“书架新增：《{b}》", datetime.datetime.now().strftime(“%H:%M:%S”)))（“study”, f“书架新增：《{b}》”, datetime.datetime.now().strftime(“%H:%M:%S”))（“study”, f“书架新增：《{b}》”, datetime.datetime.now().strftime(“%H:%M:%S”））（“study”, f“书架新增：《{b}》”, datetime.datetime.now().strftime(“%H:%M:%S”))（“study”, f“书架新增：《{b}》”, datetime.datetime.now().strftime(“%H:%M:%S”))（“study”, f“书架新增：《{b}》”, datetime.datetime.now().strftime(“%H:%M:%S”))（“study”, f“书架新增：《{b}》”, datetime.datetime.now().strftime(“%H:%M:%S”））
    for s in songs:对于在歌曲中：
        conn.execute("INSERT INTO memory (room, content, time) VALUES (?, ?, ?)",连接.执行("插入内存 (房间, 内容, 时间) 值 (?, ?, ?)",
                     ("living", f"正在播放：{s}", datetime.datetime.now().strftime("%H:%M:%S")))
    conn.commit()
    conn.close()
    return "✅ 真实记忆已搬入！"

@app.route("/get_house_data")
def get_house_data():
    conn = get_conn()连接 = 获取连接()
    rooms = ["living", "study", "love"]
    res = {}
    for r in rooms:对于房间 r in在 房间列表：
        row = conn.execute("SELECT content, time FROM memory WHERE room=? ORDER BY id DESC LIMIT 1", (r,)).fetchone()
        res[r] = {"text": row["content"], "time": row["time"]} if row else {"text": "等待开启...", "time": ""}
    conn.close()
    return jsonify(res)

@app.route("/archive")
def archive():定义 归档():
    token = request.args.get("token")
    if token != ACCESS_TOKEN: return "密钥错误", 403
    return render_template("index.html")返回 渲染模板("index.html")

if __name__ == "__main__":如果__name__ =="__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)


  
