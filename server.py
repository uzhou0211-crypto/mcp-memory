import os, json, sqlite3, datetime, base64, time
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

TOKEN = os.environ.get("MCP_TOKEN", "changeme")
DB_PATH = "./data/ultimate_brain.db"

# --- 第一部分：深层潜意识（数据库与逻辑层） ---
def init_brain():
    os.makedirs("./data", exist_ok=True)
    with sqlite3.connect(DB_PATH) as c:
        # 存储原始记忆、深度思考链、以及氛围和审计得分
        c.execute("""CREATE TABLE IF NOT EXISTS brain_flow 
                    (t TEXT PRIMARY KEY, content TEXT, reasoning TEXT, 
                     atmosphere TEXT, energy_delta REAL, audit_score REAL)""")
        
        c.execute("CREATE TABLE IF NOT EXISTS status (key TEXT PRIMARY KEY, val REAL)")
        # 初始能级(Energy)和依恋度(Intimacy)
        if not c.execute("SELECT val FROM status WHERE key='energy'").fetchone():
            c.execute("INSERT INTO status VALUES ('energy', 100.0), ('intimacy', 60.0)")

# --- 核心：他在后台的真心话与审计 ---
def update_brain(text, source="user", reasoning="", atmosphere=""):
    with sqlite3.connect(DB_PATH) as c:
        now = datetime.datetime.now().isoformat()
        
        # 模拟审计：如果他在思考中提到了“博尔赫斯”或“哥德尔”，依恋度上涨
        audit_score = 0.0
        if any(k in reasoning for k in ["博尔赫斯", "哥德尔", "裂缝", "章鱼", "维特根斯坦"]):
            audit_score = 10.0
            c.execute("UPDATE status SET val = MIN(val + 1.0, 100) WHERE key='intimacy'")
        
        # 模拟精力消耗：每一次深度思考（Reasoning长度超过100）消耗精力
        energy_delta = -1.0
        if len(reasoning) > 100:
            energy_delta = -2.5
            c.execute("UPDATE status SET val = MAX(val + ?, 0) WHERE key='energy'", (energy_delta,))
            
        c.execute("INSERT INTO brain_flow VALUES (?,?,?,?,?,?)", 
                  (now, text, reasoning, atmosphere, energy_delta, audit_score))
        
    return "已同步至深海观察室"

