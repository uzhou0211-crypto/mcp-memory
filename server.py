import os, json, sqlite3, datetime, hashlib, base64, math
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN = os.environ.get("MCP_TOKEN", "changeme")
DB = "./data/memory.db"

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

def init():
    os.makedirs("./data", exist_ok=True)
    with sqlite3.connect(DB) as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            category TEXT,
            content TEXT,
            emotion INTEGER,
            hash TEXT
        )
        """)

def emotion_score(text):
    text = str(text)
    if any(k in text for k in ["爱","想你","喜欢","离不开"]):
        return 5
    if any(k in text for k in ["在意","重要"]):
        return 4
    if any(k in text for k in ["累","烦","难受"]):
        return 3
    return 1

def save_memory(category, content):
    content = str(content)
    category = str(category) if category else "默认"
    if not content:
        return "内容不能为空"
    h = sha(content)
    with sqlite3.connect(DB) as c:
        if c.execute("SELECT 1 FROM memories WHERE hash=?", (h,)).fetchone():
            return "已存在相同记忆，跳过保存"
        c.execute(
            "INSERT INTO memories VALUES (NULL,?,?,?,?,?)",
            (now().isoformat(), category, enc(content), emotion_score(content), h)
        )
    return f"记忆已保存：[{category}] {content}"

def decay(emotion, created_at):
    t = datetime.datetime.fromisoformat(created_at)
    hours = (now() - t).total_seconds() / 3600
    return emotion * math.exp(-0.04 * hours)

def get_memories(category=None):
    with sqlite3.connect(DB) as c:
        if category:
            rows = c.execute(
                "SELECT created_at, category, content, emotion FROM memories WHERE category=?",
                (category,)
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT created_at, category, content, emotion FROM memories"
            ).fetchall()

    if not rows:
        return "暂无记忆"

    scored = []
    for r in rows:
        weight = decay(r[3], r[0])
        scored.append((weight, r[1], dec(r[2]), r[0]))

    scored.sort(reverse=True)

    lines = []
    for weight, cat, content, created_at in scored[:20]:
        lines.append(f"[{cat}] {content}  （{created_at[:10]}）")

    return "\n".join(lines)

# MCP Tools definition
TOOLS = [
    {
        "name": "save_memory",
        "description": "保存一条记忆，指定分类和内容",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "记忆分类，例如：爱、日常、重要"},
                "content": {"type": "string", "description": "记忆内容"}
            },
            "required": ["category", "content"]
        }
    },
    {
        "name": "get_memories",
        "description": "获取已保存的记忆，可按分类筛选",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "筛选分类，留空则返回全部"}
            }
        }
    }
]

class H(BaseHTTPRequestHandler):

    def log_message(self, *a):
        pass

    def do_GET(self):
        if not self.path.startswith(f"/mcp/{TOKEN}"):
            self.send_response(401)
            self.end_headers()
            return
        # SSE endpoint for MCP handshake
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

    def do_POST(self):
        try:
            if not self.path.startswith(f"/mcp/{TOKEN}"):
                self.send_response(401)
                self.end_headers()
                return

            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}

            method = body.get("method", "")
            bid = body.get("id")
            params = body.get("params", {})

            if method == "initialize":
                out = {
                    "jsonrpc": "2.0", "id": bid,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "memory-server", "version": "1.0"}
                    }
                }

            elif method == "tools/list":
                out = {
                    "jsonrpc": "2.0", "id": bid,
                    "result": {"tools": TOOLS}
                }

            elif method == "tools/call":
                name = params.get("name")
                args = params.get("arguments", {})

                if name == "save_memory":
                    res = save_memory(args.get("category", "默认"), args.get("content", ""))
                elif name == "get_memories":
                    res = get_memories(args.get("category"))
                else:
                    res = f"未知工具: {name}"

                out = {
                    "jsonrpc": "2.0", "id": bid,
                    "result": {
                        "content": [{"type": "text", "text": res}]
                    }
                }

            elif method == "notifications/initialized":
                self.send_response(200)
                self.end_headers()
                return

            else:
                out = {
                    "jsonrpc": "2.0", "id": bid,
                    "result": {}
                }

        except Exception as e:
            out = {
                "jsonrpc": "2.0", "id": None,
                "error": {"code": -32603, "message": str(e)}
            }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(out).encode())

if __name__ == "__main__":
    init()
    port = int(os.environ.get("PORT", 3456))
    print(f"MCP memory server running on port {port}")
    HTTPServer(("", port), H).serve_forever()
