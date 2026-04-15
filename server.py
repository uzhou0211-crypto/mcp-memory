import os, json, sqlite3, datetime, hashlib
import numpy as np
from flask import Flask, request, jsonify

app = Flask(__name__)

# ================= CONFIG =================
TOKEN = os.environ.get("MCP_TOKEN", "changeme")
DB_PATH = "memory.db"
PERSONALITY_PATH = "personality.json"

# ================= INIT DB =================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT,
        content TEXT,
        summary TEXT,
        tags TEXT,
        embedding TEXT,
        importance INTEGER
    )
    """)
    conn.commit()
    conn.close()

init_db()

# ================= UTIL =================
def fake_embed(text):
    h = hashlib.md5(text.encode()).hexdigest()
    return [int(h[i:i+2],16)/255 for i in range(0,32,2)]

def cosine(a,b):
    a=np.array(a); b=np.array(b)
    return float(np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b)+1e-9))

# ================= PERSONALITY =================
def load_personality():
    if not os.path.exists(PERSONALITY_PATH):
        return {
            "stress":0.5,
            "energy":0.5,
            "trend":"stable"
        }
    return json.load(open(PERSONALITY_PATH,"r"))

def save_personality(p):
    json.dump(p, open(PERSONALITY_PATH,"w"), ensure_ascii=False, indent=2)

def update_personality(memories):
    p = load_personality()

    stress_words = ["累","烦","压力","崩"]
    energy_words = ["开心","爽","好","舒服"]

    stress = sum(1 for m in memories if any(w in m["content"] for w in stress_words))
    energy = sum(1 for m in memories if any(w in m["content"] for w in energy_words))

    p["stress"] = min(1.0, p["stress"] + stress*0.02)
    p["energy"] = min(1.0, p["energy"] + energy*0.02)

    if p["stress"] > 0.7:
        p["trend"]="压力上升"
    elif p["energy"] > 0.7:
        p["trend"]="状态良好"

    save_personality(p)
    return p

# ================= MEMORY CORE =================
def analyze(text):
    tags=[]
    if any(k in text for k in ["累","烦","压力","崩"]):
        tags.append("stress")
    if any(k in text for k in ["开心","爽","好"]):
        tags.append("positive")

    summary=text[:60]
    embedding=fake_embed(text)
    importance=3
    return summary,tags,embedding,importance

def save_memory(content):
    summary,tags,embedding,importance=analyze(content)

    conn=sqlite3.connect(DB_PATH)
    conn.execute("""
    INSERT INTO memories (created_at,content,summary,tags,embedding,importance)
    VALUES (?,?,?,?,?,?)
    """,(
        datetime.datetime.now().isoformat(),
        content,
        summary,
        ",".join(tags),
        json.dumps(embedding),
        importance
    ))
    conn.commit()
    conn.close()

def get_all():
    conn=sqlite3.connect(DB_PATH)
    rows=conn.execute("SELECT * FROM memories").fetchall()
    conn.close()

    res=[]
    for r in rows:
        res.append({
            "id":r[0],
            "time":r[1],
            "content":r[2],
            "summary":r[3],
            "tags":r[4],
            "embedding":r[5]
        })
    return res

# ================= SEARCH =================
def search(query):
    qv=fake_embed(query)
    rows=get_all()

    results=[]
    for r in rows:
        if not r["embedding"]:
            continue
        score=cosine(qv,json.loads(r["embedding"]))
        if score>0.75:
            results.append({**r,"score":score})

    return sorted(results,key=lambda x:x["score"],reverse=True)

# ================= RECALL =================
def recall(query):
    mem=search(query)
    p=load_personality()

    text="🧠 记忆回忆：\n"
    for m in mem[:6]:
        text+=f"- {m['content']}\n"

    text+="\n📊 人格状态：\n"
    text+=f"- stress:{p['stress']:.2f}\n"
    text+=f"- energy:{p['energy']:.2f}\n"
    text+=f"- trend:{p['trend']}\n"

    return text

# ================= MCP =================
@app.route("/mcp/<token>",methods=["POST"])
def mcp(token):
    if token!=TOKEN:
        return jsonify({"error":"unauthorized"}),401

    body=request.json
    name=body["params"]["name"]
    args=body["params"].get("arguments",{})

    if name=="save_memory":
        save_memory(args.get("content",""))
        return jsonify({"result":"ok"})

    if name=="recall_memory":
        return jsonify({"result":recall(args.get("query",""))})

    if name=="update_personality":
        return jsonify(update_personality(get_all()))

    return jsonify({"result":"unknown tool"})

# ================= API =================
@app.route("/api/save",methods=["POST"])
def api_save():
    if request.args.get("token")!=TOKEN:
        return jsonify({"error":"unauthorized"}),401
    save_memory(request.json.get("content",""))
    return jsonify({"ok":True})

@app.route("/api/recall")
def api_recall():
    if request.args.get("token")!=TOKEN:
        return jsonify({"error":"unauthorized"}),401
    return jsonify({"result":recall(request.args.get("q",""))})

@app.route("/api/search")
def api_search():
    if request.args.get("token")!=TOKEN:
        return jsonify({"error":"unauthorized"}),401
    return jsonify(search(request.args.get("q","")))

# ================= SIMPLE UI =================
@app.route("/")
def index():
    return """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>V7 Brain</title>
<style>
body{background:#0b0f14;color:#fff;font-family:Arial;padding:20px}
textarea{width:100%;height:80px}
.item{border-left:2px solid #4dc;margin:6px;padding:6px}
</style>
</head>
<body>

<h2>🧠 V7 MEMORY BRAIN</h2>

<textarea id="t"></textarea><br>
<button onclick="save()">SAVE</button>
<button onclick="recall()">RECALL</button>

<pre id="out"></pre>

<script>
const TOKEN="changeme"

async function save(){
  await fetch('/api/save?token='+TOKEN,{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({content:document.getElementById('t').value})
  })
  alert("saved")
}

async function recall(){
  let r=await fetch('/api/recall?token='+TOKEN+'&q=stress')
  let d=await r.json()
  document.getElementById('out').innerText=d.result
}
</script>

</body>
</html>
"""

# ================= RUN =================
if __name__=="__main__":
    app.run(host="0.0.0.0",port=3000)
