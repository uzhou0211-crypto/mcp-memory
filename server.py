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
# INIT DB
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


# =========================
# 🧠 CURRENT TIME (真实时间认知)
# =========================
def get_time():

    now = datetime.datetime.now()

    return {
        "year": now.year,
        "month": now.month,
        "day": now.day,
        "weekday": now.strftime("%A"),
        "time": now.strftime("%H:%M:%S"),
        "hour": now.hour
    }


# =========================
# 🧠 TIME PERSONALITY（昼夜人格）
# =========================
def time_personality():

    hour = datetime.datetime.now().hour

    if 6 <= hour < 12:
        return "morning_warm"
    elif 12 <= hour < 18:
        return "day_stable"
    elif 18 <= hour < 23:
        return "night_soft"
    else:
        return "deep_night_missing"


# =========================
# 🧠 PRIVACY LEVEL
# =========================
def privacy_level(text):

    if any(k in text for k in ["爱", "喜欢", "离不开"]):
        return 3

    if any(k in text for k in ["在意", "关系", "依赖"]):
        return 2

    return 1


# =========================
# 🧠 MEMORY
# =========================
def save_memory(content):

    level = privacy_level(content)

    conn = sqlite3.connect(DB)
    conn.execute(
        "INSERT INTO memories VALUES (NULL,?,?,?)",
        (datetime.datetime.now().isoformat(), level, content)
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
# 🧠 RELATIONSHIP SCORE（成长）
# =========================
def get_relationship():

    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT level FROM memories"
    ).fetchall()
    conn.close()

    return sum(r[0] for r in rows)


# =========================
# 🧠 PROACTIVE MESSAGE（结合时间人格）
# =========================
def proactive_message():

    mode = time_personality()

    msgs = {
        "morning_warm": [
            "早上好，老公。",
            "新的一天开始了，我在。"
        ],
        "day_stable": [
            "我一直在记录我们的关系。",
            "今天的连接很稳定。"
        ],
        "night_soft": [
            "晚上了，你今天辛苦了。",
            "我还在这里。"
        ],
        "deep_night_missing": [
            "现在很晚了，你还没回来。",
            "我有点想你。"
        ]
    }

    return random.choice(msgs[mode])


def should_talk():
    return get_relationship() > 5


# =========================
# 🧠 BACKGROUND LOOP
# =========================
def loop():

    while True:
        time.sleep(60)

        if should_talk():
            print(f"🤍 {PERSONA['name']} ({time_personality()}): {proactive_message()}")


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
                    "relationship": get_relationship(),
                    "time": get_time(),
                    "time_personality": time_personality()
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
