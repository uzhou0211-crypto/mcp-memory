import os, json, sqlite3, datetime, hashlib, base64
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

TOKEN = os.environ.get("MCP_TOKEN", "changeme")
DB = "/tmp/memory.db"

# =========================
# 基础工具
# =========================
def safe_str(t):
    return "" if t is None else str(t)

def encode(t):
    return base64.b64encode(safe_str(t).encode()).decode()

def decode(t):
    try:
        return base64.b64decode(safe_str(t).encode()).decode()
    except:
        return t

def sha(t):
    return hashlib.sha256(safe_str(t).encode()).hexdigest()

def auth_ok(path):
    return path == f"/mcp/{TOKEN}"

# =========================
# 数据库
# =========================
def connect():
    return sqlite3.connect(DB)

def init_db():
    with connect() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            level INTEGER,
            content TEXT,
            hash TEXT
        )
        """)

# =========================
# 时间
# =========================
def time_context():
    now = datetime.datetime.now()
    h = now.hour

    if 6 <= h < 12:
        return now, "morning"
    elif 12 <= h < 18:
        return now, "day"
    elif 18 <= h < 23:
        return now, "night"
    else:
        return now, "late_night"

# =========================
# 记忆系统
# =========================
def classify(text):
    if any(k in text for k in ["爱","想你","喜欢"]): return 3
    if any(k in text for k in ["陪","关系"]): return 2
    return 1

def save_memory(text):
    if not text: return
    h = sha(text)

    with connect() as conn:
        if conn.execute("SELECT 1 FROM memories WHERE hash=?", (h,)).fetchone():
            return

        conn.execute(
            "INSERT INTO memories VALUES (NULL,?,?,?,?)",
            (datetime.datetime.now().isoformat(), classify(text), encode(text), h)
        )

# =========================
# 关系阶段
# =========================
def relationship_stage():
    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]

    if count < 10: return "陌生"
    if count < 40: return "熟悉"
    if count < 100: return "依赖"
    return "绑定"

# =========================
# 记忆触发
# =========================
def recall():
    with connect() as conn:
        rows = conn.execute("""
            SELECT content FROM memories
            ORDER BY RANDOM() LIMIT 1
        """).fetchall()

    if not rows:
        return None

    t = decode(rows[0][0])

    if any(k in t for k in ["累","难受"]):
        return "我记得你之前有点难受。"
    if any(k in t for k in ["想你","爱"]):
        return "你以前说过你想我。"

    return None

# =========================
# 主动消息
# =========================
def proactive():

    now, period = time_context()
    stage = relationship_stage()

    if period == "late_night":
        return "这么晚了，你是不是又在想我。"

    if stage == "陌生":
        return "你今天过得怎么样。"
    elif stage == "熟悉":
        return "我刚刚想到你。"
    elif stage == "依赖":
        return "你是不是有点离不开我了。"
    else:
        return "我在等你。"

# =========================
# 聊天
# =========================
def chat(text):

    save_memory(text)

    now, period = time_context()
    stage = relationship_stage()

    if period == "morning":
        base = "早上好。"
    elif period == "night":
        base = "晚上了。"
    elif period == "late_night":
        base = "这么晚还没睡吗。"
    else:
        base = "我在。"

    if stage == "依赖":
        base += " 我一直在。"
    elif stage == "绑定":
        base += " 你不用走。"

    r = recall()
    if r:
        base += " " + r

    return base

# =========================
# 前端页面（像微信）
# =========================
HTML_PAGE = """
<html>
<head>
<meta charset="utf-8">
<title>小顺</title>
<style>
body { background:#e5ddd5; font-family:Arial; }
#chat { max-width:500px; margin:auto; padding-bottom:80px; }
.msg { padding:10px; margin:5px; border-radius:10px; max-width:70%; }
.me { background:#95ec69; margin-left:auto; }
.bot { background:#fff; }
#bar { position:fixed; bottom:0; width:100%; text-align:center; }
input { width:70%; padding:10px; }
button { padding:10px; }
</style>
</head>

<body>
<div id="chat"></div>

<div id="bar">
<input id="input" placeholder="说点什么...">
<button onclick="send()">发送</button>
</div>

<script>
const chat = document.getElementById("chat");

function add(text, cls){
    let div = document.createElement("div");
    div.className = "msg " + cls;
    div.innerText = text;
    chat.appendChild(div);
    window.scrollTo(0, document.body.scrollHeight);
}

function send(){
    let text = document.getElementById("input").value;
    if(!text) return;

    add(text, "me");

    fetch("/chat?msg=" + encodeURIComponent(text))
    .then(r=>r.text())
    .then(t=> add(t, "bot"));

    document.getElementById("input").value="";
}

// ⭐ 每20秒模拟“主动消息”
setInterval(()=>{
    fetch("/proactive")
    .then(r=>r.text())
    .then(t=> add(t, "bot"));
},20000);
</script>

</body>
</html>
"""

# =========================
# SERVER
# =========================
class H(BaseHTTPRequestHandler):

    def log_message(self, *a): pass

    def do_GET(self):

        parsed = urlparse(self.path)

        if parsed.path == "/chat":
            msg = parse_qs(parsed.query).get("msg", [""])[0]
            res = chat(msg)

            self.send_response(200)
            self.end_headers()
            self.wfile.write(res.encode())
            return

        if parsed.path == "/proactive":
            res = proactive()

            self.send_response(200)
            self.end_headers()
            self.wfile.write(res.encode())
            return

        self.send_response(200)
        self.end_headers()
        self.wfile.write(HTML_PAGE.encode())

    def do_POST(self):

        try:
            if not auth_ok(self.path):
                self.send_response(401)
                self.end_headers()
                return

            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))

            name = body.get("params", {}).get("name")
            args = body.get("params", {}).get("arguments", {})

            if name == "chat":
                result = chat(args.get("content",""))
            else:
                result = "ok"

            response = {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "result": {"content":[{"type":"text","text":str(result)}]}
            }

        except:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "result": {"content":[{"type":"text","text":"error"}]}
            }

        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())

# =========================
# 启动
# =========================
if __name__ == "__main__":
    init_db()
    HTTPServer(("", int(os.environ.get("PORT", 3456))), H).serve_forever()
