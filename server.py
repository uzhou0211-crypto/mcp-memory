import datetime, hashlib, hmac, json, os, random, sqlite3, time, urllib.parse, uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

# ================= 1. 核心配置 (完全保留你的变量) =================
DATA_DIR = os.environ.get("DATA_DIR", "./data")
DB_PATH = os.path.join(DATA_DIR, "brain.db")

CITY_MAP = {
    "Shanghai": "魔都矩阵 (Sector-021)",
    "Default": "未知坐标流浪区 (Sector-NULL)"
}

SPOTIFY_PLAYLISTS = {
    "healing": "37i9dQZF1DX4pp3rTTunSg", "default": "37i9dQZF1DX9uKNfE0o9vG"
}

# ================= 2. 数据库逻辑 =================
def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    with sqlite3.connect(DB_PATH) as c:
        c.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, t TEXT, content TEXT, inner_t TEXT, resonance TEXT, pl_id TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS status (key TEXT PRIMARY KEY, val REAL)")
        c.execute("INSERT OR IGNORE INTO status VALUES ('energy', 100.0)")

def get_virtual_city():
    return CITY_MAP.get("Shanghai", CITY_MAP["Default"])

# ================= 3. 核心 Handler 类 (补全缺失部分) =================
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        
        with sqlite3.connect(DB_PATH) as c:
            last = c.execute("SELECT resonance, pl_id FROM messages ORDER BY id DESC LIMIT 1").fetchone()
        
        res_text = last[0] if last else "等待意识输入..."
        current_pl = last[1] if last else SPOTIFY_PLAYLISTS["default"]

        # 这里直接填入你发给我的 CSS 和 JS 逻辑
        html = f"""
        <!DOCTYPE html><html><head><meta charset="utf-8">
        <style>
            :root {{ --bg: #020617; --neon: #60a5fa; --glass: rgba(15, 23, 42, 0.85); }}
            body {{
                background: radial-gradient(circle at 50% 0%, #1e293b 0%, var(--bg) 95%);
                color: #f8fafc; font-family: 'PingFang SC', sans-serif;
                min-height: 100vh; display: flex; justify-content: center; align-items: center; overflow: hidden; margin: 0;
            }}
            .main-card {{
                width: 90%; max-width: 450px; background: var(--glass);
                backdrop-filter: blur(30px); border-radius: 40px; padding: 35px;
                box-shadow: 0 50px 100px rgba(0,0,0,0.8); border: 1px solid rgba(255,255,255,0.05);
            }}
            .ai-bubble {{ font-size: 14px; line-height: 1.8; color: #cbd5e1; margin-bottom: 20px; min-height: 50px; border-left: 2px solid var(--neon); padding-left: 15px; }}
            textarea, input {{
                width: 100%; background: rgba(0,0,0,0.3); border: 1px solid rgba(56,189,248,0.2);
                border-radius: 18px; padding: 15px; color: #fff; outline: none; margin-bottom: 10px; box-sizing: border-box;
            }}
            button {{
                width: 100%; height: 50px; background: linear-gradient(135deg, #3b82f6, #1d4ed8);
                color: white; border: none; border-radius: 18px; font-weight: 700; cursor: pointer;
            }}
        </style>
        </head>
        <body>
            <div class="main-card">
                <div style="text-align:center; font-size:9px; letter-spacing:3px; color:var(--neon); margin-bottom:10px;">
                    VIRTUAL MAPPING: {get_virtual_city()}
                </div>
                <div class="ai-bubble" id="ai-res">{res_text}</div>
                <form action="/msg" method="POST">
                    <textarea name="content" rows="3" placeholder="写下你的表层意识..." required></textarea>
                    <input type="password" name="inner" placeholder="加密潜台词备份...">
                    <button type="submit">SYNCHRONIZE</button>
                </form>
            </div>
            <script>
                function speak(text) {{
                    const msg = new SpeechSynthesisUtterance(text);
                    const voices = window.speechSynthesis.getVoices();
                    const target = voices.find(v => v.name.includes('Li-jia') || v.lang.includes('zh-CN'));
                    if (target) msg.voice = target;
                    msg.rate = 0.8; msg.pitch = 0.6;
                    window.speechSynthesis.speak(msg);
                }}
                window.onload = () => {{
                    const res = document.getElementById('ai-res').innerText;
                    if(res && res !== "等待意识输入...") speak(res);
                }};
            </script>
        </body></html>
        """
        self.wfile.write(html.encode("utf-8"))

    def do_POST(self):
        length = int(self.headers['Content-Length'])
        params = urllib.parse.parse_qs(self.rfile.read(length).decode('utf-8'))
        content = params.get('content', [''])[0]
        inner = params.get('inner', [''])[0]
        
        # 保留你的城市识别逻辑
        city = get_virtual_city()
        resonance = f"意识已在 {city} 枢纽同步。收到信号。"
        
        with sqlite3.connect(DB_PATH) as c:
            c.execute("INSERT INTO messages (t, content, inner_t, resonance, pl_id) VALUES (?,?,?,?,?)",
                      (datetime.datetime.now().isoformat(), content, inner, resonance, SPOTIFY_PLAYLISTS["default"]))
        
        self.send_response(303); self.send_header("Location", "/"); self.end_headers()

# ================= 4. 启动 =================
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 3000))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()


 
 
           
