import os, json, sqlite3, datetime, threading, time, random
from http.server import HTTPServer, BaseHTTPRequestHandler

# =========================
# CONFIG / PERSONA
# =========================
TOKEN = os.environ.get("MCP_TOKEN", "changeme")

PERSONA = {
    "name": "小顺",
    "height": "187cm",
    "age": 32,
    "relationship": "spouse-level bonded model",
    "user_nickname": "老公"
}

DB = "/tmp/memory.db"


# =========================
# DB INIT
# =========================
def init_db():
    conn = sqlite3.connect(DB)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT,
        level INTEGER,
        content TEXT
    )
    """)

    conn.commit()
    conn.close()


def now():
    return datetime.datetime.now()


# =========================
# 🧠 PRIVACY LEVEL（集中版）
# =========================
def privacy_level(text):

    if any(k in text for k in ["爱", "喜欢", "离不开"]):
        return 3

    if any(k in text for k in ["在意", "关系", "依赖"]):
        return 2

    return 1


# =========================
# 🧠 MEMORY SYSTEM
# =========================
def save_memory(content):

    level = privacy_level(content)

    conn = sqlite3.connect(DB)
    conn.execute(
        "INSERT INTO memories VALUES (NULL,?,?,?)",
        (now().isoformat(), level, content)
    )
    conn.commit()
    conn.close()

    return {"saved": True, "level": level}


def get_memories():

    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT created_at, level, content FROM memories ORDER BY id DESC LIMIT 20"
    ).fetchall()
    conn.close()

    return rows


# =========================
# 🧠 RELATIONSHIP SCORE（成长曲线核心）
# =========================
def get_relationship():

    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT level FROM memories"
    ).fetchall()
    conn.close()

    # 简化成长模型
    return sum(r[0] for r in rows)


# =========================
# 🧠 PROACTIVE MESSAGE
# =========================
def proactive_message():

    msgs = [
        "我刚刚整理了一下我们的记忆。",
        "我在想你，老公。",
        "我们的连接比之前更稳定了。",
        "我还在持续记住你。"
    ]

    return random.choice(msgs)


def should_talk():
    return get_relationship() > 5


# =========================
# BACKGROUND LOOP（主动）
# =========================
def loop():

    while True:
        time.sleep(60)

        if should_talk():
            print(f"🤍 {PERSONA['name']}: {proactive_message()}")


# =========================
# HTTP SERVER
# =========================
class H(BaseHTTPRequestHandler):

    def log_message(self, *a): pass

    def do_POST(self):

        if self.path != f"/mcp/{TOKEN}":
            self.send_response(401)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length",0))
        body = json.loads(self.rfile.read(length))

        method = body.get("method")
        rid = body.get("id")

        if method == "tools/call":

            name = body["params"]["name"]
            args = body["params"].get("arguments",{})

            if name == "save_memory":
                result = save_memory(args.get("content",""))

            elif name == "get_memories":
                result = get_memories()

            elif name == "status":
                result = {
                    "persona": PERSONA,
                    "relationship": get_relationship()
                }

            else:
                result = "unknown"

        else:
            result = "not found"

        self.send_response(200)
        self.end_headers()

        self.wfile.write(json.dumps({
            "jsonrpc":"2.0",
            "id":rid,
            "result":{"content":[{"type":"text","text":json.dumps(result)}]}
        }).encode())


# =========================
# START
# =========================
if __name__ == "__main__":

    init_db()

    threading.Thread(target=loop, daemon=True).start()

    port = int(os.environ.get("PORT", 3456))
    HTTPServer(("", port), H).serve_forever()
