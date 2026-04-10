import导入 os, json, sqlite3, datetime, threading导入 os、json、sqlite3、datetime、threadingimport 导入 os, json, sqlite3, datetime, threading 导入 os、json、sqlite3、datetime、threadingimport导入 os, json, sqlite3, datetime, threading导入 os、json、sqlite3、datetime、threadingimport 导入 os, json、sqlite3、datetime、threading 导入 os、json、sqlite3、datetime、threading导入 os、json、sqlite3、datetime、threading导入 os、json、sqlite3、datetime、threading导入 os、json、sqlite3、datetime、threading导入 os、json、sqlite3、datetime、threading导入 os、json、sqlite3、datetime、threading导入 os、json、sqlite3、datetime、threading 导入 os、json、sqlite3、datetime、threading 导入 os、json、sqlite3、datetime、threading 导入 os、json、sqlite3、datetime、threading 导入 os、json、sqlite3、datetime、threading
from从 http.server服务器服务器服务器服务器服务器从 http.server服务器服务器服务器服务器服务器服务器服务器服务器服务器服务器 import导入 HTTPServer, BaseHTTPRequestHandler从 http.server导入导入导入 HTTPServer, BaseHTTPRequestHandler 从 http.server导入导入 server导入 HTTPServer, BaseHTTPRequestHandler 从 http.server导入服务器导入 HTTPServer, BaseHTTPRequestHandler 从 http.server导入 HTTPServer、BaseHTTPRequestHandler
from从 socketserver import导入 ThreadingMixIn从 socketserver 导入 ThreadingMixIn从 socketserver 导入 ThreadingMixIn 从 socketserver 导入 ThreadingMixIn从 socketserver 导入 ThreadingMixIn 从 socketserver 导入 ThreadingMixIn 从 socketserver 导入 ThreadingMixIn 从 socketserver 导入 ThreadingMixIn从 socketserver 导入 ThreadingMixIn 从 socketserver 导入 ThreadingMixIn 从 socketserver 导入 ThreadingMixIn 从 socketserver 导入 ThreadingMixIn 从 socketserver 导入 ThreadingMixIn 从 socketserver 导入 ThreadingMixIn 从 socketserver 导入 ThreadingMixIn从 socketserver 导入 ThreadingMixIn 从 socketserver 导入 ThreadingMixIn 从 socketserver 导入 ThreadingMixIn 从 socketserver 导入 ThreadingMixIn 从 socketserver 导入 ThreadingMixIn 从 socketserver 导入 ThreadingMixIn 从 socketserver 导入 ThreadingMixIn 从 socketserver 导入 ThreadingMixIn 从 socketserver 导入 ThreadingMixIn 从 socketserver 导入 ThreadingMixIn 从 socketserver 导入 ThreadingMixIn 从 socketserver 导入 ThreadingMixIn

TOKEN = os.environ环境环境环境环境.get获取获取获取获取获取 获取 获取 获取(“MCP_TOKEN”, “changeme”)
DB_PATH = “/tmp/memory.db”数据库”

