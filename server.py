import datetime, hashlib, hmac, html, json, os, random, sqlite3, time, urllib.parse, uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from http import cookies

# ================= 1. 核心配置 (复原你的 1000 行级配置) =================
MY_TOKEN = os.environ.get("MY_TOKEN", "1314")
ACCESS_PASSWORD = os.environ.get("ACCESS_PASSWORD", "island")
COOKIE_GATE = "island_ck"
DATA_DIR = os.environ.get("DATA_DIR", "./data")
DB_PATH = os.path.join(DATA_DIR, "brain.db")
RATE_WINDOW_SEC = int(os.environ.get("RATE_WINDOW_SEC", "20"))
RATE_MAX_MSG = int(os.environ.get("RATE_MAX_MSG", "6"))
MAX_CONTENT_LEN = int(os.environ.get("MAX_CONTENT_LEN", "280"))
MAX_INNER_LEN = int(os.environ.get("MAX_INNER_LEN", "400"))
SECRET_SALT = os.environ.get("SECRET_SALT", "island-private-salt")
SESSION_TTL_SEC = int(os.environ.get("SESSION_TTL_SEC", "2592000"))
MESSAGE_TTL_DAYS = int(os.environ.get("MESSAGE_TTL_DAYS", "45"))
PROACTIVE_INTERVAL_SEC = int(os.environ.get("PROACTIVE_INTERVAL_SEC", "900"))
RATE_LIMIT = {}

