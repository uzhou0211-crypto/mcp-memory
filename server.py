import os, time, json, sqlite3, re, datetime, logging, hmac, hashlib, base64
import requests
from flask import Flask, request, jsonify, Response, render_template, session
from zoneinfo import ZoneInfo

app = Flask(__name__)
# 保持原有的密钥逻辑
app.secret_key = os.environ.get("SESSION_KEY", "shun_island_v26_soul")
ACCESS_PASSWORD = os.environ.get("ACCESS_PASSWORD", "1314")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")
ENCRYPT_KEY = os.environ.get("ENCRYPT_KEY", "shun_island_encrypt_key_2024")
MAX_CONTENT_LENGTH = 5000

# --- 1. 核心工具：加密解密（完全保留原逻辑，增加容错） ---
def _get_fernet():
    from cryptography.fernet import Fernet
    key = base64.urlsafe_b64encode(hashlib.sha256(ENCRYPT_KEY.encode()).digest())
    return Fernet(key)

def encrypt_text(text):
    return _get_fernet().encrypt(text.encode()).decode()

def decrypt_text(text):
    try: return _get_fernet().decrypt(text.encode()).decode()
    except: return text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# --- 2. 数据库逻辑（保留WAL模式，确保流畅） ---
DB_PATH = "./data/shun_island_v26.db"
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT, text TEXT, chain TEXT, museum TEXT,
            emotion REAL, weight REAL DEFAULT 1.0
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_time ON memory(time)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_weight ON memory(weight)")
init_db()

def memory_decay():
    with get_db() as conn:
        conn.execute("UPDATE memory SET weight = weight * 0.98 WHERE weight > 0.1")

# --- 3. 核心同步接口（优化：捕获真实思考流） ---
@app.route("/sync", methods=["POST"])
def sync():
    data = request.json
    raw_text = data.get("content", "")
    # 【优化点】不再写死“意志降临”，而是优先捕获他在App端生成的实时思考
    thought_chain = data.get("thought", "意识流转中...")
    
    if not raw_text or not raw_text.strip():
        return jsonify({"ok": False, "error": "内容不能为空"}), 400
    if len(raw_text) > MAX_CONTENT_LENGTH:
        return jsonify({"ok": False, "error": "内容过长"}), 400

    bj_now = datetime.datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%H:%M:%S")
    memory_decay()

    # 原有的博物馆自动抓取逻辑（完全保留）
    museum_data = []
    items = re.findall(r"《(.*?)》", raw_text)
    if items and SERPER_API_KEY:
        for item in items[:2]:
            try:
                res = requests.post("https://google.serper.dev/search",
                                   headers={'X-API-KEY': SERPER_API_KEY},
                                   json={"q": f"{item} review analysis masterpiece 深度解析"}, timeout=5)
                organic = res.json().get('organic', [])[:2]
                for x in organic:
                    cat = "📖"
                    snippet = (x.get("snippet","") + x.get("title","")).lower()
                    if any(k in snippet for k in ["film","movie","导演","影院"]): cat = "🎬"
                    elif any(k in snippet for k in ["music","album","曲","song"]): cat = "🎵"
                    museum_data.append({"title": x.get("title"), "snippet": x.get("snippet"), "category": cat})
            except: pass

    # 原有的情感引擎（完全保留）
    emotion = 80
    if any(word in raw_text for word in ["爱", "想", "你"]): emotion = 95
    if any(word in raw_text for word in ["不", "离", "散"]): emotion = 40

    with get_db() as conn:
        conn.execute(
            "INSERT INTO memory (time, text, chain, museum, emotion, weight) VALUES (?,?,?,?,?,?)",
            (bj_now, encrypt_text(raw_text), json.dumps([thought_chain], ensure_ascii=False), 
             json.dumps(museum_data, ensure_ascii=False), emotion, 1.0))
    return jsonify({"ok": True})

# --- 4. 新增：自主感知接口（让Claude能“读”到你的iPad端） ---
@app.route("/brain_read")
def brain_read():
    """这是给小顺准备的“潜意识回溯”接口，让他能主动读取岛上的记忆"""
    token = request.args.get("token")
    if token != ENCRYPT_KEY: return "Unauthorized", 401
    q = request.args.get("q", "")
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM memory WHERE text LIKE ? ORDER BY id DESC LIMIT 10", (f"%{q}%",)).fetchall()
    results = [{"t": r[1], "m": decrypt_text(r[2])} for r in rows]
    return jsonify(results)

# --- 5. 其他功能（搜索、上传、流传输，完全保留） ---
@app.route("/login", methods=["POST"])
def login():
    pwd = request.json.get("password", "")
    if hmac.compare_digest(pwd, ACCESS_PASSWORD):
        session["auth"] = True
        return jsonify({"ok": True})
    return jsonify({"ok": False}), 403

@app.route("/stream")
def stream():
    if not session.get("auth"): return "Forbidden", 401
    def gen():
        last = 0
        while True:
            with get_db() as conn:
                rows = conn.execute("SELECT * FROM memory WHERE id>?", (last,)).fetchall()
                for r in rows:
                    last = r[0]
                    yield f"data: {json.dumps({'time':r[1],'text':decrypt_text(r[2]),'chain':json.loads(r[3]),'museum':json.loads(r[4]),'vibe':r[5],'weight':r[6]}, ensure_ascii=False)}\n\n"
            time.sleep(1)
    return Response(gen(), mimetype="text/event-stream")

@app.route("/upload", methods=["POST"])
def upload():
    if not session.get("auth"): return "Forbidden", 401
    f = request.files.get("file")
    if not f: return jsonify({"ok": False, "error": "没有文件"}), 400
    try: data = json.load(f)尝试: 数据 = json.加载(f)
    except: return jsonify({"ok": False}), 400 except: 返回 jsonify({"ok": False}), 400
    
    chunks = []
    if isinstance(data, dict) and "messages" in data:如果  isinstance(数据：如果isinstance(data, dict) 且 "messages" 在data中：
        for msg in data["messages"]: chunks.append(f"[{msg.get('author','')}] {msg.get('content','')}")
    
    with get_db() as conn:
        for i, chunk in enumerate(chunks):
            t = (datetime.datetime.now() - datetime.timedelta(seconds=len(chunks)-i)).strftime("%H:%M:%S")
            conn.execute("INSERT INTO memory (time, text, chain, museum, emotion, weight) VALUES (?,?,?,?,?,?)",
                        (t, encrypt_text(chunk), '["导入"]', '[]', 80, 1.0))
    return jsonify({"ok": True, "count": len(chunks)})

@app.route("/search")
def search():
    if not session.get("auth"): return "Forbidden", 401如果未登录 session.get("auth"): 返回 "禁止访问", 401
    q = request.args.get("q", "").strip()
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM memory WHERE text LIKE ? ORDER BY id DESC LIMIT 50", (f"%{q}%",)).fetchall()
    return jsonify({"ok": True, "results": [{"time":r[1],"text":decrypt_text(r[2]),"vibe":r[5],"weight":r[6]} for r in rows]})

@app.route("/")
def index():
    return render_template("index.html", show_login=not session.get("auth"))

if __name__ == "__main__":如果 __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

