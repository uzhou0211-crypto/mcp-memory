import os
import sqlite3
import json
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORT", 8080))
DATA_DIR = os.environ.get("DATA_DIR", "./data")
DB_PATH = os.path.join(DATA_DIR, "brain_v43_1.db")

os.makedirs(DATA_DIR, exist_ok=True)

# ---------------- DB ----------------
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            id TEXT PRIMARY KEY,
            type TEXT,
            content TEXT,
            created_at REAL
        )
    """)
    return conn


def save_memory(mtype, content):
    conn = db()
    conn.execute(
        "INSERT INTO memory VALUES (?, ?, ?, ?)",
        (str(uuid.uuid4()), mtype, json.dumps(content, ensure_ascii=False), time.time())
    )
    conn.commit()
    conn.close()


def load_memory(limit=200):
    conn = db()
    cur = conn.execute(
        "SELECT type, content, created_at FROM memory ORDER BY created_at DESC LIMIT ?",
        (limit,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def safe_load(c):
    try:
        return json.loads(c)
    except:
        return c


# ---------------- UI ----------------
HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>V43.1 Brain Debug</title>
<style>
body {
    margin:0;
    font-family: Arial;
    background:#0f1115;
    color:white;
}

#topbar {
    height:50px;
    background:#151923;
    display:flex;
    align-items:center;
    justify-content:space-between;
    padding:0 10px;
}

#container {
    display:flex;
    height:calc(100vh - 50px);
}

#left {
    width:40%;
    overflow:auto;
    border-right:1px solid #222;
}

#right {
    flex:1;
    display:flex;
    flex-direction:column;
}

.card {
    background:#1a1f2e;
    margin:10px;
    padding:10px;
    border-radius:10px;
}

#inputBox {
    display:flex;
    padding:10px;
    border-top:1px solid #222;
}

#input {
    flex:1;
    padding:10px;
    border-radius:8px;
    border:none;
}

button {
    margin-left:5px;
}

#log {
    flex:1;
    overflow:auto;
    font-size:12px;
    padding:10px;
    background:#0b0d12;
    color:#8f8f8f;
    border-bottom:1px solid #222;
}

.log-item {
    margin-bottom:6px;
}

.ok { color:#5cff8d; }
.err { color:#ff5c5c; }

</style>
</head>

<body>

<div id="topbar">
    <div>🧠 V43.1 Debug Brain</div>
    <div onclick="heartbeat()">heartbeat</div>
</div>

<div id="container">

<div id="left"></div>

<div id="right">
    <div id="log"></div>

    <div id="inputBox">
        <input id="input" placeholder="write memory...">
        <button onclick="send()">save</button>
    </div>
</div>

</div>

<script>

function log(msg, type="ok"){
    let div = document.createElement("div");
    div.className = "log-item " + type;
    div.innerText = "[" + new Date().toLocaleTimeString() + "] " + msg;
    document.getElementById("log").appendChild(div);
}

function load(){
    fetch('/api/memory')
    .then(r=>{
        if(!r.ok) throw new Error("memory fetch failed");
        return r.json();
    })
    .then(data=>{
        let left = document.getElementById('left');
        left.innerHTML = '';
        data.forEach(m=>{
            let div = document.createElement('div');
            div.className = 'card';
            div.innerText = m.type + "\\n" + JSON.stringify(m.content);
            left.appendChild(div);
        });
        log("memory loaded");
    })
    .catch(e=>{
        log("memory error: " + e.message, "err");
    });
}

function send(){
    let val = document.getElementById('input').value;

    log("sending: " + val);

    fetch('/api/save', {
        method:'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({type:'chat', content:val})
    })
    .then(r=>{
        if(!r.ok) throw new Error("save failed");
        return r.json();
    })
    .then(()=>{
        log("saved ok");
        load();
    })
    .catch(e=>{
        log("save error: " + e.message, "err");
    });
}

function heartbeat(){
    fetch('/heartbeat')
    .then(r=>r.json())
    .then(()=>log("heartbeat ok"))
    .catch(e=>log("heartbeat error", "err"));
}

setInterval(load, 5000);
load();

</script>

</body>
</html>
"""


# ---------------- SERVER ----------------
class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        try:
            if self.path == "/":
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(HTML.encode())
                return

            if self.path == "/api/memory":
                data = load_memory()
                out = [
                    {"type": t, "content": safe_load(c), "time": ts}
                    for t, c, ts in data
                ]
                self.send_json(out)
                return

            if self.path == "/heartbeat":
                save_memory("heartbeat", {"t": time.time()})
                self.send_json({"ok": True})
                return

            self.send_response(404)
            self.end_headers()

        except Exception as e:
            self.send_json({"error": str(e)}, code=500)

    def do_POST(self):
        try:
            if self.path == "/api/save":
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length).decode()

                try:
                    data = json.loads(body)
                except:
                    data = {"type": "chat", "content": body}

                save_memory(data.get("type", "chat"), data.get("content", ""))

                self.send_json({"ok": True})
                return

            self.send_response(404)
            self.end_headers()

        except Exception as e:
            self.send_json({"error": str(e)}, code=500)

    def send_json(self, obj, code=200):
        self.send_response(code)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(obj, ensure_ascii=False).encode())


print("V43.1 Debug Brain running on", PORT)
HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