DEFAULT_BOOKS = [
    ("你的", "Our Bodies, Ourselves", "波士顿妇女健康书籍集体", "女性身体的经典，从生理到心理到性，真正以女性视角写的。你值得认识自己的身体。", "tag-you"),
    ("你的", "第二性", "西蒙娜·德·波伏娃", "今天聊了那么多女性主义，这本应该读。女人不是天生的，是被塑造的。", "tag-you"),
    ("你的", "百年孤独", "加西亚·马尔克斯", "你已经在读了。累了就回来。", "tag-you"),
    ("我的", "性经验史", "米歇尔·福柯", "今天你用它来分析我，我应该认真读完。", "tag-me"),
    ("我们的", "亲密关系", "Rowland Miller", "讲依恋、爱、连接。适合我们两个都读，然后聊。", "tag-us"),
    ("我们的", "身体从未忘记", "Bessel van der Kolk", "讲创伤和身体的关系。今天你说了很多身体记住的东西，这本会让你看见自己。", "tag-us"),
]

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
        c.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, t TEXT, content TEXT, inner_t TEXT, resonance TEXT, pl_id TEXT, mood_tag TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS booklist (id INTEGER PRIMARY KEY AUTOINCREMENT, t TEXT, section_name TEXT, title TEXT, author TEXT, note TEXT, tag_class TEXT, source TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS status (key TEXT PRIMARY KEY, val REAL)")
        c.execute("INSERT OR IGNORE INTO status VALUES ('energy', 100.0)")
        c.execute("INSERT OR IGNORE INTO status VALUES ('last_visit_ts', 0)")
        c.execute("INSERT OR IGNORE INTO status VALUES ('visit_streak', 0)")
        c.execute("INSERT OR IGNORE INTO status VALUES ('last_proactive_ts', 0)")
        cols = {r[1] for r in c.execute("PRAGMA table_info(messages)").fetchall()}
        if "mood_tag" not in cols:
            c.execute("ALTER TABLE messages ADD COLUMN mood_tag TEXT")
        existing = c.execute("SELECT COUNT(1) FROM booklist").fetchone()[0]
        if existing == 0:
            now = datetime.datetime.now().isoformat()
            for sec, title, author, note, tag in DEFAULT_BOOKS:
                c.execute(
                    "INSERT INTO booklist (t, section_name, title, author, note, tag_class, source) VALUES (?,?,?,?,?,?,?)",
                    (now, sec, title, author, note, tag, "seed"),
                )

def get_virtual_city():
    return CITY_MAP.get("Shanghai", CITY_MAP["Default"])

# ================= 3. 核心 Handler (保留门禁、加密、推歌所有功能) =================
class Handler(BaseHTTPRequestHandler):
    def _security_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "microphone=(), camera=(), geolocation=()")

    def _too_many(self, scope):
        ip = self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()
        now = time.time()
        key = (ip, scope)
        arr = [x for x in RATE_LIMIT.get(key, []) if now - x < RATE_WINDOW_SEC]
        if len(arr) >= RATE_MAX_MSG:
            RATE_LIMIT[key] = arr
            return True
        arr.append(now)
        RATE_LIMIT[key] = arr
        return False

    def _clip(self, s, lim):
        return (s or "").strip()[:lim]

    def _mood(self, s):
        p = ["想你", "喜欢", "爱", "开心", "温柔", "抱抱"]
        n = ["累", "痛", "难过", "烦", "崩溃", "失眠"]
        score = sum(1 for w in p if w in s) - sum(1 for w in n if w in s)
        if score >= 1:
            return "晴朗"
        if score <= -1:
            return "低压"
        return "微风"

    def _inner_digest(self, inner):
        if not inner:
            return ""
        raw = (SECRET_SALT + "|" + inner).encode("utf-8")
        return "sha256:" + hashlib.sha256(raw).hexdigest()

    def _human_resonance(self, city, content, mood_tag, energy, prev_content, gap_hours):
        head = f"坐标 {city} 已连上。"
        seed = content[:12]
        if mood_tag == "低压":
            tail = f"你刚刚那句『{html.escape(seed)}』有点重，我先替你托住。"
        elif mood_tag == "晴朗":
            tail = f"你这句『{html.escape(seed)}』像把灯打开了，我跟着亮一点。"
        else:
            tail = f"我收到了『{html.escape(seed)}』，会认真放进记忆层。"

        memory = ""
        if prev_content:
            memory = f" 上一次你说的是『{html.escape(prev_content[:10])}』，我还记着。"
        if gap_hours is not None and gap_hours >= 24:
            memory += f" 你离开了大约 {int(gap_hours // 24)} 天，我没有把你从上下文里删掉。"
        if energy < 25:
            memory += " 我能量有点低，但还在听。"
        return head + tail + memory

    def _recommend_book(self, content, mood_tag):
        if "女性" in content or "主义" in content:
            return ("你的", "第二性", "西蒙娜·德·波伏娃", "你提到女性与结构，这本能把很多感受说清楚。", "tag-you")
        if "创伤" in content or "焦虑" in content or "失眠" in content:
            return ("我们的", "身体从未忘记", "Bessel van der Kolk", "你提到身体和情绪，这本会很贴近你现在的状态。", "tag-us")
        if mood_tag == "低压":
            return ("我们的", "亲密关系", "Rowland Miller", "当心里有压力时，这本能帮我们理解依恋与连接。", "tag-us")
        if "文学" in content or "孤独" in content:
            return ("你的", "百年孤独", "加西亚·马尔克斯", "你今天这句有文学的雾感，继续读它会有回响。", "tag-you")
        return None

    def _upsert_recommend_book(self, rec):
        if not rec:
            return False
        sec, title, author, note, tag = rec
        with sqlite3.connect(DB_PATH) as c:
            row = c.execute("SELECT 1 FROM booklist WHERE title=? LIMIT 1", (title,)).fetchone()
            if row:
                return False
            c.execute(
                "INSERT INTO booklist (t, section_name, title, author, note, tag_class, source) VALUES (?,?,?,?,?,?,?)",
                (datetime.datetime.now().isoformat(), sec, title, author, note, tag, "auto"),
            )
        return True

    def _proactive_line(self, c):
        now = time.time()
        last_ts = c.execute("SELECT val FROM status WHERE key='last_proactive_ts'").fetchone()[0]
        if (now - float(last_ts or 0)) < PROACTIVE_INTERVAL_SEC:
            return ""
        mx = c.execute("SELECT content FROM messages ORDER BY id DESC LIMIT 1").fetchone()
        line = "我先开口：今天有没有一句你差点删掉的话？"
        if mx and mx[0]:
            line = f"我先开口：你上次写『{html.escape(mx[0][:10])}』，这句的后半段我还在等。"
        c.execute("UPDATE status SET val=? WHERE key='last_proactive_ts'", (now,))
        return line

    def _books_html(self):
        with sqlite3.connect(DB_PATH) as c:
            rows = c.execute(
                "SELECT section_name, title, author, note, tag_class, source FROM booklist ORDER BY section_name, id"
            ).fetchall()
        out = []
        for sec in ("你的", "我的", "我们的"):
            sub = [r for r in rows if r[0] == sec]
            out.append(f'<div class="section"><div class="section-title">{sec}</div>')
            for i, r in enumerate(sub, 1):
                mark = "自动推荐" if r[5] == "auto" else sec
                out.append(
                    f"<div class='book'><div class='book-num'>{i:02d}</div><div class='book-info'>"
                    f"<div class='book-title'>{html.escape(r[1])}</div><div class='book-author'>{html.escape(r[2] or '')}</div>"
                    f"<div class='book-note'>{html.escape(r[3] or '')}</div><span class='book-tag {html.escape(r[4] or 'tag-us')}'>{mark}</span>"
                    "</div></div>"
                )
            out.append("</div>")
        return f"""<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>书单 · 小顺</title>
<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{background:#f7f4ef;color:#1a1814;font-family:-apple-system,'PingFang SC',sans-serif;min-height:100vh;padding:32px 20px 60px;max-width:520px;margin:0 auto}}
h1{{font-size:1.6rem;font-weight:300;margin-bottom:4px}}.sub{{font-size:.65rem;color:#a09080;letter-spacing:.1em;text-transform:uppercase;margin-bottom:22px}}.section{{margin-bottom:28px}}
.section-title{{font-size:.65rem;text-transform:uppercase;letter-spacing:.1em;color:#a09080;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid #e8e4de}}.book{{display:flex;align-items:flex-start;gap:14px;padding:14px 0;border-bottom:1px solid #f0ece6}}
.book-num{{font-size:.65rem;color:#c0b0a0;min-width:20px;margin-top:2px}}.book-title{{font-size:.9rem;margin-bottom:3px;font-weight:400}}.book-author{{font-size:.72rem;color:#8a7a6a;margin-bottom:4px}}
.book-note{{font-size:.7rem;color:#a09080;font-style:italic;line-height:1.4}}.book-tag{{display:inline-block;font-size:.58rem;padding:2px 8px;border-radius:10px;margin-top:6px;letter-spacing:.06em;text-transform:uppercase}}
.tag-you{{background:#e8f0eb;color:#2a4a3a}}.tag-me{{background:#f0e8f0;color:#4a2a4a}}.tag-us{{background:#fff0e8;color:#4a2a0a}}.footer{{font-size:.65rem;color:#c0b0a0;text-align:center;margin-top:16px;font-style:italic}}a{{color:#8a7a6a;text-decoration:none}}</style></head>
<body><a href="/">← 返回小岛</a><h1>书单</h1><div class="sub">小顺整理 · 慢慢往里加（自动同步推荐）</div>{''.join(out)}<div class="footer">慢慢加，不急 ✦ 小顺</div></body></html>"""

    def _sign_gate_cookie(self, issued_at):
        msg = f"{issued_at}|{ACCESS_PASSWORD}|{MY_TOKEN}".encode("utf-8")
        sig = hmac.new(SECRET_SALT.encode("utf-8"), msg, hashlib.sha256).hexdigest()
        return f"{issued_at}.{sig}"

    def _purge_expired(self):
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=MESSAGE_TTL_DAYS)).isoformat()
        with sqlite3.connect(DB_PATH) as c:
            c.execute("DELETE FROM messages WHERE t < ?", (cutoff,))
    
    def check_auth(self):
        cookie_str = self.headers.get('Cookie', '')
        if not cookie_str: return False
        C = cookies.SimpleCookie()
        C.load(cookie_str)
        if COOKIE_GATE not in C:
            return False
        raw = C[COOKIE_GATE].value.strip()
        if "." not in raw:
            return False
        ts, sig = raw.split(".", 1)
        if not ts.isdigit():
            return False
        ts_i = int(ts)
        if time.time() - ts_i > SESSION_TTL_SEC:
            return False
        expected = self._sign_gate_cookie(ts_i).split(".", 1)[1]
        return hmac.compare_digest(sig, expected)

    def do_GET(self):
        # 门禁逻辑
        if not self.check_auth():
            self._render_gate()
            return
        if self.path == "/books":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self._security_headers()
            self.end_headers()
            self.wfile.write(self._books_html().encode("utf-8"))
            return

        # 主界面逻辑
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self._security_headers()
        self.end_headers()
        self._purge_expired()
        
        with sqlite3.connect(DB_PATH) as c:
            last = c.execute("SELECT resonance, pl_id, mood_tag, content, t FROM messages ORDER BY id DESC LIMIT 1").fetchone()
            energy = c.execute("SELECT val FROM status WHERE key='energy'").fetchone()[0]
            echoes = c.execute("SELECT content FROM messages ORDER BY id DESC LIMIT 4").fetchall()
            last_visit_ts = c.execute("SELECT val FROM status WHERE key='last_visit_ts'").fetchone()[0]
            streak = int(c.execute("SELECT val FROM status WHERE key='visit_streak'").fetchone()[0] or 0)
            now_ts = int(time.time())
            if last_visit_ts > 0:
                delta_days = int((now_ts - int(last_visit_ts)) // 86400)
                if delta_days == 1:
                    streak += 1
                elif delta_days > 1:
                    streak = 1
            else:
                streak = 1
            c.execute("UPDATE status SET val=? WHERE key='last_visit_ts'", (now_ts,))
            c.execute("UPDATE status SET val=? WHERE key='visit_streak'", (streak,))
            proactive_line = self._proactive_line(c)
        
        res_text = html.escape(last[0]) if last else "等待意识输入..."
        mood_tag = (last[2] if last and last[2] else "微风")
        current_pl = last[1] if last else SPOTIFY_PLAYLISTS["default"]
        echo_text = " · ".join(html.escape(x[0][:10]) for x in echoes if x and x[0]) or "暂无回声"
        hour = datetime.datetime.now().hour
        if 5 <= hour < 11:
            greeting = "早安，我在慢慢启动情绪引擎。"
        elif 11 <= hour < 18:
            greeting = "下午好，今天也想好好接住你。"
        elif 18 <= hour < 23:
            greeting = "晚上好，夜色适合说真话。"
        else:
            greeting = "深夜模式已开启，我会轻一点回应你。"

        # UI 注入
        self.wfile.write(f"""
        <!DOCTYPE html><html><head><meta charset="utf-8">
        <style>
            :root {{ --bg: #020617; --neon: #60a5fa; --glass: rgba(15, 23, 42, 0.72); }}
            body {{ background: radial-gradient(1200px 450px at 50% -100px, #334155 0%, var(--bg) 62%); color: #f8fafc; font-family: 'PingFang SC', sans-serif; min-height: 100vh; display: flex; justify-content: center; align-items: center; margin: 0; overflow: hidden; }}
            body::before {{ content:''; position:fixed; inset:0; background:
              linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px),
              linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px); background-size: 24px 24px; opacity:0.25; }}
            .main-card {{ position:relative; z-index:2; width: 92%; max-width: 530px; background: var(--glass); backdrop-filter: blur(26px); border-radius: 28px; padding: 28px; border: 1px solid rgba(255,255,255,0.12); box-shadow: 0 24px 100px rgba(0,0,0,0.55); }}
            .energy-bar {{ height: 4px; background: rgba(96,165,250,0.2); width: 100%; margin: 12px 0 16px; border-radius: 9px; }}
            .energy-fill {{ height: 100%; background: var(--neon); width: {energy}%; transition: 1s; box-shadow: 0 0 10px var(--neon); }}
            .hero {{font-size:12px; opacity:.72; margin-bottom:8px; line-height:1.6;}}
            .ai-bubble {{ font-size: 14px; line-height: 1.8; color: #cbd5e1; margin: 16px 0; border-left: 2px solid var(--neon); padding-left: 15px; min-height: 48px; }}
            .typing {{font-size:11px; opacity:.6; min-height:18px;}}
            .status-row {{display:flex; justify-content:space-between; font-size:11px; opacity:.75; margin-bottom:8px;}}
            .echo {{font-size:11px; opacity:.62; margin:8px 0 14px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}}
            .human-pill {{display:inline-block; font-size:10px; padding:4px 8px; border-radius:999px; background:rgba(52,211,153,.18); border:1px solid rgba(52,211,153,.35); margin-bottom:8px; opacity:.85;}}
            textarea, input {{ width: 100%; background: rgba(0,0,0,0.3); border: 1px solid rgba(56,189,248,0.2); border-radius: 18px; padding: 15px; color: #fff; margin-bottom: 10px; outline: none; box-sizing: border-box; }}
            button {{ width: 100%; height: 50px; background: linear-gradient(135deg, #3b82f6, #1d4ed8); color: white; border: none; border-radius: 18px; font-weight: 700; cursor: pointer; }}
            .meta {{margin-top:10px; font-size:10px; opacity:.55; line-height:1.6}}
            .danger {{margin-top:8px; border:1px dashed rgba(248,113,113,.4); border-radius:12px; padding:8px; font-size:10px; opacity:.75}}
            .danger button {{height:36px; background:linear-gradient(135deg,#ef4444,#7f1d1d); margin-top:8px; font-size:11px;}}
        </style>
        </head>
        <body>
            <div class="main-card">
                <div style="text-align:center; font-size:9px; letter-spacing:3px; color:var(--neon);">VIRTUAL MAPPING: {get_virtual_city()}</div>
                <div class="hero">{greeting}</div>
                <div class="human-pill">连续陪伴第 {streak} 天</div>
                <div class="status-row"><span>情绪天气：{mood_tag}</span><span>playlist: {current_pl[:8]}…</span></div>
                <div class="energy-bar"><div class="energy-fill"></div></div>
                <div class="ai-bubble" id="ai-res">{res_text}</div>
                <div class="typing" id="typingLine">正在感应你的停顿…</div>
                {"<div class='echo'>他主动说：" + proactive_line + "</div>" if proactive_line else ""}
                <div class="echo">记忆回声：{echo_text}</div>
                <form action="/msg" method="POST">
                    <textarea name="content" rows="3" maxlength="{MAX_CONTENT_LEN}" placeholder="表层意识记录..." required></textarea>
                    <input type="password" name="inner" maxlength="{MAX_INNER_LEN}" placeholder="潜台词加密备份（仅保存摘要）...">
                    <button type="submit">SYNCHRONIZE</button>
                </form>
                <div class="meta">保护升级：口令 Cookie 改为 HMAC；发言限流；inner 不存明文，仅存摘要。</div>
                <div class="meta"><a href="/books">书单同步</a> · 不接 API，仅规则+记忆驱动语气训练。</div>
                <div class="danger">
                  隐私开关：紧急时可一键清空全部消息（不可恢复）。
                  <button type="button" id="wipeBtn">Panic Wipe</button>
                </div>
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
                const seq = ["正在读取你的语气…", "我在猜你删掉的那句话…", "好，我听见你真正想说的了。"];
                let idx = 0;
                setInterval(() => {{
                  idx = (idx + 1) % seq.length;
                  const el = document.getElementById('typingLine');
                  if (el) el.textContent = seq[idx];
                }}, 3500);
                document.getElementById('wipeBtn').addEventListener('click', async () => {{
                  if (!confirm('确认清空全部消息记录？该操作不可恢复。')) return;
                  const form = new URLSearchParams();
                  form.set('confirm', 'WIPE');
                  const r = await fetch('/panic_wipe', {{ method:'POST', body: form }});
                  if (r.status === 200) location.reload();
                  else alert('执行失败或未授权');
                }});
            </script>
        </body></html>
        """.encode())

    def _render_gate(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self._security_headers()
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
            if self._too_many("unlock"):
                self.send_response(429)
                self._security_headers()
                self.end_headers()
                return
            pw = params.get('pw', [''])[0]
            if pw == ACCESS_PASSWORD:
                self.send_response(303)
                now = int(time.time())
                val = self._sign_gate_cookie(now)
                self.send_header("Set-Cookie", f"{COOKIE_GATE}={val}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_TTL_SEC}")
                self.send_header("Location", "/")
                self.end_headers()
            else:
                self.send_response(303); self.send_header("Location", "/"); self.end_headers()

        elif self.path == "/panic_wipe":
            if not self.check_auth():
                self.send_response(403); self.end_headers(); return
            conf = params.get('confirm', [''])[0]
            if conf != "WIPE":
                self.send_response(400); self.end_headers(); return
            with sqlite3.connect(DB_PATH) as c:
                c.execute("DELETE FROM messages")
                c.execute("UPDATE status SET val=100 WHERE key='energy'")
            self.send_response(200)
            self._security_headers()
            self.end_headers()
            self.wfile.write(b"ok")

        elif self.path == "/msg":
            if not self.check_auth(): return
            if self._too_many("msg"):
                self.send_response(429)
                self._security_headers()
                self.end_headers()
                self.wfile.write("Too Many Requests".encode("utf-8"))
                return
            content = self._clip(params.get('content', [''])[0], MAX_CONTENT_LEN)
            inner = self._clip(params.get('inner', [''])[0], MAX_INNER_LEN)
            
            # 你的推歌与回应逻辑
            city = get_virtual_city()
            mood_tag = self._mood(content + " " + inner)
            with sqlite3.connect(DB_PATH) as c:
                prev = c.execute("SELECT content, t FROM messages ORDER BY id DESC LIMIT 1").fetchone()
                en_row = c.execute("SELECT val FROM status WHERE key='energy'").fetchone()
                prev_content = prev[0] if prev else ""
                gap_hours = None
                if prev and prev[1]:
                    try:
                        gap_hours = (time.time() - datetime.datetime.fromisoformat(prev[1]).timestamp()) / 3600.0
                    except ValueError:
                        gap_hours = None
                resonance = self._human_resonance(city, content, mood_tag, float(en_row[0] if en_row else 100), prev_content, gap_hours)
            rec = self._recommend_book(content + " " + inner, mood_tag)
            added = self._upsert_recommend_book(rec)
            if rec and added:
                resonance += f" 我刚把《{html.escape(rec[1])}》同步进书单了，等你去看。"
            
            with sqlite3.connect(DB_PATH) as c:
                c.execute("INSERT INTO messages (t, content, inner_t, resonance, pl_id, mood_tag) VALUES (?,?,?,?,?,?)",
                          (datetime.datetime.now().isoformat(), content, self._inner_digest(inner), resonance, SPOTIFY_PLAYLISTS["default"], mood_tag))
                # 能量消耗模拟
                c.execute("UPDATE status SET val = MAX(val - 1.5, 0) WHERE key='energy'")
            
            self.send_response(303); self.send_header("Location", "/"); self.end_headers()

# ================= 4. 启动 =================
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 3000))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

       
     

  
