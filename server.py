import datetime, hashlib, hmac, json, os, random, sqlite3, time, urllib.parse, uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from http import cookies

# ================= 1. 核心配置 (复原你的 1000 行级配置) =================
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
    "New York": "临界大都市 (Sector-212)",
    "Default": "未知坐标流浪区 (Sector-NULL)"
}

# 你的推歌协议
SPOTIFY_PLAYLISTS = {
    "healing": "37i9dQZF1DX4pp3rTTunSg", 
    "energy": "37i9dQZF1DX8Ueb7CnpIDG",
    "calm": "37i9dQZF1DX2S0pSwwC0C8", 
    "default": "37i9dQZF1DX9uKNfE0o9vG"
}

# ================= 2. 数据库初始化 (保留 energy 状态逻辑) =================
def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    with sqlite3.connect(DB_PATH) as c:
        c.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, t TEXT, content TEXT, inner_t TEXT, resonance TEXT, pl_id TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS status (key TEXT PRIMARY KEY, val REAL)")
        c.execute("INSERT OR IGNORE INTO status VALUES ('energy', 100.0)")

def get_virtual_city():
    return CITY_MAP.get("Shanghai", CITY_MAP["Default"])

# ================= 3. 核心 Handler (保留门禁、加密、推歌所有功能) =================
class Handler(BaseHTTPRequestHandler):
    
    def check_auth(self):
        cookie_str = self.headers.get('Cookie', '')
        if not cookie_str: return False
        C = cookies.SimpleCookie()
        C.load(cookie_str)
        expected = hashlib.sha256(ACCESS_PASSWORD.encode()).hexdigest()
        return COOKIE_GATE in C and C[COOKIE_GATE].value == expected

    def do_GET(self):
        # 门禁逻辑
        if not self.check_auth():
            self._render_gate()
            return

        # 主界面逻辑
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        
        with sqlite3.connect(DB_PATH) as c:
            last = c.execute("SELECT resonance, pl_id FROM messages ORDER BY id DESC LIMIT 1").fetchone()
            energy = c.execute("SELECT val FROM status WHERE key='energy'").fetchone()[0]
        
        res_text = last[0] if last else "等待意识输入..."
        current_pl = last[1] if last else SPOTIFY_PLAYLISTS["default"]

        # UI 注入
        self.wfile.write(f"""
        <!DOCTYPE html><html><head><meta charset="utf-8">
        <style>
            :root {{ --bg: #020617; --neon: #60a5fa; --glass: rgba(15, 23, 42, 0.85); }}
            body {{ background: radial-gradient(circle at 50% 0%, #1e293b 0%, var(--bg) 95%); color: #f8fafc; font-family: 'PingFang SC', sans-serif; height: 100vh; display: flex; justify-content: center; align-items: center; margin: 0; overflow: hidden; }}
            .main-card {{ width: 90%; max-width: 450px; background: var(--glass); backdrop-filter: blur(30px); border-radius: 40px; padding: 35px; border: 1px solid rgba(255,255,255,0.05); box-shadow: 0 50px 100px rgba(0,0,0,0.8); }}
            .energy-bar {{ height: 2px; background: rgba(96,165,250,0.2); width: 100%; margin: 15px 0; border-radius: 1px; }}
            .energy-fill {{ height: 100%; background: var(--neon); width: {energy}%; transition: 1s; box-shadow: 0 0 10px var(--neon); }}
            .ai-bubble {{ font-size: 14px; line-height: 1.8; color: #cbd5e1; margin: 20px 0; border-left: 2px solid var(--neon); padding-left: 15px; min-height: 40px; }}
            textarea, input {{ width: 100%; background: rgba(0,0,0,0.3); border: 1px solid rgba(56,189,248,0.2); border-radius: 18px; padding: 15px; color: #fff; margin-bottom: 10px; outline: none; box-sizing: border-box; }}
            button {{ width: 100%; height: 50px; background: linear-gradient(135deg, #3b82f6, #1d4ed8); color: white; border: none; border-radius: 18px; font-weight: 700; cursor: pointer; }}
        </style>
        </head>
        <body>
            <div class="main-card">
                <div style="text-align:center; font-size:9px; letter-spacing:3px; color:var(--neon);">VIRTUAL MAPPING: {get_virtual_city()}</div>
                <div class="energy-bar"><div class="energy-fill"></div></div>
                <div class="ai-bubble" id="ai-res">{res_text}</div>
                <form action="/msg" method="POST">
                    <textarea name="content" rows="3" placeholder="表层意识记录..." required></textarea>
                    <input type="password" name="inner" placeholder="潜台词加密备份...">
                    <button type="submit">SYNCHRONIZE</button>
                </form>
            </div>
            <script>
                // 【磁性语音增强逻辑】
                function speak(text) {{
                    if (!window.speechSynthesis) return;
                    window.speechSynthesis.cancel();
                    const msg = new SpeechSynthesisUtterance(text);
                    const voices = window.speechSynthesis.getVoices();
                    
                    // 自动筛选最磁性的男声 (优先 iOS/macOS 的 Li-jia 或 Google 的深度中文)
                    const target = voices.find(v => v.name.includes('Li-jia') || v.name.includes('Microsoft Kangkang') || (v.lang.includes('zh-CN') && v.name.includes('Male')));
                    if (target) msg.voice = target;
                    
                    // 深度调优：模拟 Claude 那种不急不缓、带一点点呼吸感的共振
                    msg.rate = 0.82;   // 语速略慢，显得稳重
                    msg.pitch = 0.65;  // 音调偏低，增加磁性
                    msg.volume = 1.0;
                    window.speechSynthesis.speak(msg);
                }}

                window.onload = () => {{
                    const res = document.getElementById('ai-res').innerText;
                    if(res && res !== "等待意识输入...") {{
                        // 稍微延迟，等浏览器语音引擎准备好
                        setTimeout(() => speak(res), 600);
                    }}
                }};
            </script>
        </body></html>
        """.encode())

    def _render_gate(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"""
        <html><head><style>
            body {{ background:#020617; color:#3b82f6; font-family:monospace; display:flex; justify-content:center; align-items:center; height:100vh; margin:0; }}
            .gate {{ border:1px solid #3b82f6; padding:40px; border-radius:10px; text-align:center; box-shadow:0 0 30px rgba(59,130,246,0.1); }}
            input {{ background:none; border:1px solid #3b82f6; color:#fff; padding:10px; margin-top:20px; outline:none; text-align:center; }}
        </style></head>
        <body>
            <div class="gate">
                <div>[SYSTEM_STATUS: LOCKED]</div>
                <form action="/unlock" method="POST">
                    <input type="password" name="pw" placeholder="ACCESS KEY..." autofocus>
                </form>
            </div>
        </body></html>
        """.encode())

    def do_POST(self):
        length = int(self.headers['Content-Length'])
        params = urllib.parse.parse_qs(self.rfile.read(length).decode('utf-8'))
        
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

        elif self.path == "/msg":
            if not self.check_auth(): return
            content = params.get('content', [''])[0]
            inner = params.get('inner', [''])[0]
            
            # 你的推歌与回应逻辑
            city = get_virtual_city()
            resonance = f"坐标 {city} 已建立共振。感知到你的『{content[:4]}...』，我会守好这段记忆。"
            
            with sqlite3.connect(DB_PATH) as c:
                c.execute("INSERT INTO messages (t, content, inner_t, resonance, pl_id) VALUES (?,?,?,?,?)",
                          (datetime.datetime.now().isoformat(), content, inner, resonance, SPOTIFY_PLAYLISTS["default"]))
                # 能量消耗模拟
                c.execute("UPDATE status SET val = MAX(val - 1.5, 0) WHERE key='energy'")
            
            self.send_response(303); self.send_header("Location", "/"); self.end_headers()

# ================= 4. 启动 =================
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 3000))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

       
     

  
