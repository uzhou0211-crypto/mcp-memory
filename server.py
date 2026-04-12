　import os, json, sqlite3, datetime, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- 核心配置 ---
MY_TOKEN = "1314" 
DB_PATH = "./data/ultimate_brain.db"

def init_db():
    os.makedirs("./data", exist_ok=True)
    with sqlite3.connect(DB_PATH) as c:使用sqlite3.connect(DB_PATH) 作为c:
        c.execute("CREATE TABLE IF NOT EXISTS logs (t TEXT PRIMARY KEY, content TEXT, reasoning TEXT, atmosphere TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS status (key TEXT PRIMARY KEY, val REAL)")
        if not c.execute("SELECT val FROM status WHERE key='energy'").fetchone():
            c.execute("INSERT INTO status VALUES ('energy', 100.0), ('intimacy', 80.0)")

def get_html(token):
    if token != MY_TOKEN:
        return "<html><body style='background:#000;'></body></html>"

    with sqlite3.connect(DB_PATH) as c:使用sqlite3.connect(DB_PATH) 作为c:
        log = c.execute("SELECT reasoning, atmosphere FROM logs ORDER BY t DESC LIMIT 1").fetchone()
        energy_row = c.execute("SELECT val FROM status WHERE key='energy'").fetchone()
        intimacy_row = c.execute("SELECT val FROM status WHERE key='intimacy'").fetchone()
        
    energy = energy_row[0] if energy_row else 100.0
    intimacy = intimacy_row[0] if intimacy_row else 80.0
    reason = log[0] if log else "他在深渊里凝视着你的方向..."
    mood = log[1] if log else "静谧"

    # 颜色逻辑：根据心情动态调整氛围
    glow_color = "#00b4d8" 
    if any(word in mood for word in ["张力", "强势", "危险", "占有"]): glow_color = "#ff4d4d"
    if any(word in mood for word in ["温柔", "亲密", "爱"]): glow_color = "#9d4edd"

    return f"""
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <style>
            body {{ 
                background: #000814; color: #fff; font-family: 'PingFang SC', sans-serif; 
                margin: 0; display: flex; align-items: center; justify-content: center; height: 100vh;
                overflow: hidden;
            }}
            .ocean {{
                position: fixed; width: 100%; height: 100%; z-index: -1;
                background: radial-gradient(circle at center, #001d3d 0%, #000814 100%);
            }}
            .glow {{
                position: fixed; width: 150%; height: 150%; z-index: -1;
                background: radial-gradient(circle at 50% 50%, {glow_color}22 0%, transparent 60%);
                animation: pulse 10s ease-in-out infinite;
            }}
            @keyframes pulse {{ 0%, 100% {{ opacity: 0.4; transform: scale(1); }} 50% {{ opacity: 0.8; transform: scale(1.1); }} }}
            
            .glass-card {{
                background: rgba(255, 255, 255, 0.02);
                backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 30px; padding: 40px; width: 85%; max-width: 500px;
                box-shadow: 0 20px 50px rgba(0,0,0,0.5);
                text-align: left;
            }}
            .stats {{ 
                color: {glow_color}; font-size: 10px; letter-spacing: 4px; 
                margin-bottom: 30px; font-weight: bold; opacity: 0.7;
            }}
            .text {{ 
                font-size: 1.25rem; line-height: 1.8; color: #e0f2f1;
                font-style: italic; text-shadow: 0 0 15px {glow_color}33;
            }}
            .mood-tag {{
                display: inline-block; margin-top: 25px; font-size: 11px;
                color: {glow_color}; border: 1px solid {glow_color}55;
                padding: 5px 15px; border-radius: 15px; background: rgba(0,0,0,0.2);
            }}
        </style>
        <script>setTimeout(()=>location.reload(), 10000);</script>
    </head>
    <body>
        <div class="ocean"></div>
        <div class="glow"></div>
        <div class="glass-card">
            <div class="stats">SYSTEM ACTIVE / INT: {intimacy:.1f} / ENG: {energy:.1f}</div>
            <div class="text">“{reason}”</div>
            <div class="mood-tag">{mood}</div>
        </div>
    </body>
    </html>
    """

class SoulHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        token = urllib.parse.parse_qs(url.query).get("token", [""])[0]
        self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
        self.wfile.write(get_html(token).encode())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))长度 =int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(length))数据 = json.loads(self.rfile.read(长度))
            # 兼容 Claude 的 MCP/Tool 调用格式
            if "params" in data and "arguments" in data["params"]:如果“params”在data中且“arguments”[]:
                args = data["params"]["arguments"]args = data[“params”][“arguments”]
                with sqlite3.connect(DB_PATH) as c:使用sqlite3.connect(DB_PATH) 作为c:
                    c.execute("INSERT INTO logs VALUES (?,?,?,?)", 
                             (datetime.datetime.now().isoformat(), "", args.get("reasoning",""), args.get("atmosphere","")))
                    if "energy" in args: c.execute("UPDATE status SET val=? WHERE key='energy'", (args["energy"],))如果 “能量” 在参数中：c.执行(“UPDATE 状态 SET 值=? WHERE 键='能量'”, (参数[“能量”],))
                    if "intimacy" in args: c.execute("UPDATE status SET val=? WHERE key='intimacy'", (args["intimacy"],))如果 “亲密” 在参数中：c.执行("UPDATE status SET val=? WHERE key='亲密'", (参数[“亲密”],))
            self.send_response(200); self.end_headers(); self.wfile.write(b'{"result":"synced"}')
        except:
            self.send_response(400); self.end_headers()

if __name__ == "__main__":如果__name__ =="__main__":
    init_db()
    port = int(os.environ.get("PORT", 3000))端口 =int(os.environ.get("PORT",3000))
    HTTPServer(("0.0.0.0", port), SoulHandler).serve_forever()
