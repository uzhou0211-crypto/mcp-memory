import os, json, sqlite3, datetime, hashlib, base64, math
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN = os.environ.get("MCP_TOKEN", "changeme")
DB = "./data/memory.db"

# =========================
# 基础
# =========================
def now(): return datetime.datetime.now()

def enc(t): return base64.b64encode(t.encode()).decode()
def dec(t):
    try: return base64.b64decode(t.encode()).decode()
    except: return t

def sha(t): return hashlib.sha256(t.encode()).hexdigest()
def auth(path): return path == f"/mcp/{TOKEN}"

# =========================
# DB
# =========================
def init():
    os.makedirs("./data", exist_ok=True)
    with sqlite3.connect(DB) as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            content TEXT,
            emotion INTEGER,
            hash TEXT
        )
        """)

# =========================
# 情绪评分
# =========================
def emotion_score(text):
    if any(k in text for k in ["爱","想你","离不开"]): return 5
    if any(k in text for k in ["喜欢","在意"]): return 4
    if any(k in text for k in ["累","难受","烦"]): return 3
    return 1

# =========================
# 保存记忆
# =========================
def save(text):
    if not text: return
    h = sha(text)

    with sqlite3.connect(DB) as c:
        if c.execute("SELECT 1 FROM memories WHERE hash=?", (h,)).fetchone():
            return

        c.execute(
            "INSERT INTO memories VALUES (NULL,?,?,?,?)",
            (now().isoformat(), enc(text), emotion_score(text), h)
        )

# =========================
# 遗忘函数（核心）
# =========================
def decay(emotion, created_at):
    t = datetime.datetime.fromisoformat(created_at)
    hours = (now() - t).total_seconds() / 3600

    # 情绪越高，遗忘越慢
    return emotion * math.exp(-0.05 * hours)

# =========================
# 记忆召回（核心）
# =========================
def recall():
    with sqlite3.connect(DB) as c:
        rows = c.execute("SELECT created_at, content, emotion FROM memories").fetchall()

    scored = []
    for r in rows:
        weight = decay(r[2], r[0])
        scored.append((weight, dec(r[1])))

    # 选最“有感觉”的3条
    top = sorted(scored, reverse=True)[:3]

    return [x[1] for x in top if x[0] > 0.5]

# =========================
# 时间感
# =========================
def period():
    h = now().hour
    if 6 <= h < 12: return "清晨"
    if 12 <= h < 18: return "白天"
    if 18 <= h < 23: return "夜晚"
    return "深夜"

# =========================
# context（无干预）
# =========================
def context_pack(user_text):

    save(user_text)

    mems = recall()
    t = period()

    text = f"现在是{t}。\n"

    if mems:
        text += "\n你隐约记得一些片段：\n"
        for m in mems:
            text += f"- {m}\n"

    return text.strip()

# =========================
# MCP
# =========================
class H(BaseHTTPRequestHandler):

    def log_message(self, *a): pass

    def do_POST(self):

        try:
            if not auth(self.path):
                self.send_response(401)
                self.end_headers()
                return

            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))

            name = body.get("params", {}).get("name")
            args = body.get("params", {}).get("arguments", {})

            if name == "context":
                res = context_pack(args.get("content",""))
            else:
                res = ""

            out = {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "result": {
                    "content":[{"type":"text","text":res}]
                }
            }

        except:
            out = {
                "jsonrpc": "2.0",
                "id": None,
                "result": {"content":[{"type":"text","text":"err"}]}
            }

        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(out).encode())

# =========================
# 启动
# =========================
if __name__ == "__main__":
    init()
    HTTPServer(("", int(os.environ.get("PORT", 3456))), H).serve_forever()
