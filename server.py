import os
import sqlite3
import json
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORT", 8000))
DATA_DIR = os.environ.get("DATA_DIR", "./data")
DB_PATH = os.path.join(DATA_DIR, "brain_v43.db")

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
        (str(uuid.uuid4()), mtype, json.dumps(content), time.time())
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


# ---------------- UI ----------------
HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>V43 Brain</title>
<style>
body {
    margin:0;
    font-family: Arial;
    background:#0f1115;
    color:white;
    overflow:hidden;
}

#topbar {
    height:50px;
    background:#151923;
    display:flex;
    align-items:center;
    padding:0 10px;
    justify-content:space-between;
}

#container {
    display:flex;
    height:calc(100vh - 50px);
}

#left {
    width:40%;
    border-right:1px solid #222;
    overflow:auto;
}

#right {
    flex:1;
    position:relative;
}

.card {
    background:#1a1f2e;
    margin:10px;
    padding:10px;
    border-radius:10px;
    cursor:grab;
    position:relative;
}

#inputBox {
    position:absolute;
    bottom:10px;
    left:10px;
    right:10px;
    display:flex;
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

#stream {
    padding:10px;
    height:100%;
    overflow:auto;
    font-size:13px;
    color:#aaa;
}
</style>
</head>

<body>

<div id="topbar">
    <div>🧠 V43 Private Brain</div>
    <div onclick="heartbeat()">heartbeat</div>
</div>

<div id="container">

<div id="left"></div>

<div id="right">
    <div id="stream"></div>

    <div id="inputBox">
        <input id="input" placeholder="write memory...">
        <button onclick="send()">save</button>
    </div>
</div>

</div>

<script>

function load(){
    fetch('/api/memory')
    .then(r=>r.json())
    .then(data=>{
        let left = document.getElementById('left');
        left.innerHTML = '';
        data.forEach(m=>{
            let div = document.createElement('div');
            div.className = 'card';
            div.innerText = m.type + "\\n" + m.content;
            makeDraggable(div);
            left.appendChild(div);
        });
    });
}

function send(){
    let val = document.getElementById('input').value;
    fetch('/api/save', {
        method:'POST',
        body: JSON.stringify({type:'chat', content:val})
    }).then(()=>load());
}

function heartbeat(){
    fetch('/heartbeat');
}

function streamLog(msg){
    let s = document.getElementById('stream');
    let div = document.createElement('div');
    div.innerText = msg;
    s.appendChild(div);
    s.scrollTop = s.scrollHeight;
}

// draggable
function makeDraggable(el){
    let offsetX, offsetY, dragging=false;

    el.onmousedown = function(e){
        dragging=true;
        offsetX=e.offsetX;
        offsetY=e.offsetY;
    };

    document.onmousemove = function(e){
        if(dragging){
            el.style.position='absolute';
            el.style.left=(e.pageX-offsetX)+'px';
            el.style.top=(e.pageY-offsetY)+'px';
        }
    };

    document.onmouseup = ()=>dragging=false;
}

load();
setInterval(load, 5000);

</script>

</body>
</html>
"""


# ---------------- SERVER ----------------
class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())
            return

        if self.path == "/api/memory":
            data = load_memory()
            out = [
                {"type": t, "content": json.loads(c), "time": ts}
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

    def do_POST(self):
        if self.path == "/api/save":
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length).decode()
            data = json.loads(body)

            save_memory(data.get("type","chat"), data.get("content",""))

            self.send_json({"ok": True})
            return

        self.send_response(404)
        self.end_headers()

    def send_json(self, obj):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode())


print("V43 Brain running on", PORT)
HTTPServer(("", PORT), Handler).serve_forever()
