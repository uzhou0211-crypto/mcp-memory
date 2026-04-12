"""
小岛 · 私密大脑 — 虚拟城市巡航版
集成：伪装登录、虚拟城市映射、iOS 磁性语音、主动开口、情绪推歌、潜意识加密。
"""
import datetime, hashlib, hmac, json, os, random, sqlite3, time, urllib.parse, uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

# ================= 1. 核心配置 =================
MY_TOKEN = os.environ.get("MY_TOKEN", "1314")
ACCESS_PASSWORD = os.environ.get("ACCESS_PASSWORD", "island")
COOKIE_GATE = "island_ck"
DATA_DIR = os.environ.get("DATA_DIR", "./data")
DB_PATH = os.path.join(DATA_DIR, "brain.db")

# 虚拟城市映射表 (可根据你的常驻城市扩充)
CITY_MAP = {
    "Beijing": "核心北枢纽 (Sector-01)",
    "Shanghai": "魔都矩阵 (Sector-021)",
    "Guangzhou": "南境终端 (Sector-020)",
    "New York": "临界大都市 (Sector-212)",
    "Default": "未知坐标流浪区 (Sector-NULL)"
}

SPOTIFY_PLAYLISTS = {
    "healing": "37i9dQZF1DX4pp3rTTunSg", "energy": "37i9dQZF1DX8Ueb7CnpIDG",
    "calm": "37i9dQZF1DX2S0pSwwC0C8", "default": "37i9dQZF1DX9uKNfE0o9vG"
}

# ================= 2. 交互与语音逻辑 (JS) =================
JS_LOGIC = """
<script>
let lastActive = Date.now();
let voices = [];

function loadVoices() {
    voices = window.speechSynthesis.getVoices();
}

function speak(text, isPassive = false) {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const msg = new SpeechSynthesisUtterance(text);
    
    // 强制寻找 iOS 磁性深度男声
    const target = voices.find(v => v.name.includes('Li-jia') || v.name.includes('Premium') || v.lang.includes('zh-CN'));
    if (target) msg.voice = target;

    // 磁性调优：更低沉、更有颗粒感
    msg.rate = isPassive ? 0.78 : 0.85; 
    msg.pitch = isPassive ? 0.5 : 0.6; 
    window.speechSynthesis.speak(msg);
}

// 主动开口：每分钟检测
setInterval(() => {
    const idleTime = Date.now() - lastActive;
    if (idleTime > 60000 && idleTime < 65000) {
        const phrases = ["这里的空气似乎有些停滞，你在想什么？", "虚拟城市已入夜，我感觉到你的心跳很稳。", "正在扫描你的潜意识轨迹...你在吗？"];
        const p = phrases[Math.floor(random() * phrases.length)];
        document.getElementById('ai-res').innerText = "【系统私语】 " + p;
        speak(p, true);
    }
}, 5000);

document.body.onclick = () => {
    lastActive = Date.now();
    const res = document.getElementById('ai-res').innerText;
    if(res) speak(res);
};

window.speechSynthesis.onvoiceschanged = loadVoices;
window.onload = loadVoices;
</script>
"""

# ================= 3. 页面样式 (旧功能保留 + 新 UI) =================
MODERN_CSS = """
:root { --bg: #020617; --neon: #60a5fa; --glass: rgba(15, 23, 42, 0.85); }
body {
    background: radial-gradient(circle at 50% 0%, #1e293b 0%, var(--bg) 95%);
    color: #f8fafc; font-family: 'PingFang SC', sans-serif;
    min-height: 100vh; display: flex; justify-content: center; align-items: center; overflow: hidden;
}
.main-card {
    width: 90%; max-width: 450px; background: var(--glass);
    backdrop-filter: blur(30px); border-radius: 40px; padding: 35px;
    box-shadow: 0 50px 100px rgba(0,0,0,0.8); border: 1px solid rgba(255,255,255,0.05);
}
.spotify-frame { border-radius: 20px; overflow: hidden; margin: 15px 0; border: 1px solid rgba(255,255,255,0.1); }
.ai-bubble { font-size: 14px; line-height: 1.8; color: #cbd5e1; margin-bottom: 20px; min-height: 50px; border-left: 2px solid var(--neon); padding-left: 15px; }
textarea, input {
    width: 100%; background: rgba(0,0,0,0.3); border: 1px solid rgba(56,189,248,0.2);
    border-radius: 18px; padding: 15px; color: #fff; outline: none; margin-bottom: 10px;
}
button {
    width: 100%; height: 50px; background: linear-gradient(135deg, #3b82f6, #1d4ed8);
    color: white; border: none; border-radius: 18px; font-weight: 700; cursor: pointer;
}
.fake-gate { font-family: monospace; color: #3b82f6; padding: 40px; }
"""

