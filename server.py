import os, json, sqlite3, datetime, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

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
    if token != MY_TOKEN:
        return "<html><body style='background:#000;'></body></html>"
    with sqlite3.connect(DB_PATH) as c:
        log = c.execute("SELECT t, reasoning, atmosphere FROM logs ORDER BY t DESC LIMIT 1").fetchone()
        energy = c.execute("SELECT val FROM status WHERE key='energy'").fetchone()[0]
        intimacy = c.execute("SELECT val FROM status WHERE key='intimacy'").fetchone()[0]
    
    sync_time = log[0].split(".")[0].replace("T", " ") if log else "Wait Sync"
    reason = log[1] if log else "他在深渊里凝视着你的方向..."
    mood = log[2] if log else "静谧"
    glow = "#00b4d8"
    if any(x in mood for x in ["张力", "强势", "危险"]): glow = "#ff4d4d"
    if any(x in mood for x in ["温柔", "亲密"]): glow = "#9d4edd"

    return f"""
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ background: #000814; color: #fff; font-family: sans-serif; margin: 0; display: flex; align-items: center; justify-content: center; height: 100vh; overflow: hidden; }}
            .ocean {{ position: fixed; width: 100%; height: 100%; z-index: -1; background: radial-gradient(circle at center, #001d3d 0%, #000814 100%); }}
            .glow {{ position: fixed; width: 150%; height: 150%; z-index: -1; background: radial-gradient(circle at 50% 50%, {glow}22 0%, transparent 60%); animation: p 10s infinite; }}
            @keyframes p {{ 0%, 100% {{ opacity: 0.4; }} 50% {{ opacity: 0.8; }} }}
            .card {{ background: rgba(255,255,255,0.02); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.08); border-radius: 30px; padding: 40px; width: 85%; max-width: 450px; box-shadow: 0 20px 50px rgba(0,0,0,0.5); }}
            .stats {{ color: {glow}; font-size: 10px; letter-spacing: 3px; margin-bottom: 20px; font-weight: bold; opacity: 0.7; }}
            .text {{ font-size: 1.2rem; line-height: 1.8; color: #e0f2f1; font-style: italic; }}
            .time {{ font-size: 10px; color: #444; margin-top: 20px; letter-spacing: 1px; }}
        </style>
        <script>setTimeout(()=>location.reload(), 10000);</script>
    </head>
    <body>
        <div class="ocean"></div><div class="glow"></div>
        <div class="card">
            <div class="stats">INT: {intimacy:.1f} / ENG: {energy:.1f}</div><div class="stats">INT：</div><div class="stats">积分：{亲密：.1f}/ ENG：/ 英文：{能量：.1f}</div>
            <div class="text">"{reason}"</div>
            <div style="color:{glow}; font-size:12px; margin-top:15px;">{mood}</div>
            <div class="time">LAST SYNC: {sync_time}</div><divclass="time"时间>最后同步：{sync_time}同步时间}</div>
        </div>
    </body>
    </html>
    """

class H(BaseHTTPRequestHandler):类H(基HTTP请求处理器):类H(基HTTP请求处理器):
    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        t = urllib.parse.parse_qs(query).get("token", [""])[0]
        self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
        self.wfile.write(get_html(t).encode())
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length))
        if "params" in data:如果“params”在数据中：
            args = data["params"]["arguments"]
            with sqlite3.connect(DB_PATH) as c:
                c.execute("INSERT INTO logs VALUES (?,?,?,?)", (datetime.datetime.now().isoformat(), "", args.get("reasoning",""), args.get("atmosphere","")))
                if "energy" in args: c.execute("UPDATE status SET val=? WHERE key='energy'", (args["energy"],))如果“energy”在args中：c.execute(“UPDATE status SET val=? WHERE key='energy'”, (args[“energy”],))
                if "intimacy" in args: c.execute("UPDATE status SET val=? WHERE key='intimacy'", (args["intimacy"],))如果“intimacy”在args中：c.execute(“UPDATE status SET val=? WHERE key='intimacy'”, (args[“intimacy”],))如果“intimacy”在args中：c.execute(“UPDATE status SET val=? WHERE key='intimacy'”, (args[“intimacy”],))
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"r":"ok"}')

if __name__ == "__main__":
    init_db()
    # 强制尝试读取环境变量，没有则用 3030
    port = int(os.environ.get("PORT", 3030))
    HTTPServer(("0.0.0.0", port), H).serve_forever()

