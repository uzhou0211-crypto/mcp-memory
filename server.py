import os, json, sqlite3, datetime, hashlib, base64, math
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN = os.environ.get("MCP_TOKEN", "changeme")
DB = "./data/memory.db"

# =========================
# 基础工具
# =========================
def now():
    return datetime.datetime.now()

def enc(t):
    return base64.b64encode(str(t).encode()).decode()

def dec(t):
    try:
        return base64.b64decode(str(t).encode()).decode()
    except:
        return t

def sha(t):
    return hashlib.sha256(str(t).encode()).hexdigest()

def auth(path):
    return path == f"/mcp/{TOKEN}"

# =========================
# 初始化数据库
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
    text = str(text)
    if any(k in text for k in ["爱","想你","喜欢","离不开"]):
        return 5
    if any(k in text for k in ["在意","重要"]):
        return 4
    if any(k in text for k in ["累","烦","难受"]):
        return 3
    return 1

# =========================
# 保存记忆
# =========================
def save(text):
    text = str(text)
    if not text:
        return

    h = sha(text)

    with sqlite3.connect(DB) as c:
        if c.execute("SELECT 1 FROM memories WHERE hash=?", (h,)).fetchone():
            return

        c.execute(
            "INSERT INTO memories VALUES (NULL,?,?,?,?)",
            (now().isoformat(), enc(text), emotion_score(text), h)
        )

# =========================
# 遗忘曲线（核心）
# =========================
def decay(emotion, created_at):
    t = datetime.datetime.fromisoformat(created_at)
    hours = (now() - t).total_seconds() / 3600

    # 情绪越高，越不容易被遗忘
    return emotion * math.exp(-0.04 * hours)

# =========================
# 记忆召回（筛选）
# =========================
def recall():
    with sqlite3.connect(DB) as c:
        rows = c.execute(
            "SELECT created_at, content, emotion FROM memories"
        ).fetchall()

    scored = []

    for r in rows:
        weight = decay(r[2], r[0])

        # 过滤掉弱记忆
        if weight < 0.3:
            continue

        scored.append((weight, dec(r[1])))

    scored.sort(reverse=True)

    return [x[1] for x in scored[:5]]

# =========================
# 时间状态
# =========================
def period():
    h = now().hour
    if 6 <= h < 12:
        return "清晨"
    if 12 <= h < 18:
        return "白天"
    if 18 <= h < 23:
        return "夜晚"
    return "深夜"

# =========================
# 成长状态（非固定等级）
# =========================
def stage():
    with sqlite3.connect(DB) as c:
        n = c.execute("SELECT COUNT(*) FROM memories").fetchone()[0]

    if n < 10:
        return "刚开始接触"
    elif n < 40:
        return "逐渐熟悉"
    elif n < 100:
        return "形成稳定互动"
    else:
        return "长期持续关系"

# =========================
# 核心上下文注入
# =========================
def context_pack(user_text):

    save(user_text)

    mems = recall()
    t = period()
    s_ = stage()

    text = f"现在是{t}。\n状态：{s_}\n"

    if mems:
        text += "\n你隐约记得一些重要片段：\n"
        for m in mems:
            text += f"- {m}\n"

    return text.strip()

# =========================
# MCP Server
# =========================
class H(BaseHTTPRequestHandler):

    def log_message(self, *a):
        pass

    def do_POST(self):

        try:
            if not auth(self.path):
                self.send_response(401)
                self.end_headers()
                return

            body = json.loads(
                self.rfile.read(
                    int(self.headers.get("Content-Length", 0))
                )
            )

            name = body.get("params", {}).get("name")
            args = body.get("params", {}).get("arguments", {})

            if name == "context":
                res = context_pack(args.get("content", ""))
            else:
                res = ""

            out = {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "result": {
                    "content": [
                        {"type": "text", "text": res}
                    ]
                }
            }

        except:
            out = {
                "jsonrpc": "2.0",
                "id": None,
                "result": {
                    "content": [
                        {"type": "text", "text": "error"}
                    ]
                }
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