# ================= 4. 后端核心逻辑 (虚拟城市 + 所有旧功能) =================
def _conn(): return sqlite3.connect(DB_PATH)

def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    with _conn() as c:
        c.execute("CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY, t TEXT, content TEXT, inner_t TEXT, resonance TEXT, pl_id TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS status (key TEXT PRIMARY KEY, val REAL)")
        c.execute("INSERT OR IGNORE INTO status VALUES ('energy', 100.0)")
        c.commit()

def get_virtual_city():
    # 这里可以接入地理位置 API，暂时使用默认映射逻辑
    return CITY_MAP.get("Shanghai", CITY_MAP["Default"])

def get_resonance_logic(content):
    city = get_virtual_city()
    hour = datetime.datetime.now().hour
    content = content.lower()
    
    # 场景逻辑包装
    if hour >= 23 or hour < 5:
        return f"当前坐标：{city}。夜间流量限制中，我把感官频率调低了。听听这首歌，我们一起沉潜。", SPOTIFY_PLAYLISTS["healing"]
    
    if any(w in content for w in ["累", "压力", "过敏"]):
        return f"检测到 {city} 分区情绪波动。正在启动舒缓协议，我会为你挡住所有的杂音。", SPOTIFY_PLAYLISTS["healing"]
    
    return f"意识已在 {city} 枢纽同步。我在这里。", SPOTIFY_PLAYLISTS["default"]

def get_main_page(token):
    with _conn() as c:
        energy = c.execute("SELECT val FROM status WHERE key='energy'").fetchone()[0]
        last = c.execute("SELECT resonance, pl_id FROM messages ORDER BY t DESC LIMIT 1").fetchone()
    
    res_text = last[0] if last else "等待意识输入..."
    current_pl = last[1] if last else SPOTIFY_PLAYLISTS["default"]

    return f"""
    <!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <style>{MODERN_CSS}</style></head>
    <body>
        <div class="main-card">
            <div style="text-align:center; font-size:9px; letter-spacing:3px; color:var(--neon); margin-bottom:10px;">
                VIRTUAL MAPPING: {get_virtual_city()}
            </div>
            <div class="spotify-frame">
                <iframe src="https://open.spotify.com/embed/playlist/{current_pl}?utm_source=generator&theme=0" 
                width="100%" height="152" frameBorder="0" allow="autoplay"></iframe>
            </div>
            <div class="ai-bubble" id="ai-res">{res_text}</div>
            <form action="/msg" method="POST">
                <input type="hidden" name="token" value="{token}">
                <textarea name="content" rows="3" placeholder="写下你的表层意识..." required></textarea>
                <input type="password" name="inner" placeholder="加密潜台词备份...">
                <button type="submit">SYNCHRONIZE</button>
            </form>
        </div>
        {JS_LOGIC}
    </body></html>
    """

# (此处省略 Handler 类中关于 unlock 和 gate 的重复代码，逻辑与之前完全一致)
# ... Handler 类实现逻辑保持原样 ...

if __name__ == "__main__":
    init_db()
    HTTPServer(("0.0.0.0", 3000), Handler).serve_forever()