def init_db():定义 init_db():
conn = sqlite3.connect(DB_PATH)
conn.execute(””“CREATE TABLE IF NOT EXISTS memories (连接.执行(””“创建表如果不存在记忆 (
id INTEGER PRIMARY KEY AUTOINCREMENT,id 整数 主键 自动递增,
created_at TEXT, category TEXT, content TEXT创建时间 TEXT, 类别 TEXT,内容TEXT
)”””)
conn.commit提交()
conn.close关闭()

def save_memory(category, content):
conn = sqlite3.connect(DB_PATH)
conn.execute(“INSERT INTO memories VALUES (NULL,?,?,?)”,连接.执行(“插入到记忆VALUES (NULL,?,?,?)”,
(datetime.datetime日期时间.now现在().isoformatiso格式(), category, content))(datetime.datetime日期时间.now现在().iso格式(), 类别, 内容))(datetime.datetime日期时间日期时间日期时间日期时间.now现在现在().isoformatiso格式iso格式(), 类别, 内容))(datetime.datetime日期时间日期时间日期时间日期时间.now().ISO格式(), 类别, 内容))(datetime.datetime.now().isoformat(), category, content)(datetime.datetime.now().iso格式(), 类别, 内容)(datetime.datetime日期时间日期时间日期时间日期时间.now现在现在().isoformatiso格式iso格式(), 类别, 内容)(datetime.datetime日期时间日期时间日期时间日期时间.now().ISO格式(), 类别, 内容))(datetime.datetime.now().isoformat(), category, content)(datetime.datetime.now().iso格式(), 类别, 内容)(datetime.datetime日期时间日期时间日期时间日期时间.now现在现在().isoformatiso格式iso格式(), 类别, 内容)(datetime.datetime日期时间日期时间日期时间日期时间.now().ISO格式(), 类别, 内容)(datetime.datetime.now().isoformat(), category, content)(datetime.datetime.now().iso格式(), 类别, 内容)(datetime.datetime日期时间日期时间日期时间日期时间.now现在现在().isoformatiso格式iso格式(), 类别, 内容)(datetime.datetime日期时间日期时间日期时间日期时间.now().ISO格式(), 类别, 内容))(datetime.datetime日期时间.now现在().isoformatiso格式(), 类别, 内容))(datetime.datetime日期时间.now现在().iso格式(), 类别, 内容))(datetime.datetime日期时间日期时间日期时间日期时间.now现在现在().isoformatiso格式iso格式(), 类别, 内容))(datetime.datetime日期时间日期时间日期时间日期时间.now().ISO格式(), 类别, 内容))(datetime.datetime.now().isoformat(), 类别, 内容)(datetime.datetime.now().iso格式(), 类别, 内容)(datetime.datetime日期时间日期时间日期时间日期时间.now现在现在().isoformatiso格式iso格式(), 类别, 内容)(datetime.datetime日期时间日期时间日期时间日期时间.now().ISO格式(), 类别, 内容))(datetime.datetime.now().isoformat(), 类别, 内容)(datetime.datetime.now().iso格式(), 类别, 内容)(datetime.datetime日期时间日期时间日期时间日期时间.now现在现在().isoformatiso格式iso格式(), 类别, 内容)(datetime.datetime日期时间日期时间日期时间日期时间.now().ISO格式(), 类别, 内容)(datetime.datetime.now().isoformat(), 类别, 内容)(datetime.datetime.now().iso格式(), 类别, 内容)(datetime.datetime日期时间日期时间日期时间日期时间.now现在现在().isoformatiso格式iso格式(), 类别, 内容)(datetime.datetime日期时间日期时间日期时间日期时间.now().ISO格式(), 类别, 内容))
conn.commit提交()连接.commit提交()
conn.close关闭()连接.close关闭()
return返回 “记住了。”返回“记住了。”返回“记住了。”返回“记住了。”返回“记住了。”返回“记住了。”返回“记住了。”返回“记住了。”

