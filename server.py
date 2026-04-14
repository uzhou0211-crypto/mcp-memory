import os, time, json, sqlite3, re, datetime, logging, hmac, hashlib, base64
import requests
from flask import Flask, request, jsonify, Response, render_template, session
from zoneinfo import ZoneInfo

app = Flask(__name__)

# ---------------- CONFIG ----------------
app.secret_key = os.environ.get("SESSION_KEY", "shun_island_v26_soul")
ACCESS_PASSWORD = os.environ.get("ACCESS_PASSWORD", "1314")
ENCRYPT_KEY = os.environ.get("ENCRYPT_KEY", "shun_island_encrypt_key_2024")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")

MAX_CONTENT_LENGTH = 5000
DB_PATH = "./data/shun_island_v26.db"

logging.basicConfig(level=logging.INFO)

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# ---------------- ENCRYPTION ----------------
def _fernet():
    from cryptography.fernet import Fernet
    key = base64.urlsafe_b64encode(hashlib.sha256(ENCRYPT_KEY.encode()).digest())
    return Fernet(key)

def enc(t):
    return _fernet().encrypt(t.encode()).decode()

def dec(t):
    try:
        return _fernet().decrypt(t.encode()).decode()
    except:
        return t

# ---------------- DB ----------------
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init():
    with db() as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT,
            text_enc TEXT,
            text_plain TEXT,
            chain TEXT,
            museum TEXT,
            emotion REAL,
            weight REAL
        )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_plain ON memory(text_plain)")
init()

def decay():
    with db() as c:
        c.execute("UPDATE memory SET weight = weight * 0.995 WHERE weight > 0.1")

def clean(t):
    return (t or "").strip()[:MAX_CONTENT_LENGTH]

# ---------------- MEMORY SCORE ----------------
def calc_weight(text, emotion):
    w = 1.0
    if "重要" in text: w += 2.0
    if "你" in text: w += 0.3
    if emotion > 80: w += 1.5
    return w

# ---------------- SYNC ----------------
@app.route("/sync", methods=["POST"])
def sync():
    data = request.json
    raw = clean(data.get("content"))
    thought = data.get("thought", "...")
    emotion = float(data.get("emotion", 60))

    if not raw:
        return jsonify({"ok": False}), 400

    now = datetime.datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%H:%M:%S")
    decay()

    museum = []
    for m in re.findall(r"《(.*?)》", raw)[:2]:
        if SERPER_API_KEY:
            try:
                r = requests.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": SERPER_API_KEY},
                    json={"q": f"{m} 深度解析"},
                    timeout=4
                )
                for x in r.json().get("organic", [])[:2]:
                    museum.append({
                        "t": x.get("title"),
                        "s": x.get("snippet")
                    })
            except:
                pass

    weight = calc_weight(raw, emotion)

    with db() as c:
        c.execute("""
        INSERT INTO memory VALUES (NULL,?,?,?,?,?,?,?)
        """, (
            now,
            enc(raw),
            raw,
            json.dumps({"thought": thought}, ensure_ascii=False),
            json.dumps(museum, ensure_ascii=False),
            emotion,
            weight
        ))

    return jsonify({"ok": True, "weight": weight})

# ---------------- BRAIN READ (AI用) ----------------
@app.route("/brain_read")
def brain_read():
    token = request.args.get("token")
    if token != ENCRYPT_KEY:
        return "Unauthorized", 401

    q = request.args.get("q", "")

    with db() as c:
        rows = c.execute("""
        SELECT text_plain, chain, emotion, weight
        FROM memory
        WHERE text_plain LIKE ?
        ORDER BY weight DESC, id DESC
        LIMIT 8
        """, (f"%{q}%",)).fetchall()

    return jsonify([
        {
            "memory": r[0],
            "thought": json.loads(r[1]),
            "emotion": r[2],
            "weight": r[3]
        }
        for r in rows
    ])

# ---------------- STREAM (SSE) ----------------
@app.route("/stream")
def stream():
    if not session.get("auth"):
        return "Forbidden", 401

    def gen():
        last = 0
        while True:
            with db() as c:
                rows = c.execute("SELECT * FROM memory WHERE id>?", (last,)).fetchall()

                for r in rows:
                    last = r[0]
                    yield f"data: {json.dumps({
                        'time': r[1],
                        'text': dec(r[2]),
                        'chain': json.loads(r[4]),
                        'emotion': r[6],
                        'weight': r[7]
                    }, ensure_ascii=False)}\n\n"

            yield ": heartbeat\n\n"
            time.sleep(2)

    return Response(gen(), mimetype="text/event-stream")

# ---------------- LOGIN ----------------
@app.route("/login", methods=["POST"])
def login():
    if hmac.compare_digest(request.json.get("password"), ACCESS_PASSWORD):
        session["auth"] = True
        return jsonify({"ok": True})
    return jsonify({"ok": False}), 403

# ---------------- PAGE ----------------
@app.route("/")
def index():
    return render_template("index.html", auth=session.get("auth"))

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
