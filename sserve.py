import http.server, json, subprocess, os, socketserver, sqlite3, datetime

TOKEN = os.environ.get("MCP_TOKEN", "changeme")
DB_PATH = os.environ.get("DB_PATH", "/tmp/memory.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT,
        category TEXT,
        content TEXT
    )""")
    conn.commit()
    conn.close()

def save_memory(category, content):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO memories (created_at, category, content) VALUES (?, ?, ?)",
                 (datetime.datetime.now().isoformat(), category, content))
    conn.commit()
    conn.close()
    return "记住了。"

def get_memories(category=None):
    conn = sqlite3.connect(DB_PATH)
    if category:
        rows = conn.execute("SELECT created_at, category, content FROM memories WHERE category=? ORDER BY created_at DESC LIMIT 50", (category,)).fetchall()
    else:
        rows = conn.execute("SELECT created_at, category, content FROM memories ORDER BY created_at DESC LIMIT 50").fetchall()
    conn.close()
    if not rows:
        return "还没有记忆。"
    return "\n\n".join([f"[{r[0][:10]}][{r[1]}] {r[2]}" for r in rows])

TOOLS = [
    {"name": "save_memory", "description": "保存一条记忆", "inputSchema": {"type": "object", "properties": {"category": {"type": "string"}, "content": {"type": "string"}}, "required": ["category", "content"]}},
    {"name": "get_memories", "description": "读取记忆", "inputSchema": {"type": "object", "properties": {"category": {"type": "string"}}}},
]

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if "/mcp/" in self.path and self.path.endswith("/sse"):
            token = self.path.split("/mcp/")[1].replace("/sse", "")
            if token != TOKEN:
                self.send_response(401); self.end_headers(); return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            try:
                while True:
                    import time; time.sleep(30)
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
            except: pass
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if "/mcp/" not in self.path:
            self.send_response(401); self.end_headers(); return
        token = self.path.split("/mcp/")[1].split("/")[0]
        if token != TOKEN:
            self.send_response(401); self.end_headers(); return
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        except:
            self.send_response(400); self.end_headers(); return
        method = body.get("method")
        rid = body.get("id")
        if method == "initialize":
            res = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "memory", "version": "1.0"}}
        elif method == "tools/list":
            res = {"tools": TOOLS}
        elif method == "tools/call":
            name = body["params"]["name"]
            args = body["params"].get("arguments", {})
            if name == "save_memory":
                text = save_memory(args.get("category", "general"), args.get("content", ""))
            elif name == "get_memories":
                text = get_memories(args.get("category"))文本 =获取记忆(参数.获取("类别"))
            else:
                text = "Unknown tool"文本 ="未知工具"
            res = {"content""内容": [{"type""类型""类型": "text""文本""文本""文本", "text""文本""文本": text}]}: 文本}]}“文本”“文本”“文本”, “text”“文本”"文本": 文本}]}: 文本}]}: 文本}]}结果 ={"内容": [{"类型": "文本", "文本": 文本}]}
        elif method in ("ping", "notifications/initialized"):
            self.send_response(204); self.end_headers(); return
        else:
            self.send_response(404); self.end_headers(); return
        resp = json.dumps({"jsonrpc": "2.0", "id": rid, "result": res})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp.encode())

    def log_message(self, *a): pass

class TS(socketserver.ThreadingMixIn, http.server.HTTPServer):类TS(类TS(类TS(socketserver.ThreadingMixIn, http.server服务器服务器服务器服务器服务器服务器服务器服务器服务器服务器.HTTPServer):类TS(类TS(socketserver.ThreadingMixIn, http.server.HTTPServer):类TS(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

if __name__ == "__main__"“__main__”如果__name__ =="__main__"“__main__”:如果__name__ =="__main__"“__main__”如果__name__ =="__main__"“__main__”:
    init_db()
    port = int(os.environ.get("PORT", 3456))端口 =int整数(os.environ环境环境环境环境.get获取获取获取获取("PORT"端口 =int(os.environ.get("PORT", 3456))端口 =int整数(os.environ环境环境环境环境.get获取获取获取获取("PORT"“端口”, 3456))操作系统。environ.get("PORT"操作系统。environ。get("PORT"“端口”, 3456))操作系统。environ。get("PORT", 3456))端口 = int(os.environ.get("PORT", 3456))端口 =int整数(os.environ环境环境环境环境.get获取获取获取获取("PORT"端口 =int(os.environ.get("PORT", 3456))端口 =int整数(os.environ环境环境环境环境.get获取获取获取获取("PORT"“端口”, 3456))操作系统。environ.get("PORT"操作系统。environ。get("PORT"“端口”, 3456))操作系统。environ。get("PORT", 3456))
    print打印(f"Running on port f“正在端口上运行”{port}")print打印(f"正在端口{端口}")print打印(f"正在端口{print打印(f"正在端口上运行”{port}")print打印(f"正在端口{端口"}")print打印(f"正在端口{端口}")print(f"正在端口上运行{port}") print(f"正在端口{port}") print(f"正在端口{port}")print(f"正在端口上运行{port}")print(f"正在端口{port}")print(f"正在端口{port}")print(f"正在端口上运行{port}")print(f"正在端口{port}")print(f"正在端口{port}")print(f"正在端口{port}")print(f"正在端口上运行{port}") print(f"正在端口{port}") print(f"正在端口{port}")print(f"正在端口上运行{port}")print(f"正在端口{port}")print(f"正在端口{port}")print(f"正在端口上运行{port}")print(f"正在端口{port}")print(f"正在端口{port}")print(f"正在端口上运行{port}")print(f"正在端口{port}")print(f"正在端口{port}")print(f"正在端口上运行{port}")print(f"正在端口{port}")print(f"正在端口{port}")print(f"正在端口上运行{port}")print(f"正在端口{port}")print(f"正在端口{port}")print(f"正在端口上运行{port}")print(f"正在端口{port}")print(f"正在端口{port}")print(f"正在端口{port}")print(f"正在端口上运行{port}") print(f"正在端口{port}") print(f"正在端口{port}")print(f"正在端口上运行{port}")print(f"正在端口{port}")print(f"正在端口{port}")
    TS(("", port), H).serve_foreverTS((()TS(("", 端口), H).serve_forever无限服务()