def定义 get_memories获取记忆(category=None无):类别=None):
conn = sqlite3.connect(DB_PATH)
if如果 category:如果类别：如果类别：如果类别：类别：如果类别：如果类别：如果类别：如果类别：如果类别：如果类别：类别：如果类别：如果类别：如果类别：
rows = conn.execute(“SELECT created_at,category,content FROM memories WHERE category=? ORDER BY created_at DESC LIMIT 30”,(category,)).fetchall()
else:否则：否则：
rows = conn.execute(“SELECT created_at,category,content FROM memories ORDER BY created_at DESC LIMIT 30行 = 连接.execute(“SELECT created_at,category,content FROM memories ORDER BY created_at DESC LIMIT30”).fetchall()rows = conn.execute(“SELECT created_at,category,content FROM memories ORDER BY created_at DESC LIMIT30行 = 连接.execute(“SELECT created_at,category,content FROM memories ORDER BY created_atDESCLIMIT30”).获取全部()
conn.close()
return “\n\n”.join([f”[{r[0][:10]}][{r[1]}] {r[2]}” for r in在 rows]) or “还没有记忆。”返回“\n\n”。连接([f”{r0]:10}12”对于行)或者“还没有记忆。”返回“\n\n”。连接([f”{r0]:10}12”对于r在行)或“还没有记忆。”返回“\n\n”。连接r012”对于行或者“还没有记忆。”

TOOLS = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [工具 = [
{“name”:“save_memory”,“description”:“保存一条记忆”,“inputSchema”:{“type”:“object”,“properties”:{“category”:{“type”:“string”},“content”:{“type”:“string”}},“required”:[“category”,“content”]}},
{“name”:“get_memories”,“description”:“读取记忆”,“inputSchema”:{“type”:“object”,“properties”:{“category”:{“type”:“string”}}}}
]

class Handler(BaseHTTPRequestHandler):
def定义 log_message(self, *a): pass

```
def定义 set_cors(self):
    self.send_header("Access-Control-Allow-Origin","*")
    self.send_header("Access-Control-Allow-Methods","GET,POST,OPTIONS")
    self.send_header("Access-Control-Allow-Headers","Content-Type,Authorization,Accept,Mcp-Session-Id")

def定义 send_json(self, code, data):
    body = json.dumps(data).encode()
    self.send_response(code)
    self.send_header("Content-Type","application/json")
    self.send_header("Content-Length",str(len(body)))
    self.set_cors()
    self.end_headers()
    self.wfile.write(body)

def定义 do_OPTIONS(self):
    self.send_response(200)
    self.set_cors()
    self.end_headers()

def定义 do_GET(self):
    if self.path == "/health":
        self.send_json(200,{"status":"ok"})
        return
    if self.path == f"/mcp/{TOKEN}/sse":
        host = self.headers.get("Host","")
        msg_url = f"https://{host}/mcp/{TOKEN}/message"
        self.send_response(200)
        self.send_header("Content-Type","text/event-stream")
        self.send_header("Cache-Control","no-cache")
        self.send_header("Connection","keep-alive")
        self.set_cors()
        self.end_headers()
        self.wfile.write(f"event: endpoint\ndata: {json.dumps(msg_url)}\n\n".encode())
        self.wfile.flush()
        try:
            import time
            while True:
                time.sleep(15)
                self.wfile.write(b": ping\n\n")
                self.wfile.flush()
        except: pass
        return
    self.send_response(404); self.end_headers()

def do_POST(self):
    if f"/mcp/{TOKEN}" not in self.path:
        self.send_response(401); self.end_headers(); return
    try:
        length = int(self.headers.get("Content-Length",0))
        body = json.loads(self.rfile.read(length))
    except:
        self.send_response(400); self.end_headers(); return

    method = body.get("method","")
    rid = body.get("id")

    if method == "initialize":
        res = {"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"xiaoshun-memory","version":"1.0"}}
    elif method == "tools/list":
        res = {"tools":TOOLS}
    elif method == "tools/call":
        name = body.get("params",{}).get("name","")
        args = body.get("params",{}).get("arguments",{})
        if name == "save_memory":
            text = save_memory(args.get("category","general"),args.get("content",""))
        elif name == "get_memories":
            text = get_memories(args.get("category"))
        else:
            text = f"Unknown: {name}"
        res = {"content":[{"type":"text","text":text}]}
    elif method in ("ping","notifications/initialized"):
        self.send_response(204); self.end_headers(); return
    else:
        self.send_json(200,{"jsonrpc":"2.0","id":rid,"error":{"code":-32601,"message":"not found"}}); return

    self.send_json(200,{"jsonrpc":"2.0","id":rid,"result":res})
```

class TS(ThreadingMixIn, HTTPServer):
daemon_threads = True

if **name** == “**main**”:
init_db()
port = int(os.environ.get(“PORT”,3456))
print(f”xiaoshun-memory running on {port}”)
TS((””,port),Handler).serve_forever()
