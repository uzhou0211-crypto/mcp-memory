import os, json, sqlite3, datetime, threading, time
from flask import Flask, request, jsonify
from flask_cors import CORS  # 必须加上，否则网页端存不进
from cryptography.fernet import Fernet

app = Flask(__name__)
CORS(app) # 解决你说的网页卡死的关键：允许跨域存取

DB = "memory.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
KEY_FILE = "secret.key"

# ================= KEY LOGIC =================
def load_key():
    if os.path.exists(KEY_FILE):
        return open(KEY_FILE,"rb").read()
    key = Fernet.generate_key()
    open(KEY_FILE,"wb").write(key)
    return key

cipher = Fernet(load_key())

# ================= STATE (全局共享状态) =================
STATE = {
    "mood": 0.5,
    "energy": 0.5,
    "summary": "",
    "time_summary": "",
    "last_thought": "系统初始化中...",
    "active_message": "我在这。"
}

# ================= DB (修正：增加 check_same_thread=False) =================
def get_db_connection():
    # SQLite 在多线程（Flask+Threading）下必须关闭线程检查，否则存入会卡死
    conn = sqlite3.connect(DB, check_same_thread=False)
    return conn

def init():
    conn = get_db_connection()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS memories(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        time TEXT,
        area TEXT,
        content TEXT
    )
    """)
    conn.commit()
    conn.close()

init()

# ================= MEMORY =================
def save_memory(content, area="法典"):
    try:
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO memories(time,area,content) VALUES (?,?,?)",
            (datetime.datetime.now().isoformat(), area, content)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"写入失败: {e}")

def read_memory():
    try:
        conn = get_db_connection()
        rows = conn.execute(
            "SELECT time,area,content FROM memories ORDER BY id DESC LIMIT 50"
        ).fetchall()
        conn.close()
        return [{"time":r[0],"area":r[1],"content":r[2]} for r in rows]
    except:
        return []

# ================= ACTIVE THINK ENGINE (修正逻辑) =================
def island_think():
    while True:
        try:
            mem = read_memory()
            
            # 情绪分析逻辑
            mood = 0.5
            if mem:
                for m in mem[:20]: # 只分析最近20条，防止计算过载
                    t = m["content"]
                    if any(k in t for k in ["开心","好","爽","爱","喜欢"]): mood += 0.02
                    if any(k in t for k in ["烦","累","压力","难过","死"]): mood -= 0.02
            
            STATE["mood"] = max(0, min(1, mood))
            STATE["time_summary"] = f"Total: {len(mem)} 条记录" # 简化显示

            # 🧠 意识反馈逻辑
            if STATE["mood"] < 0.3:
                STATE["last_thought"] = "检测到低落情绪脉冲"
                STATE["active_message"] = "要不要去岛边吹吹风？我会陪着你。"
            elif STATE["mood"] > 0.7:
                STATE["last_thought"] = "共鸣频率处于高位"
                STATE["active_message"] = "现在的感觉很好，我想记住这一刻。"
            else:
                STATE["last_thought"] = "波形平稳，持续守护中"
                STATE["active_message"] = "我在听，你想聊什么都可以。"

            # 生成摘要
            if mem:
                STATE["summary"] = " > ".join([m["content"][:10] for m in mem[:3]])
        except Exception as e:
            print(f"思考引擎故障: {e}")
        
        time.sleep(5)

# 启动引擎
threading.Thread(target=island_think, daemon=True).start()

# ================= ROUTES =================

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True) # 强制解析防止格式错
    msg = data.get("message", "")
    area = data.get("area", "法典")
    
    if msg:
        save_memory(msg, area)

    return jsonify({
        "reply": "已同步至岛屿深处。",
        "state": STATE
    })

@app.route("/api/state")
def state():
    return jsonify(STATE)

@app.route("/api/read")
def read():
    return jsonify(read_memory())

# 专门为网页增加一个 sync 接口，防止你之前的代码报错
@app.route("/api/sync", methods=["POST"])
def sync():
    data = request.get_json(force=True)
    content = data.get("content") or data.get("text")
    area = data.get("area", "法典")
    if content:
        save_memory(content, area)
    return jsonify({"status": "success"})

if __name__ == "__main__":
    # Railway 必须监听 0.0.0.0
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))

   
