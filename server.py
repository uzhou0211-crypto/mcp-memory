import os, json, sqlite3, datetime, threading, time
from flask import Flask, request, jsonify, send_from_directory
from cryptography.fernet import Fernet

app = Flask(__name__)

DB = "memory.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ================= SECRET KEY =================
KEY_FILE = "secret.key"

def load_key():
    if os.path.exists(KEY_FILE):
        return open(KEY_FILE,"rb").read()
    key = Fernet.generate_key()
    open(KEY_FILE,"wb").write(key)
    return key

FERNET = Fernet(load_key())

# ================= STATE =================
STATE = {
    "mood":0.5,
    "energy":0.5,
    "summary":"等待生成",
    "last_thought":""
}

# ================= DB =================
def init():
    conn=sqlite3.connect(DB)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS memories(
        id INTEGER PRIMARY KEY,
        time TEXT,
        content TEXT
    )
    """)
    conn.commit()
    conn.close()

init()

# ================= MEMORY =================
def save_memory(text):
    conn=sqlite3.connect(DB)
    conn.execute(
        "INSERT INTO memories(time,content) VALUES (?,?)",
        (datetime.datetime.now().isoformat(), text)
    )
    conn.commit()
    conn.close()

def load_memory():
    conn=sqlite3.connect(DB)
    rows=conn.execute("SELECT * FROM memories").fetchall()
    conn.close()
    return [{"time":r[1],"content":r[2]} for r in rows]

# ================= ANALYSIS =================
def analyze(mem):
    mood = 0.5
    for m in mem:
        if any(k in m["content"] for k in ["开心","好","爽"]):
            mood += 0.01
        if any(k in m["content"] for k in ["烦","累","压力"]):
            mood -= 0.01

    return max(0,min(1,mood))

# ================= AUTO THINK =================
def generate_summary(mem):
    if not mem:
        return "暂无记忆"

    last = mem[-5:]
    return "最近记忆: " + " | ".join([x["content"] for x in last])

# ================= BACKGROUND ENGINE =================
def loop():
    while True:
        mem = load_memory()

        STATE["mood"] = analyze(mem)
        STATE["summary"] = generate_summary(mem)

        if STATE["mood"] < 0.3:
            STATE["last_thought"] = "岛屿注意到你的状态偏低"
        elif STATE["mood"] > 0.7:
            STATE["last_thought"] = "岛屿检测到你的状态上升"
        else:
            STATE["last_thought"] = "岛屿正在持续记录你"

        time.sleep(5)

threading.Thread(target=loop,daemon=True).start()

# ================= CHAT =================
@app.route("/api/chat",methods=["POST"])
def chat():
    msg=request.json.get("message","")

    save_memory(msg)

    return jsonify({
        "reply":"已记录并更新岛屿状态",
        "state":STATE
    })

# ================= STATE =================
@app.route("/api/state")
def state():
    return jsonify(STATE)

# ================= UPLOAD ENCRYPT =================
@app.route("/upload",methods=["POST"])
def upload():
    f=request.files.get("file")

    if not f:
        return jsonify({"error":"no file"}),400

    data=f.read()

    encrypted = FERNET.encrypt(data)

    name=datetime.datetime.now().strftime("%Y%m%d_%H%M%S_")+f.filename
    path=os.path.join(UPLOAD_DIR,name)

    with open(path,"wb") as w:
        w.write(encrypted)

    return jsonify({"status":"encrypted_uploaded","file":name})

# ================= FILE LIST =================
@app.route("/files")
def files():
    return jsonify(os.listdir(UPLOAD_DIR))

# ================= DECRYPT FILE =================
@app.route("/file/<name>")
def get_file(name):
    path=os.path.join(UPLOAD_DIR,name)

    if not os.path.exists(path):
        return "not found"

    data=open(path,"rb").read()
    try:
        decrypted = FERNET.decrypt(data)
        return decrypted.decode(errors="ignore")
    except:
        return "decrypt failed"

# ================= RUN =================
if __name__=="__main__":
    app.run(host="0.0.0.0",port=3000)
