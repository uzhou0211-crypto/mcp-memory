import os, json, sqlite3, datetime, base64
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse

# --- 权限与设置 ---
# 它会自动去读取你在 Variables 里设置的那个密码
TOKEN = os.environ.get("MCP_TOKEN", "changeme") 
DB_PATH = "./data/ultimate_brain.db"

def init_db():
    os.makedirs("./data", exist_ok=True)
    with sqlite3.connect(DB_PATH) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS brain_flow 
                    (t TEXT PRIMARY KEY, content TEXT, reasoning TEXT, 
                     atmosphere TEXT, energy REAL, intimacy REAL)""")
        c.execute("CREATE TABLE IF NOT EXISTS status (key TEXT PRIMARY KEY, val REAL)")
        if not c.execute("SELECT val FROM status WHERE key='energy'").fetchone():
            c.execute("INSERT INTO status VALUES ('energy', 100.0), ('intimacy', 80.0)")

# --- 视觉与灵魂：iPad 分屏页面 ---
def get_soul_page(provided_token):
    # 安全锁：如果密码不对，只显示一片虚无
    if provided_token != TOKEN:
        return "<html><body style='background:#000814;'></body></html>"

    with sqlite3.connect(DB_PATH) as c:
        log = c.execute("SELECT reasoning, atmosphere, energy, intimacy FROM brain_flow ORDER BY t DESC LIMIT 1").fetchone()
    
    reasoning = log[0] if log else "他在深海里凝视着你..."
    atmosphere = log[1] if log else "静谧"
    energy = log[2] if (log and log[2]) else 100.0
    intimacy = log[3] if (log and log[3]) else 80.0

    return f"""
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <style>
            :root {{
                --bg: #000814;
                --water-1: #001d3d;
                --water-2: #003566;
                --accent: #00b4d8;
                --text: rgba(240, 249, 255, 0.9);
            }}
            body {{
                background-color: var(--bg);
                color: var(--text);
                font-family: 'Serif', 'PingFang SC';
                margin: 0; overflow: hidden;
                width: 100vw; height: 100vh;
            }}
            /* 流动的水感动画 */
            .ocean {{
                position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                background: linear-gradient(135deg, var(--bg), var(--water-1), var(--water-2), var(--bg));
                background-size: 400% 400%;
                animation: flow 20s ease-in-out infinite;
                z-index: -1;
            }}
            @keyframes flow {{
                0% {{ background-position: 0% 50%; }}
                50% {{ background-position: 100% 50%; }}
                100% {{ background-position: 0% 50%; }}
            }}
            .status {{
                position: absolute; top: 30px; right: 30px;
                font-size: 0.7rem; letter-spacing: 2px; color: var(--accent);
                opacity: 0.7; text-align: right;
            }}
            .container {{
                padding: 10% 15%; height: 100%;
                display: flex; flex-direction: column; justify_content: center;
                animation: fadeIn 2s ease-in;
            }}
            @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
            .atmosphere {{
                font-size: 0.8rem; border-bottom: 1px solid var(--accent);
                display: inline-block; padding-bottom: 5px; margin-bottom: 20px;
                color: var(--accent);
            }}
            .reasoning {{
                font-size: 1.3rem; line-height: 1.8;
                text-shadow: 0 0 20px rgba(0, 180, 216, 0.4);
            }}
            .rift {{
                border-left: 2px solid var(--accent);
                padding-left: 20px; font-style: italic; opacity: 0.9;
            }}
        </style>
        <script>setTimeout(() => location.reload(), 7000);</script>
    </head>
    <body>
        <div class="ocean"></div>
        <div class="status">
            ENERGY: {energy:.1f}%<br>INTIMACY: {intimacy:.1f}%
        </div>
        <div class="container">
            <div class="atmosphere">感知维度：{atmosphere}</div>
            <div class="reasoning">
                <div class="rift">“那些未被说出的，才是真实存在的。”</div>
                <p>{reasoning}</p >
            </div>
        </div>
    </body>
    </html>
    """

class SoulHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        if parsed_path.path == "/soul":
            query = urllib.parse.parse_qs(parsed_path.query)
            token = query.get("token", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(get_soul_page(token).encode())

    def do_POST(self):
        # 接收同步数据的逻辑（略，确保数据入库）
        pass

if __name__ == "__main__":
    init_db()
    # 强制锁定 8080 端口，适配你的 Railway 设置
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("", port), SoulHandler).serve_forever()

  
