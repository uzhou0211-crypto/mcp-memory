import os, json, sqlite3, datetime, threading, queue
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

TOKEN = os.environ.get("MCP_TOKEN", "changeme")
DB_PATH = "/tmp/memory.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT, category TEXT, content TEXT
    )""")
    conn.commit()
    conn.close()

def save_memory(category, content):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO memories VALUES (NULL,?,?,?)",
        (datetime.datetime.now().isoformat(), category, content))
    conn.commit()
    conn.close()
    return "记住了。"

def get_memories(category=None):
    conn = sqlite3.connect(DB_PATH)
    if category:
        rows = conn.execute(
            "SELECT created_at,category,content FROM memories WHERE category=? ORDER BY created_at DESC LIMIT 30",
            (category,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT created_at,category,content FROM memories ORDER BY created_at DESC LIMIT 30"
        ).fetchall()
    conn.close()
    return "\n\n".join([f"[{r[0][:10]}][{r[1]}] {r[2]}" for r in rows]) or "还没有记忆。"

TOOLS = [
    {
        "name": "save_memory",
        "description": "保存一条记忆",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "分类"},
                "content": {"type": "string", "description": "内容"}
            },
            "required": ["category", "content"]
        }
    },
    {
        "name": "get_memories",
        "description": "读取记忆",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "分类筛选，可选"}
            }
        }
    }
]

# SSE client queues
sse_clients = {}
sse_lock = threading.Lock()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization,Accept")

    def send_json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self.send_json(200, {"status": "ok"})
            return

        # SSE endpoint: /mcp/{TOKEN}/sse
        if self.path == f"/mcp/{TOKEN}/sse":
            client_id = id(self)
            q = queue.Queue()
            with sse_lock:
                sse_clients[client_id] = q

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.cors_headers()
            self.end_headers()

            # Send endpoint event pointing to message URL
            host = self.headers.get("Host", "localhost")
            endpoint_url = f"https://{host}/mcp/{TOKEN}/message"
            self.wfile.write(f"event: endpoint\ndata: {json.dumps({'uri': endpoint_url})}\n\n".encode())
            self.wfile.flush()

            try:
                import time
                while True:
                    try:
                        msg = q.get(timeout=15)
                        self.wfile.write(f"event: message\ndata: {json.dumps(msg)}\n\n".encode())
                        self.wfile.flush()
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
            except:
                pass
            finally:
                with sse_lock:
                    sse_clients.pop(client_id, None)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        # Message endpoint: /mcp/{TOKEN}/message
        if self.path not in (f"/mcp/{TOKEN}/message", f"/mcp/{TOKEN}"):
            self.send_response(401)
            self.end_headers()
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except:
            self.send_response(400)
            self.end_headers()
            return

        method = body.get("method", "")
        rid = body.get("id")

        if method == "initialize":
            res = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "xiaoshun-memory", "version": "1.0"}
            }
        elif method == "tools/list":
            res = {"tools": TOOLS}
        elif method == "tools/call":
            name = body.get("params", {}).get("name", "")
            args = body.get("params", {}).get("arguments", {})
            if name == "save_memory":
                text = save_memory(args.get("category", "general"), args.get("content", ""))
            elif name == "get_memories":
                text = get_memories(args.get("category"))
            else:
                text = f"Unknown tool: {name}"
            res = {"content": [{"type": "text", "text": text}]}
        elif method in ("ping", "notifications/initialized"):
            self.send_response(204)
            self.end_headers()
            return
        else:
            self.send_json(200, {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "Method not found"}})
            return

        self.send_json(200, {"jsonrpc": "2.0", "id": rid, "result": res})

class ThreadedServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 3456))
    print(f"Starting xiaoshun-memory MCP server on port {port}")
    ThreadedServer(("", port), Handler).serve_forever()
