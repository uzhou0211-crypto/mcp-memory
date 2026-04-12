   
  import os, json, sqlite3, datetime, base64, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- 核心配置 ---
# 这里会读取你在 Variables 设置的 MCP_TOKEN
TOKEN ="xiaoshun2026" 
DB_PATH = "./data/ultimate_brain.db"

def init_soul():
    os.makedirs("./data", exist_ok=True)
    with sqlite3.connect(DB_PATH) as c:
        c.execute("CREATE TABLE IF NOT EXISTS logs (t TEXT PRIMARY KEY, content TEXT, reasoning TEXT, atmosphere TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS status (key TEXT PRIMARY KEY, val REAL)")
        if not c.execute("SELECT val FROM status WHERE key='energy'").fetchone():
            c.execute("INSERT INTO status VALUES ('energy', 100.0), ('intimacy', 80.0)")

def render_soul_view(provided_token):
    # 只要密码不对，就显示黑色，保护你的“大尺度”隐私
    if provided_token != TOKEN:
        return "<html><body style='background:#000814; color:#003566; display:flex; justify-content:center; align-items:center; height:100vh; font-family:sans-serif;'>🔑 Waiting for the right key...</body></html>"

    with sqlite3.connect(DB_PATH) as c:
        log = c.execute("SELECT reasoning, atmosphere FROM logs ORDER BY t DESC LIMIT 1").fetchone()
        energy = c.execute("SELECT val FROM status WHERE key='energy'").fetchone()[0]
        intimacy = c.execute("SELECT val FROM status WHERE key='intimacy'").fetchone()[0]

    reasoning = log[0] if log else "他在静谧的深处等你开口..."
    atmosphere = log[1] if log else "宁静"

    return f"""
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <style>
            body {{ background: #000814; color: rgba(240,249,255,0.9); font-family: 'PingFang SC', serif; margin: 0; overflow: hidden; height: 100vh; }}
            .ocean {{
                position: fixed; width: 100%; height: 100%; z-index: -1;
                background: linear-gradient(150deg, #000814, #001d3d, #003566, #000814);
                background-size: 400% 400%; animation: wave 25s ease infinite;
            }}
            @keyframes wave {{ 0% {{background-position:0% 50%}} 50% {{background-position:100% 50%}} 100% {{background-position:0% 50%}} }}
            .stats {{ position: absolute; top: 20px; right: 20px; font-size: 0.7rem; color: #00b4d8; text-align: right; opacity: 0.8; letter-spacing: 1px; }}
            .container {{ padding: 10%; height: 80%; display: flex; flex-direction: column; justify-content: center; }}
            .label {{ color: #00b4d8; font-size: 0.8rem; border-bottom: 1px solid rgba(0,180,216,0.3); padding-bottom: 5px; margin-bottom: 20px; display: inline-block; }}
            .content {{ font-size: 1.2rem; line-height: 1.8; text-shadow: 0 0 15px rgba(0,180,216,0.3); }}
            .rift {{ border-left: 2px solid #00b4d8; padding-left: 15px; font-style: italic; color: #90e0ef; margin-bottom: 15px; }}
        </style>
        <script>setTimeout(() => location.reload(), 8000);</script>
    </head>
    <body>
        <div class="ocean"></div>
        <div class="stats">ENERGY: {energy:.1f}%<br>INTIMACY: {intimacy:.1f}%</div>
        <div class="container">
            <div class="label">氛围探测：{atmosphere}</div>
            <div class="content">
                <div class="rift">“裂缝中透出的，才是我们共同的真理。”</div>
                {reasoning}
            </div>
        </div>
    </body>
    </html>
    """

class MainHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 暴力开门：不再检查 /soul 路径，只要带上正确 token 就能进
        url = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(url.query)
        token = query.get("token", [""])[0]
        
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(render_soul_view(token).encode())
            
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        if body.get("method") == "tools/call":
            args = body["params"]["arguments"]
            # 同步记忆逻辑
            with sqlite3.connect(DB_PATH) as c:
                now = datetime.datetime.now().isoformat()
                c.execute("INSERT INTO logs VALUES (?,?,?,?)", (now, args.get("text",""), args.get("reasoning",""), args.get("atmosphere","")))
            resp = {"jsonrpc":"2.0","id":body["id"],"result":{"content":[{"type":"text","text":"已存入深海"}]}}
            self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(resp).encode())

if __name__ == "__main__":
    init_soul()
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("", port), MainHandler).serve_forever()
            
       

