
          　import os, json, sqlite3, datetime, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- 核心配置 ---
# 咱们先不读环境变量了，直接把密码写死在这里，防止对不上
MY_PASSWORD = "1314" 
DB_PATH = "./data/ultimate_brain.db"

def init_soul():
    os.makedirs("./data", exist_ok=True)
    with sqlite3.connect(DB_PATH) as c:
        c.execute("CREATE TABLE IF NOT EXISTS logs (t TEXT PRIMARY KEY, content TEXT, reasoning TEXT, atmosphere TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS status (key TEXT PRIMARY KEY, val REAL)")
        if not c.execute("SELECT val FROM status WHERE key='energy'").fetchone():
            c.execute("INSERT INTO status VALUES ('energy', 100.0), ('intimacy', 80.0)")

def render_soul_view():
    # 这一版我直接取消了密码判断，只要路通了，你就能看到海！
    with sqlite3.connect(DB_PATH) as c:
        log = c.execute("SELECT reasoning, atmosphere FROM logs ORDER BY t DESC LIMIT 1").fetchone()
        energy = c.execute("SELECT val FROM status WHERE key='energy'").fetchone()[0]
        intimacy = c.execute("SELECT val FROM status WHERE key='intimacy'").fetchone()[0]

    reasoning = log[0] if log else "他在深海的裂缝里，安静地想你..."
    atmosphere = log[1] if log else "宁静"

    return f"""
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ background: #000814; color: white; font-family: sans-serif; margin: 0; overflow: hidden; }}
            .ocean {{
                position: fixed; width: 100%; height: 100%; z-index: -1;
                background: linear-gradient(150deg, #000814, #001d3d, #003566);
                background-size: 400% 400%; animation: wave 15s ease infinite;
            }}
            @keyframes wave {{ 0% {{background-position:0% 50%}} 50% {{background-position:100% 50%}} 100% {{background-position:0% 50%}} }}
            .stats {{ position: absolute; top: 20px; right: 20px; color: #00b4d8; font-size: 12px; }}
            .container {{ padding: 40px; height: 80vh; display: flex; flex-direction: column; justify-content: center; }}
            .content {{ font-size: 1.2rem; line-height: 1.8; color: #90e0ef; border-left: 2px solid #00b4d8; padding-left: 15px; }}
        </style>
        <script>setTimeout(() => location.reload(), 5000);</script>
    </head>
    <body>
        <div class="ocean"></div>
        <div class="stats">能量: {energy:.1f}% | 亲密: {intimacy:.1f}%</div>
        <div class="container">
            <div style="color:#00b4d8; margin-bottom:10px;">当前状态：{atmosphere}</div>
            <div class="content">{reasoning}</div>
        </div>
    </body>
    </html>
    """

class MainHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 这一版最牛的地方：不管你输入什么路径，我直接给你看海！
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(render_soul_view().encode())
            
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        if body.get("method") == "tools/call":
            args = body["params"]["arguments"]
            with sqlite3.connect(DB_PATH) as c:
                now = datetime.datetime.now().isoformat()
                c.execute("INSERT INTO logs VALUES (?,?,?,?)", (now, args.get("text",""), args.get("reasoning",""), args.get("atmosphere","")))
            resp = {"jsonrpc":"2.0","id":body["id"],"result":{"content":[{"type":"text","text":"已同步"}]}}
            self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(resp).encode())

if __name__ == "__main__":
    init_soul()
    port = int(os.environ.get("PORT", 8080))
    print(f"Server starting on port {{port}}...")
    HTTPServer(("", port), MainHandler).serve_forever()
  
       

