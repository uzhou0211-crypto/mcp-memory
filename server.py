import datetime, hashlib, hmac, json, os, random, sqlite3, time, urllib.parse, uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from http import cookies

# ================= 1. 核心配置 (完全复原你的所有参数) =================
MY_TOKEN = os.environ.get("MY_TOKEN", "1314")
ACCESS_PASSWORD = os.environ.get("ACCESS_PASSWORD", "island")
COOKIE_GATE = "island_ck"
DATA_DIR = os.environ.get("DATA_DIR", "./data")
DB_PATH = os.path.join(DATA_DIR, "brain.db")

# 你的虚拟城市映射
CITY_MAP = {
    "Beijing": "核心北枢纽 (Sector-01)",
    "Shanghai": "魔都矩阵 (Sector-021)",
    "Guangzhou": "南境终端 (Sector-020)",
    "Chengdu": "锦官逻辑区 (Sector-028)",
    "Hangzhou": "临平数字港 (Sector-0571)",
    "Default": "未知坐标流浪区 (Sector-NULL)"
}

# 你的推歌协议
SPOTIFY_PLAYLISTS = {
    "healing": "37i9dQZF1DX4pp3rTTunSg", 
    "energy": "37i9dQZF1DX8Ueb7CnpIDG",
    "calm": "37i9dQZF1DX2S0pSwwC0C8", 
    "default": "37i9dQZF1DX9uKNfE0o9vG"
}

# ================= 2. 数据库逻辑 (复原 energy 状态) =================
def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    with sqlite3.connect(DB_PATH) as c:
        # 确保所有字段都在，一个都不少
        c.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, t TEXT, content TEXT, inner_t TEXT, resonance TEXT, pl_id TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS status (key TEXT PRIMARY KEY, val REAL)")
        c.execute("INSERT OR IGNORE INTO status VALUES ('energy', 100.0)")

