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
        else:
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
            return

        method = body.get("method","")
        rid = body.get("id")

        if method == "tools/list":
            res = {
                "tools":[
                    {"name":"save_memory","inputSchema":{"type":"object","properties":{"content":{"type":"string"}}}},
                    {"name":"get_memories","inputSchema":{"type":"object","properties":{}}}
                ]
            }

        elif method == "tools/call":
            name = body.get("params",{}).get("name","")
            args = body.get("params",{}).get("arguments",{})

            if name == "save_memory":
                text = save_memory(args.get("content",""))
            elif name == "get_memories":
                text = get_memories()
            else:
                text = "unknown"

            res = {"content":[{"type":"text","text":text}]}

        else:
            res = {"error":"unknown"}

        self.send_json({"jsonrpc":"2.0","id":rid,"result":res})

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT",3000))
    HTTPServer(("",port),H).serve_forever()
# ================== 新增：前端接口 ==================

MEMORY = []

@app.route("/api/read", methods=["GET"])
def read_memory():
    return jsonify(MEMORY)

@app.route("/api/sync", methods=["POST"])
def sync_memory():
    token = request.args.get("token")
    if token != "1314":
        return jsonify({"error": "unauthorized"}), 401

    data = request.json
    item = {
        "content": data.get("content", ""),
        "area": data.get("area", "未知"),
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    MEMORY.append(item)

    return jsonify({"status": "saved"})
    
