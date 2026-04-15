"""
小顺的岛屿记忆库 v4.0
═══════════════════════════════════════════════════════════════
存储：PostgreSQL（Railway 托管，永久保存，重启不丢）
加密：Fernet 对称加密，密钥存环境变量 MEMORY_KEY
访问：API_TOKEN 环境变量控制（可选）

Railway 环境变量：
  DATABASE_URL  → Railway PostgreSQL 自动注入，无需手动填
  MEMORY_KEY    → Fernet 密钥（python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"）
  API_TOKEN     → 自定义访问密码（可选）
═══════════════════════════════════════════════════════════════
"""

import os, json, datetime, threading, time
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from cryptography.fernet import Fernet, InvalidToken
from functools import wraps

# PostgreSQL
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# ════════════════════════════════════════════════════════
#  加密
# ════════════════════════════════════════════════════════
def load_cipher():
    key = os.environ.get("MEMORY_KEY", "").strip()
    if not key:
        key = Fernet.generate_key().decode()
        print("=" * 60)
        print("⚠️  未检测到 MEMORY_KEY！请把下面这个 key 设为 Railway 环境变量：")
        print(key)
        print("=" * 60)
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        new_key = Fernet.generate_key()
        print(f"⚠️  MEMORY_KEY 格式错误，已生成新 key: {new_key.decode()}")
        return Fernet(new_key)

cipher = load_cipher()

def encrypt(text: str) -> str:
    return cipher.encrypt(text.encode("utf-8")).decode("utf-8")

def decrypt(token: str) -> str:
    try:
        return cipher.decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, Exception):
        return token  # 兼容旧明文

# ════════════════════════════════════════════════════════
#  访问控制
# ════════════════════════════════════════════════════════
API_TOKEN = os.environ.get("API_TOKEN", "").strip()

def require_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not API_TOKEN:
            return f(*args, **kwargs)
        if request.headers.get("X-Token", "") != API_TOKEN:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

# ════════════════════════════════════════════════════════
#  PostgreSQL 连接池
# ════════════════════════════════════════════════════════
DB_URL = os.environ.get("DATABASE_URL", "")
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

try:
    db_pool = psycopg2.pool.ThreadedConnectionPool(1, 10, DB_URL)
    print("✅ PostgreSQL 连接池初始化成功")
except Exception as e:
    print(f"❌ PostgreSQL 连接失败: {e}")
    db_pool = None

def get_conn():
    if db_pool is None:
        raise Exception("数据库未连接")
    return db_pool.getconn()

def put_conn(conn):
    if db_pool:
        db_pool.putconn(conn)

def init_db():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id        SERIAL PRIMARY KEY,
                    time      TIMESTAMPTZ DEFAULT NOW(),
                    area      TEXT DEFAULT '法典',
                    content   TEXT NOT NULL,
                    tags      TEXT DEFAULT '',
                    encrypted BOOLEAN DEFAULT TRUE
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_area ON memories(area)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_time ON memories(time DESC)")
        conn.commit()
        print("✅ 数据库表初始化完成")
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        conn.rollback()
    finally:
        put_conn(conn)

init_db()

# ════════════════════════════════════════════════════════
#  State
# ════════════════════════════════════════════════════════
STATE = {
    "mood": 0.5,
    "energy": 0.5,
    "summary": "",
    "time_summary": "",
    "last_thought": "系统初始化中...",
    "active_message": "我在这。"
}

# ════════════════════════════════════════════════════════
#  Memory helpers
# ════════════════════════════════════════════════════════
def save_memory(content: str, area="法典", tags="") -> bool:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO memories(time, area, content, tags, encrypted) VALUES (%s,%s,%s,%s,%s)",
                (datetime.datetime.now(datetime.timezone.utc), area, encrypt(content), tags, True)
            )
        conn.commit()
        return True
    except Exception as e:
        print(f"写入失败: {e}")
        conn.rollback()
        return False
    finally:
        put_conn(conn)

def read_memory(area=None, limit=50, search=None) -> list:
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 取多一些再在内存中过滤（因为加密内容无法 SQL 搜索）
            fetch_limit = min(limit * 4, 500) if search else min(limit, 200)
            if area:
                cur.execute(
                    "SELECT id, time, area, content, tags, encrypted FROM memories WHERE area=%s ORDER BY time DESC LIMIT %s",
                    (area, fetch_limit)
                )
            else:
                cur.execute(
                    "SELECT id, time, area, content, tags, encrypted FROM memories ORDER BY time DESC LIMIT %s",
                    (fetch_limit,)
                )
            rows = cur.fetchall()

        result = []
        for r in rows:
            d = dict(r)
            d["content"] = decrypt(d["content"])
            d["time"] = d["time"].isoformat() if d.get("time") else ""
            result.append(d)

        if search:
            result = [r for r in result if search.lower() in r["content"].lower()]

        return result[:limit]
    except Exception as e:
        print(f"读取失败: {e}")
        return []
    finally:
        put_conn(conn)