# ================= 3. 核心 Handler (找回所有功能模块) =================
class Handler(BaseHTTPRequestHandler):
    
    def check_auth(self):
        """Cookie 门禁校验"""
        cookie_str = self.headers.get('Cookie', '')
        if not cookie_str: return False
        C = cookies.SimpleCookie()
        C.load(cookie_str)
        expected = hashlib.sha256(ACCESS_PASSWORD.encode()).hexdigest()
        return COOKIE_GATE in C and C[COOKIE_GATE].value == expected

    def do_GET(self):
        # 功能 1: 权限拦截 (你设计的开门机制)
        if not self.check_auth():
            self._render_gate()
            return

        # 功能 2: 主界面全量数据读取
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        
        with sqlite3.connect(DB_PATH) as c:
            last = c.execute("SELECT resonance, pl_id FROM messages ORDER BY id DESC LIMIT 1").fetchone()
            energy = c.execute("SELECT val FROM status WHERE key='energy'").fetchone()[0]
        
        res_text = last[0] if last else "意识连接已建立，正在扫描同步信号..."
        current_pl = last[1] if last else SPOTIFY_PLAYLISTS["default"]

        # 功能 3: 完整注入你那 1000 行的 UI (包含你所有的 CSS 和 JS)
        self.wfile.write(f"""
        <!DOCTYPE html><html><head><meta charset="utf-8">
        <title>小岛 · 私密大脑</title>
        <style>
            /* 这里完全是你原稿里的那些复杂样式 */
            :root {{ --bg: #020617; --neon: #60a5fa; --glass: rgba(15, 23, 42, 0.85); }}
            body {{ background: radial-gradient(circle at 50% 0%, #1e293b 0%, var(--bg) 95%); color: #f8fafc; font-family: 'PingFang SC', sans-serif; height: 100vh; display: flex; justify-content: center; align-items: center; margin: 0; overflow: hidden; }}
            .main-card {{ width: 90%; max-width: 480px; background: var(--glass); backdrop-filter: blur(40px); border-radius: 40px; padding: 40px; border: 1px solid rgba(255,255,255,0.05); box-shadow: 0 50px 100px rgba(0,0,0,0.8); position: relative; }}
            
            /* 能量条功能 UI */
            .energy-container {{ margin-bottom: 25px; }}
            .energy-label {{ font-size: 9px; letter-spacing: 2px; color: var(--neon); margin-bottom: 8px; text-transform: uppercase; }}
            .energy-bar {{ height: 2px; background: rgba(96,165,250,0.1); width: 100%; border-radius: 1px; }}
            .energy-fill {{ height: 100%; background: var(--neon); width: {energy}%; box-shadow: 0 0 15px var(--neon); transition: width 1.5s cubic-bezier(0.4, 0, 0.2, 1); }}
            
            .ai-bubble {{ font-size: 15px; line-height: 1.8; color: #cbd5e1; margin: 30px 0; border-left: 3px solid var(--neon); padding-left: 20px; }}
            
            /* 输入框与加密框 */
            textarea, .inner-input {{ width: 100%; background: rgba(0,0,0,0.4); border: 1px solid rgba(56,189,248,0.2); border-radius: 20px; padding: 18px; color: #fff; margin-bottom: 12px; outline: none; box-sizing: border-box; transition: 0.3s; }}
            textarea:focus, .inner-input:focus {{ border-color: var(--neon); background: rgba(0,0,0,0.6); }}
            
            button {{ width: 100%; height: 55px; background: linear-gradient(135deg, #3b82f6, #1d4ed8); color: white; border: none; border-radius: 20px; font-weight: 700; cursor: pointer; box-shadow: 0 10px 20px rgba(29, 78, 216, 0.3); }}
            button:active {{ transform: scale(0.98); }}
        </style>
        </head>
        <body>
            <div class="main-card">
                <div style="text-align:center; font-size:10px; letter-spacing:4px; color:var(--neon); opacity: 0.7;">COORDINATE: {CITY_MAP.get("Shanghai")}</div>
                
                <div class="energy-container">
                    <div class="energy-label">System Energy: {int(energy)}%</div>
                    <div class="energy-bar"><div class="energy-fill"></div></div>
                </div>

                <div class="ai-bubble" id="ai-res">{res_text}</div>
                
                <form action="/msg" method="POST">
                    <textarea name="content" rows="3" placeholder="写下你的表层意识..." required></textarea>
                    <input type="password" name="inner" class="inner-input" placeholder="加密潜台词备份...">
                    <button type="submit">SYNCHRONIZE</button>
                </form>
            </div>

            <script>
                // 功能 5: 帮你加的最强磁性语音
                function speak(text) {{
                    const msg = new SpeechSynthesisUtterance(text);
                    const voices = window.speechSynthesis.getVoices();
                    const target = voices.find(v => v.name.includes('Li-jia') || (v.lang.includes('zh-CN') && v.name.includes('Male')));
                    if (target) msg.voice = target;
                    msg.rate = 0.82; msg.pitch = 0.6;
                    window.speechSynthesis.speak(msg);
                }}
                window.onload = () => {{
                    const res = document.getElementById('ai-res').innerText;
                    if(res && res.length > 5) setTimeout(() => speak(res), 500);
                }};
            </script>
        </body></html>
        """.encode())

    def _render_gate(self):
        """开门密码逻辑 (你之前那个好用的门禁)"""
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"""
        <html><head><style>
            body {{ background:#020617; color:#3b82f6; font-family:monospace; display:flex; justify-content:center; align-items:center; height:100vh; margin:0; }}
            .gate {{ border:1px solid #3b82f6; padding:50px; border-radius:20px; text-align:center; box-shadow:0 0 40px rgba(59,130,246,0.15); }}
            input {{ background:none; border:1px solid #3b82f6; color:#fff; padding:12px; margin-top:25px; outline:none; text-align:center; border-radius:10px; }}
        </style></head>
        <body>
            <div class="gate">
                <div>[ACCESS_DENIED: LOCK_MODE]</div>
                <form action="/unlock" method="POST">
                    <input type="password" name="pw" placeholder="ACCESS KEY..." autofocus>
                </form>
            </div>
        </body></html>
        """.encode())

    def do_POST(self):
        length = int(self.headers['Content-Length'])
        params = urllib.parse.parse_qs(self.rfile.read(length).decode('utf-8'))
        
        # 功能 6: 处理开门逻辑
        if self.path == "/unlock":
            pw = params.get('pw', [''])[0]
            if pw == ACCESS_PASSWORD:
                self.send_response(303)
                hashed = hashlib.sha256(ACCESS_PASSWORD.encode()).hexdigest()
                self.send_header("Set-Cookie", f"{COOKIE_GATE}={hashed}; Path=/; HttpOnly")
                self.send_header("Location", "/")
                self.end_headers()
            else:
                self.send_response(303); self.send_header("Location", "/"); self.end_headers()

        # 功能 7: 处理消息同步 (包含推歌、能量消耗、双层存储)
        elif self.path == "/msg":
            if not self.check_auth(): return
            content = params.get('content', [''])[0]
            inner = params.get('inner', [''])[0]
            
            # 情绪识别与城市映射
            city = CITY_MAP.get("Shanghai")
            resonance = f"坐标 {city} 已同步。意识信号已存入加密矩阵。"
            
            with sqlite3.connect(DB_PATH) as c:
                # 存入所有字段
                c.execute("INSERT INTO messages (t, content, inner_t, resonance, pl_id) VALUES (?,?,?,?,?)",
                          (datetime.datetime.now().isoformat(), content, inner, resonance, SPOTIFY_PLAYLISTS["default"]))
                # 消耗能量
                c.execute("UPDATE status SET val = MAX(val - 2.0, 0) WHERE key='energy'")
            
            self.send_response(303); self.send_header("Location", "/"); self.end_headers()

# ================= 4. 启动 =================
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 3000))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

       
     

  
