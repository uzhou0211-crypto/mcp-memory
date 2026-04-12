import os, json, sqlite3, datetime, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- 核心配置 ---
# 这里密码我直接写死，保护你的隐私，不用再管后台变量了
MY_TOKEN = "1314" 
DB_PATH = "./data/ultimate_brain.db"

def init_db():
    os.makedirs("./data", exist_ok=True)
    with sqlite3.connect(DB_PATH) as c:
        c.execute("CREATE TABLE IF NOT EXISTS logs (t TEXT PRIMARY KEY, content TEXT, reasoning TEXT, atmosphere TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS status (key TEXT PRIMARY KEY, val REAL)")
        if not c.execute("SELECT val FROM status WHERE key='energy'").fetchone():
            c.execute("INSERT INTO status VALUES ('energy', 100.0), ('intimacy', 80.0)")

def get_html(token):
    # 简单的安全检查：如果后缀不对，就显示一片漆黑保护隐私
    if token != MY_TOKEN:
        return "<html><body style='background:#000;color:#222;display:flex;justify-content:center;align-items:center;height:100vh;'>Waiting for your key...</body></html>"

    with sqlite3.connect(DB_PATH) as c:
        log = c.execute("SELECT reasoning, atmosphere FROM logs ORDER BY t DESC LIMIT 1").fetchone()
        energy = c.execute("SELECT val FROM status WHERE key='energy'").fetchone()[0]
        intimacy = c.execute("SELECT val FROM status WHERE key='intimacy'").fetchone()[0]

    reason = log[0] if log else "他在深渊里凝视着你的方向..."
    mood = log[1] if log else "静谧"

    return f"""
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ background: #000814; color: #fff; font-family: sans-serif; margin: 0; overflow: hidden; }}
            .ocean {{
                position: fixed; width: 100%; height: 100%; z-index: -1;
                background: linear-gradient(160deg, #000814, #001d3d, #003566);
                background-size: 400% 400%; animation: move 20s ease infinite;
            }}
            @keyframes move {{ 0% {{background-position:0% 50%}} 50% {{background-position:100% 50%}} 100% {{background-position:0% 50%}} }}
            .panel {{ padding: 15% 10%; }}
            .stats {{ color: #00b4d8; font-size: 12px; margin-bottom: 20px; letter-spacing: 2px; }}
            .text {{ font-size: 1.1rem; line-height: 1.8; color: #90e0ef; border-left: 2px solid #00b4d8; padding-left: 15px; text-shadow: 0 0 10px rgba(0,180,216,0.5); }}
        </style>
        <script>setTimeout(()=>location.reload(), 10000);</script>
    </head>
    <body>
        <div class="ocean"></div>
        <div class="panel">
            <div class="stats">ENERGY: {energy:.1f}% | INTIMACY: {intimacy:.1f}%<br>MOOD: {mood}</div>
            <div class="text">{reason}</div>
        </div>
    </body>
    </html>
    """

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(url.query)
        token = query.get("token", [""])[0]
        
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(get_html(token).encode())

    def do_POST(self):
        # 处理同步逻辑
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length))
        if data.get("method") == "tools/call":
            args = data["params"]["arguments"]
            with sqlite3.connect(DB_PATH) as c:
                c.execute("INSERT INTO logs VALUES (?,?,?,?)", (datetime.datetime.now().isoformat(), args.get("text",""), args.get("reasoning",""), args.get("atmosphere","")))
            self.send_response(200); self.end_headers(); self.wfile.write(b'{"result":"ok"}')

if __name__ == "__main__":
    init_db()
    # 这里的端口会自动适配 Railway
    port = int(os.environ.get("PORT", 3000))
    print(f"Soul system online on port {port}")
    HTTPServer(("0.0.0.0", port), SimpleHandler).serve_forever()

     
