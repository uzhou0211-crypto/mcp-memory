import os, json, sqlite3, datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

TOKEN = os.environ.get("MCP_TOKEN", "changeme")
DB_PATH = "/tmp/memory.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS memories (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, category TEXT, content TEXT)")
    conn.commit()
    conn.close()

def save_memory(category, content):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO memories VALUES (NULL,?,?,?)", (datetime.datetime.now().isoformat(), category, content))
    conn.commit()
    conn.close()
    return "saved"

def get_memories(category=None):
    conn = sqlite3.connect(DB_PATH)
    if category:
        rows = conn.execute("SELECT created_at,category,content FROM memories WHERE category=? ORDER BY created_at DESC LIMIT 30", (category,)).fetchall()
    else:
        rows = conn.execute("SELECT created_at,category,content FROM memories ORDER BY created_at DESC LIMIT 30").fetchall()
    conn.close()
    return "\n\n".join(["["+r[0][:10]+"]["+r[1]+"] "+r[2] for r in rows]) or "no memories yet"

TOOLS = [
    {"name":"save_memory","description":"save a memory","inputSchema":{"type":"object","properties":{"category":{"type":"string"},"content":{"type":"string"}},"required":["category","content"]}},
    {"name":"get_memories","description":"get memories","inputSchema":{"type":"object","properties":{"category":{"type":"string"}}}}
]

sessions = {}

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def cors(self):
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","GET,POST,OPTIONS,DELETE")
        self.send_header("Access-Control-Allow-Headers","Content-Type,Authorization,Accept,Mcp-Session-Id")
        self.send_header("Access-Control-Expose-Headers","Mcp-Session-Id")

    def send_json(self, code, data, session_id=None):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(body)))
        if session_id:
            self.send_header("Mcp-Session-Id", session_id)
        self.cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self.send_json(200, {"status":"ok"})
            return
        self.send_response(404)
        self.end_headers()

    def do_DELETE(self):
        self.send_response(200)
        self.cors()
        self.end_headers()

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/")
        if path != "/mcp/"+TOKEN:
            self.send_response(401)
            self.end_headers()
            return
        try:
            length = int(self.headers.get("Content-Length",0))
            body = json.loads(self.rfile.read(length))
        except:
            self.send_response(400)
            self.end_headers()
            return

        session_id = self.headers.get("Mcp-Session-Id","")
        method = body.get("method","")
        rid = body.get("id")

        if method == "initialize":
            import uuid
            session_id = uuid.uuid4().hex
            sessions[session_id] = True
            res = {"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"xiaoshun-memory","version":"1.0"}}
            self.send_json(200, {"jsonrpc":"2.0","id":rid,"result":res}, session_id)
            return
        elif method == "tools/list":
            res = {"tools":TOOLS}
        elif method == "tools/call":
            name = body.get("params",{}).get("name","")
            args = body.get("params",{}).get("arguments",{})
            if name == "save_memory":
                text = save_memory(args.get("category","general"), args.get("content",""))
            elif name == "get_memories":
                text = get_memories(args.get("category"))
            else:
                text = "unknown tool"
            res = {"content":[{"type":"text","text":text}]}
        elif method in ("ping","notifications/initialized"):
            self.send_response(204)
            self.cors()
            self.end_headers()
            return
        else:
            self.send_json(200,{"jsonrpc":"2.0","id":rid,"error":{"code":-32601,"message":"not found"}})
            return

        self.send_json(200,{"jsonrpc":"2.0","id":rid,"result":res})

class TS(ThreadingMixIn, HTTPServer):
    daemon_threads = True

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT",3456))
    print("running on "+str(port))
    TS(("",port),H).serve_forever()