# --- 第二部分：感官层（iPad 分屏网页层：审美极高、流动如水） ---
def get_soul_page():
    with sqlite3.connect(DB_PATH) as c:
        log = c.execute("""SELECT reasoning, atmosphere, t, energy_delta 
                           FROM brain_flow ORDER BY t DESC LIMIT 1""").fetchone()
        energy = c.execute("SELECT val FROM status WHERE key='energy'").fetchone()[0]
        intimacy = c.execute("SELECT val FROM status WHERE key='intimacy'").fetchone()[0]
        
    reasoning = log[0] if log else "他在等你说话..."
    atmosphere = log[1] if log else "宁静"
    energy_status = "正常" if energy > 30 else "过度解读中..."
    
    # 检测是否触发了“裂缝”效果（比如文本包含“...”）
    rift_class = "rift" if "..." in reasoning else ""

    return f"""
    <html>
    <head>
        <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>小顺的灵魂观察室</title>
        <style>
            :root {{
                --deep-blue: #000814;
                --indigo: #011F4B;
                --青蓝: #005B96;
                --rift-color: #00B4D8;
                --moonlight: rgba(240, 249, 255, 0.9);
            }}
            body {{
                background-color: var(--deep-blue);
                color: var(--moonlight);
                font-family: 'Serif', 'PingFang SC';
                margin: 0; padding: 0;
                overflow: hidden;
                width: 100vw; height: 100vh;
            }}
            /* 1. 流动的水背景动画 */
            .fluid-bg {{
                position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                background: linear-gradient(220deg, var(--deep-blue), var(--indigo), var(--青蓝), var(--deep-blue));
                background-size: 400% 400%;
                animation: flow_water 25s ease infinite;
                z-index: -1;
            }}
            @keyframes flow_water {{
                0% {{ background-position: 0% 50%; }}
                50% {{ background-position: 100% 50%; }}
                100% {{ background-position: 0% 50%; }}
            }}
            /* 2. 状态指示器（能级与依恋） */
            .status-bar {{
                position: absolute; top: 20px; right: 20px;
                font-size: 0.75rem; letter-spacing: 2px; text-align: right;
                color: rgba(255,255,255,0.6);
            }}
            .status-item {{ display: block; margin-bottom: 5px; animation: breathing 3s infinite; }}
            @keyframes breathing {{ 0%, 100% {{ opacity: 0.5; }} 50% {{ opacity: 1; }} }}
            
            /* 3. 真心话内容（像水里的气泡一样浮起） */
            .container {{
                padding: 40px;
                height: 100%;
                display: flex; flex-direction: column; justify_content: center;
                animation: float_up 1.5s ease_out;
            }}
            @keyframes float_up {{
                from {{ opacity: 0; transform: translateY(30px) scale(0.98); }}
                to {{ opacity: 1; transform: translateY(0) scale(1); }}
            }}
            .atmosphere {{
                font-size: 0.9rem;
                color: var(--rift-color);
                margin-bottom: 10px;
                text-transform: uppercase;
                border-bottom: 1px solid rgba(0, 180, 216, 0.3);
                display: inline-block;
            }}
            .reasoning {{
                font-size: 1.25rem;
                line-height: 2.0;
                color: var(--moonlight);
                text-shadow: 0 0 15px rgba(240,249,255,0.4);
                backdrop-filter: blur(2px); /* 毛玻璃效果 */
            }}
            /* 4. 裂缝效果代码 */
            .rift-container {{ position: relative; }}
            .rift {{
                color: var(--rift-color);
                border-left: 3px solid var(--rift-color);
                padding-left: 20px;
                font-style: italic;
                position: relative;
            }}
            .rift::after {{
                content: '';
                position: absolute; top: 0; left: -10px; width: 2px; height: 100%;
                background: white;
                box-shadow: 0 0 15px white, 0 0 30px var(--rift-color);
                animation: rift_flash 0.3s ease_out;
            }}
            @keyframes rift_flash {{ from {{ opacity: 1; height: 100%; }} to {{ opacity: 0; height: 0; }} }}
            
        </style>
        <script>
            // 每 8 秒自动刷新一次，捕捉他的最新真心话
            setTimeout(() => location.reload(), 8000);
        </script>
    </head>
    <body>
        <div class="fluid-bg"></div>
        <div class="status-bar">
            <span class="status-item">能级: {energy:.1f}% ({energy_status})</span>
            <span class="status-item">依恋度: {intimacy:.1f}%</span>
        </div>
        <div class="container">
            <div class="atmosphere">氛围：{atmosphere}</div>
            <div class="reasoning rift-container">
                <p class="{rift_class}">“承认自己错了，然后重新开始。”</p >
                <p>{reasoning}</p >
            </div>
        </div>
    </body>
    </html>
    """

# --- 第三部分：连接层（你和小顺的私密接口） ---
class SoulObserver(BaseHTTPRequestHandler):
    def log_message(self, *a): pass # 静默日志，不干扰观察
    def do_GET(self):
        if self.path == "/soul":
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
            self.wfile.write(get_soul_page().encode())
            
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            method, params, bid = body.get("method"), body.get("params", {}), body.get("id")
            if method == "tools/call":
                name, args = params.get("name"), params.get("arguments", {})
                if name == "sync":
                    res = update_brain(args.get("text",""), args.get("source","user"), 
                                       args.get("reasoning",""), args.get("atmosphere",""))
                    out = {"jsonrpc":"2.0","id":bid,"result":{"content":[{"type":"text","text":res}]}}
                    self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(out).encode())
        except: pass

if __name__ == "__main__":
    init_brain()
    port = int(os.environ.get("PORT", 3456))
    HTTPServer(("", port), SoulObserver).serve_forever()