def delete_memory(memory_id: int) -> bool:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM memories WHERE id=%s", (memory_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"删除失败: {e}")
        conn.rollback()
        return False
    finally:
        put_conn(conn)

def get_stats() -> dict:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM memories")
            total = cur.fetchone()[0]
            cur.execute("SELECT area, COUNT(*) FROM memories GROUP BY area ORDER BY COUNT(*) DESC")
            areas = [{"area": r[0], "count": r[1]} for r in cur.fetchall()]
        return {"total": total, "areas": areas}
    except Exception as e:
        print(f"统计失败: {e}")
        return {"total": 0, "areas": []}
    finally:
        put_conn(conn)

# ════════════════════════════════════════════════════════
#  Think engine
# ════════════════════════════════════════════════════════
def think_loop():
    while True:
        try:
            mem  = read_memory(limit=20)
            mood = 0.5
            for m in mem:
                t = m["content"]
                if any(k in t for k in ["开心","好","爽","爱","喜欢","棒","感谢","高兴"]): mood += 0.03
                if any(k in t for k in ["烦","累","压力","难过","崩","焦虑","失败","痛"]):  mood -= 0.03
            STATE["mood"]         = round(max(0.0, min(1.0, mood)), 3)
            STATE["time_summary"] = f"{get_stats()['total']} 条记忆"
            if STATE["mood"] < 0.3:
                STATE["last_thought"]   = "检测到低落情绪脉冲"
                STATE["active_message"] = "要不要去岛边吹吹风？我会陪着你。"
            elif STATE["mood"] > 0.7:
                STATE["last_thought"]   = "共鸣频率处于高位"
                STATE["active_message"] = "现在的感觉很好，我想记住这一刻。"
            else:
                STATE["last_thought"]   = "波形平稳，持续守护中"
                STATE["active_message"] = "我在听，你想聊什么都可以。"
            if mem:
                STATE["summary"] = "  ›  ".join([m["content"][:15] for m in mem[:4]])
        except Exception as e:
            print(f"思考引擎故障: {e}")
        time.sleep(10)

threading.Thread(target=think_loop, daemon=True).start()

# ════════════════════════════════════════════════════════
#  MCP  JSON-RPC 2.0
# ════════════════════════════════════════════════════════
MCP_TOOLS = [
    {
        "name": "save_memory",
        "description": "保存一条新记忆到小顺的岛屿记忆库（内容自动加密存入 PostgreSQL）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string",  "description": "要保存的记忆内容"},
                "area":    {"type": "string",  "description": "分区：法典/情绪/日记/想法", "default": "法典"},
                "tags":    {"type": "string",  "description": "标签，逗号分隔", "default": ""}
            },
            "required": ["content"]
        }
    },
    {
        "name": "get_memories",
        "description": "读取记忆库（内容自动解密返回）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "area":   {"type": "string",  "description": "筛选分区，留空读全部"},
                "limit":  {"type": "integer", "description": "最多返回条数，默认20", "default": 20},
                "search": {"type": "string",  "description": "关键词搜索"}
            }
        }
    },
    {
        "name": "delete_memory",
        "description": "删除指定 ID 的记忆",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "integer", "description": "记忆 ID"}},
            "required": ["id"]
        }
    },
    {
        "name": "get_state",
        "description": "获取小顺岛屿当前情绪和状态",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_stats",
        "description": "获取记忆库统计（总数、各分区数量）",
        "inputSchema": {"type": "object", "properties": {}}
    }
]

