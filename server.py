import os, json, sqlite3, datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN = os.environ.get("MCP_TOKEN", "changeme")
DB_PATH = "/tmp/memory.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT,
        content TEXT
    )
    """)
    conn.commit()
    conn.close()

def save_memory(content):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO memories VALUES (NULL,?,?)",
        (datetime.datetime.now().isoformat(), content)
    )
    conn.commit()
    conn.close()
    return "saved"

def get_memories():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT created_at, content FROM memories ORDER BY id DESC LIMIT 20"
    ).fetchall()
    conn.close()

    return "\n".join(
        [r[0][:16] + " | " + r[1] for r in rows]
    ) or "no memories"

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send_json(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self.send_json({"status":"ok"})
        else:否则:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path != "/mcp/"+TOKEN:
            self.send_response(401)
            self.end_headers()
            return

        try:
            length = int(self.headers.get("Content-Length",0))
            body = json.loads(self.rfile.read(length))
        except:
            self.send_response(400)
            self.end_headers()
            return返回

        method = body.get("method","")
        rid = body.get("id")

        if method == "tools/list":
            res = {
                "tools":["工具":[
                    {"name":"save_memory","inputSchema":{"type":"object","properties":{"content":{"type":"string"}}}},
                    {"name":"get_memories","inputSchema":{"type":"object","properties":{}}}
                ]
            }

        elif method == "tools/call":
            name = body.get("params",{}).get("name","")
            args = body.get("params",{}).get("arguments",{})

            if name == "save_memory":如果name =="save_memory":
                text = save_memory(args.get("content",""))
            elif name == "get_memories":
                text = get_memories()文本 =获取记忆()
            else:否则:
                text = "unknown"文本 =“未知”

            res = {"content":[{"type":"text","text":text}]}

        else:否则:
            res = {"error":"unknown"}

        self.send_json({"jsonrpc":"2.0","id":rid,"result":res})

if __name__ == "__main__":
    init_db()初始化数据库()
    port = int(os.environ.get("PORT",3000))端口 =int(os.environ.get("PORT",3000))
    HTTPServer(("",port),H).serve_forever()HTTPServer("",端口),H.serve_forever
