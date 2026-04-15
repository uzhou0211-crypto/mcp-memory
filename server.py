import os, json, sqlite3, datetime
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)

# ================= CONFIG =================
TOKEN = os.environ.get("MCP_TOKEN", "changeme")
DB_PATH = os.path.join(os.getcwd(), "memory.db")
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ================= DB =================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT,
        area TEXT,
        content TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

# ================= MEMORY =================
def save_memory(content, area="默认"):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO memories VALUES (NULL,?,?,?)",
        (datetime.datetime.now().isoformat(), area, content)
    )
    conn.commit()
    conn.close()

def read_memory(limit=100):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT created_at, area, content FROM memories ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()

    return [
        {"time": r[0], "area": r[1], "content": r[2]}
        for r in rows
    ]

# ================= MCP =================
@app.route("/mcp/<token>", methods=["POST"])
def mcp(token):
    if token != TOKEN:
        return jsonify({"error":"unauthorized"}), 401

    body = request.json
    method = body.get("method")
    rid = body.get("id")

    if method == "tools/list":
        return jsonify({
            "jsonrpc":"2.0",
            "id":rid,
            "result":{
                "tools":[
                    {"name":"save_memory",
                     "inputSchema":{"type":"object","properties":{"content":{"type":"string"},"area":{"type":"string"}}}},
                    {"name":"get_memories",
                     "inputSchema":{"type":"object","properties":{}}}
                ]
            }
        })

    if method == "tools/call":
        name = body["params"]["name"]
        args = body["params"].get("arguments",{})

        if name == "save_memory":
            save_memory(args.get("content",""), args.get("area","默认"))
            result = "saved"

        elif name == "get_memories":
            result = json.dumps(read_memory(), ensure_ascii=False)

        else:
            result = "unknown tool"

        return jsonify({
            "jsonrpc":"2.0",
            "id":rid,
            "result":{"content":[{"type":"text","text":result}]}
        })

    return jsonify({"error":"unknown method"})

# ================= API =================
@app.route("/api/read")
def api_read():
    return jsonify(read_memory())

@app.route("/api/sync", methods=["POST"])
def api_sync():
    data = request.json
    save_memory(data.get("content",""), data.get("area","未知"))
    return jsonify({"status":"ok"})

# ================= FILE UPLOAD (.md) =================
@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    if not f:
        return jsonify({"error":"no file"}), 400

    if not f.filename.endswith(".md"):
        return jsonify({"error":"only md allowed"}), 400

    name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_") + f.filename
    path = os.path.join(UPLOAD_DIR, name)
    f.save(path)

    return jsonify({"status":"uploaded","file":name})

@app.route("/files")
def files():
    return jsonify(os.listdir(UPLOAD_DIR))

@app.route("/files/<name>")
def file_get(name):
    return send_from_directory(UPLOAD_DIR, name)

# ================= FRONTEND =================
@app.route("/")
def index():
    return """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>SHUN ISLAND</title>
<style>
body{background:#0b0f14;color:#fff;font-family:Arial;padding:20px}
textarea{width:100%;height:80px}
button{margin-top:10px}
.item{border-left:2px solid #4dc;padding:6px;margin:6px}
</style>
</head>
<body>

<h2>SHUN ISLAND</h2>

<textarea id="t"></textarea><br>
<button onclick="send()">SAVE</button>
<button onclick="upload()">UPLOAD MD</button>

<div id="list"></div>

<input type="file" id="f" style="display:none">

<script>

async function load(){
  let r=await fetch('/api/read')
  let d=await r.json()
  document.getElementById('list').innerHTML=
    d.map(x=>`<div class='item'>[${x.area}] ${x.content}</div>`).join('')
}

async function send(){
  let v=document.getElementById('t').value
  await fetch('/api/sync?token=1314',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({content:v,area:'法典'})
  })
  document.getElementById('t').value=''
  load()
}

function upload(){
  document.getElementById('f').click()
}

document.getElementById('f').onchange=async(e)=>{
  let fd=new FormData()
  fd.append('file',e.target.files[0])
  await fetch('/upload',{method:'POST',body:fd})
  alert('上传成功')
}

load()
</script>

</body>
</html>
"""

# ================= START =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