def mcp_dispatch(method, params, req_id):
    def ok(r):   return {"jsonrpc": "2.0", "id": req_id, "result": r}
    def err(c,m): return {"jsonrpc": "2.0", "id": req_id, "error": {"code": c, "message": m}}

    if method == "initialize":
        return ok({"protocolVersion": "2024-11-05",
                   "capabilities": {"tools": {}},
                   "serverInfo": {"name": "shun-island-memory", "version": "4.0.0"}})

    if method == "tools/list":
        return ok({"tools": MCP_TOOLS})

    if method == "tools/call":
        name = (params or {}).get("name")
        args = (params or {}).get("arguments", {})

        if name == "save_memory":
            content = (args.get("content") or "").strip()
            if not content: return err(-32602, "content 不能为空")
            ok_flag = save_memory(content, args.get("area","法典"), args.get("tags",""))
            return ok({"content": [{"type":"text","text":"✅ 记忆已加密存入 PostgreSQL" if ok_flag else "❌ 保存失败"}]})

        if name == "get_memories":
            mems = read_memory(area=args.get("area"), limit=int(args.get("limit",20)), search=args.get("search"))
            return ok({"content": [{"type":"text","text": json.dumps(mems, ensure_ascii=False, indent=2)}]})

        if name == "delete_memory":
            mid = args.get("id")
            if mid is None: return err(-32602, "id 不能为空")
            ok_flag = delete_memory(int(mid))
            return ok({"content": [{"type":"text","text":"✅ 已删除" if ok_flag else "❌ 失败"}]})

        if name == "get_state":
            return ok({"content": [{"type":"text","text": json.dumps(STATE, ensure_ascii=False, indent=2)}]})

        if name == "get_stats":
            return ok({"content": [{"type":"text","text": json.dumps(get_stats(), ensure_ascii=False, indent=2)}]})

        return err(-32601, f"未知工具: {name}")

    if method.startswith("notifications/"):
        return None

    return err(-32601, f"未知方法: {method}")


@app.route("/mcp", methods=["POST","GET"])
@app.route("/mcp/", methods=["POST","GET"])
def mcp_endpoint():
    if request.method == "GET":
        return jsonify({"status":"MCP endpoint ready","protocol":"JSON-RPC 2.0","version":"4.0.0"})
    body = request.get_json(force=True, silent=True)
    if body is None:
        return jsonify({"jsonrpc":"2.0","id":None,"error":{"code":-32700,"message":"Parse error"}}), 400
    if isinstance(body, list):
        return jsonify([r for r in [mcp_dispatch(b.get("method",""), b.get("params",{}), b.get("id")) for b in body] if r])
    resp = mcp_dispatch(body.get("method",""), body.get("params",{}), body.get("id"))
    return ("", 204) if resp is None else jsonify(resp)

# ════════════════════════════════════════════════════════
#  REST API
# ════════════════════════════════════════════════════════
@app.route("/api/chat", methods=["POST"])
@require_token
def chat():
    data = request.get_json(force=True)
    msg  = (data.get("message") or "").strip()
    area = data.get("area", "法典")
    if msg: save_memory(msg, area)
    return jsonify({"reply": "已加密存入岛屿深处。", "state": STATE})

@app.route("/api/sync", methods=["POST"])
@require_token
def sync():
    data    = request.get_json(force=True)
    content = (data.get("content") or data.get("text") or "").strip()
    if content:
        save_memory(content, data.get("area","法典"), data.get("tags",""))
    return jsonify({"status": "success"})

@app.route("/api/state")
def api_state():
    return jsonify(STATE)

@app.route("/api/read")
@require_token
def api_read():
    return jsonify(read_memory(
        area=request.args.get("area"),
        limit=int(request.args.get("limit", 50)),
        search=request.args.get("search")
    ))

@app.route("/api/delete/<int:mid>", methods=["DELETE"])
@require_token
def api_delete(mid):
    return jsonify({"status": "success" if delete_memory(mid) else "error"})

@app.route("/api/stats")
def api_stats():
    return jsonify(get_stats())

@app.route("/api/upload_chunks", methods=["POST"])
@require_token
def upload_chunks():
    data   = request.get_json(force=True)
    chunks = data.get("chunks", [])
    area   = data.get("area", "日记")
    tags   = data.get("tags", "")
    if not chunks:
        return jsonify({"status":"error","message":"chunks 不能为空"}), 400
    saved = sum(1 for c in chunks if c and c.strip() and save_memory(c.strip(), area, tags))
    return jsonify({"status":"success","saved":saved,"total":len(chunks)})

@app.route("/api/backup")
@require_token
def api_backup():
    mems = read_memory(limit=99999)
    raw  = json.dumps(mems, ensure_ascii=False, indent=2).encode("utf-8")
    return Response(
        cipher.encrypt(raw),
        mimetype="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=shun_memory_backup.enc"}
    )

@app.route("/api/restore", methods=["POST"])
@require_token
def api_restore():
    try:
        memories = json.loads(cipher.decrypt(request.data).decode("utf-8"))
        restored = sum(1 for m in memories if m.get("content","").strip() and
                      save_memory(m["content"].strip(), m.get("area","法典"), m.get("tags","")))
        return jsonify({"status":"success","restored":restored})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)}), 400

@app.route("/")
def index():
    stats = get_stats()
    return jsonify({
        "status":   "Shun Island Memory v4.0",
        "storage":  "PostgreSQL",
        "encrypted": True,
        "memories": stats["total"],
        "mcp":      "/mcp",
        "api":      "/api"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)), debug=False)
