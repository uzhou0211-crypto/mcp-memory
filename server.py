import os
import json
import datetime
import io
import zipfile
import psycopg2
import psycopg2.extras
from flask import Flask, request, jsonify, Response, send_file, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:iTdnKHeCrIAXletVRPmyCKSlFojZWoiu@postgres.railway.internal:5432/railway")

STATE = {
    "mood": 0.5,
    "energy": 0.5,
    "active_message": "我在这里",
    "last_thought": "初始化完成"
}

# =====================
# 数据库初始化
# =====================
def get_conn():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id SERIAL PRIMARY KEY,
                    content TEXT NOT NULL,
                    area TEXT DEFAULT '法典',
                    tags TEXT DEFAULT '',
                    time TIMESTAMP DEFAULT NOW()
                )
            """)
        conn.commit()

# =====================
# 工具函数
# =====================
def save_memory(content, area="法典", tags=""):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO memories (content, area, tags) VALUES (%s, %s, %s) RETURNING id, content, area, tags, time",
                (content, area, tags)
            )
            row = cur.fetchone()
        conn.commit()
    return {"id": row[0], "content": row[1], "area": row[2], "tags": row[3], "time": row[4].isoformat()}

def get_memories(area=None, search=None, limit=200):
    with get_conn() as conn:
        with conn.cursor() as cur:
            sql = "SELECT id, content, area, tags, time FROM memories"
            conds, vals = [], []
            if area:
                conds.append("area = %s"); vals.append(area)
            if search:
                conds.append("content ILIKE %s"); vals.append(f"%{search}%")
            if conds:
                sql += " WHERE " + " AND ".join(conds)
            sql += " ORDER BY id DESC LIMIT %s"
            vals.append(limit)
            cur.execute(sql, vals)
            rows = cur.fetchall()
    return [{"id": r[0], "content": r[1], "area": r[2], "tags": r[3], "time": r[4].isoformat()} for r in rows]

def delete_memory(mid):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM memories WHERE id = %s", (mid,))
            deleted = cur.rowcount
        conn.commit()
    return deleted > 0

def get_state():
    return dict(STATE)

def get_stats():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM memories")
            total = cur.fetchone()[0]
            cur.execute("SELECT area, COUNT(*) FROM memories GROUP BY area")
            areas = {r[0]: r[1] for r in cur.fetchall()}
            cur.execute("SELECT MAX(time) FROM memories")
            last = cur.fetchone()[0]
    return {
        "total": total,
        "areas": areas,
        "last_saved": last.isoformat() if last else None
    }

# =====================
# MCP 工具定义（5个）
# =====================
TOOLS = [
    {
        "name": "save_memory",
        "description": "保存一条记忆到记忆岛",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "要保存的记忆内容"},
                "area":    {"type": "string", "description": "区域：法典/情绪/日记/想法", "default": "法典"},
                "tags":    {"type": "string", "description": "标签（逗号分隔，可选）"}
            },
            "required": ["content"]
        }
    },
    {
        "name": "get_memories",
        "description": "读取记忆，可按区域/关键词过滤",
        "inputSchema": {
            "type": "object",
            "properties": {
                "area":   {"type": "string", "description": "按区域过滤（可选）"},
                "search": {"type": "string", "description": "关键词搜索（可选）"},
                "limit":  {"type": "number", "description": "最多返回条数，默认200"}
            }
        }
    },
    {
        "name": "delete_memory",
        "description": "根据 id 删除一条记忆",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "number", "description": "要删除的记忆 id"}
            },
            "required": ["id"]
        }
    },
    {
        "name": "get_state",
        "description": "获取当前岛屿状态（情绪、能量、活跃信息）",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_stats",
        "description": "获取记忆库统计（总数、各区域分布、最后保存时间）",
        "inputSchema": {"type": "object", "properties": {}}
    }
]

# =====================
# JSON-RPC 核心
# =====================
def handle_rpc(data):
    method = data.get("method", "")
    req_id = data.get("id")
    params = data.get("params", {})

    def ok(result):
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def err(code, message):
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}

    if method == "initialize":
        return ok({
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "memory-island", "version": "11.0"}
        })

    if method in ("notifications/initialized", "notifications/cancelled"):
        return None

    if method == "ping":
        return ok({})

    if method == "tools/list":
        return ok({"tools": TOOLS})

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})

        if name == "save_memory":
            result = save_memory(args.get("content", ""), args.get("area", "法典"), args.get("tags", ""))
        elif name == "get_memories":
            result = get_memories(area=args.get("area"), search=args.get("search"), limit=int(args.get("limit", 200)))
        elif name == "delete_memory":
            result = {"deleted": delete_memory(args.get("id"))}
        elif name == "get_state":
            result = get_state()
        elif name == "get_stats":
            result = get_stats()
        else:
            return err(-32601, f"未知工具: {name}")

        return ok({"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]})

    return err(-32601, f"未知方法: {method}")


# =====================
# MCP 端点
# =====================
@app.route("/mcp", methods=["GET", "POST", "OPTIONS"])
def mcp():
    if request.method == "OPTIONS":
        return _cors("", 204)
    if request.method == "GET":
        return _cors("", 204)

    try:
        data = json.loads(request.get_data(as_text=True))
    except Exception:
        return _cors(json.dumps({"jsonrpc":"2.0","id":None,"error":{"code":-32700,"message":"Parse error"}}), 400, "application/json")

    if isinstance(data, list):
        results = [r for r in (handle_rpc(d) for d in data) if r is not None]
        return _cors(json.dumps(results, ensure_ascii=False) if results else "", 200 if results else 202, "application/json")

    result = handle_rpc(data)
    if result is None:
        return _cors("", 202)
    return _cors(json.dumps(result, ensure_ascii=False), 200, "application/json")


def _cors(body, status=200, ct="text/plain"):
    r = Response(body, status=status, content_type=ct)
    r.headers["Access-Control-Allow-Origin"] = "*"
    r.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    r.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Mcp-Session-Id"
    return r


# =====================
# REST API
# =====================
@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(force=True)
    msg  = data.get("message", "")
    area = data.get("area", "法典")
    mem  = save_memory(msg, area)
    return jsonify({"reply": f"已加密同步至{area}。", "state": get_state(), "memory": mem})

@app.route("/api/read")
def api_read():
    area   = request.args.get("area")
    search = request.args.get("search")
    limit  = int(request.args.get("limit", 200))
    return jsonify(get_memories(area=area, search=search, limit=limit))

@app.route("/api/delete/<int:mid>", methods=["DELETE"])
def api_delete(mid):
    return jsonify({"ok": delete_memory(mid)})

@app.route("/api/state")
def api_state():
    return jsonify(get_state())

@app.route("/api/stats")
def api_stats():
    return jsonify(get_stats())

# =====================
# 批量导入
# =====================
@app.route("/api/upload_chunks", methods=["POST"])
def api_upload_chunks():
    data   = request.get_json(force=True)
    chunks = data.get("chunks", [])
    area   = data.get("area", "法典")
    tags   = data.get("tags", "")
    saved  = 0
    with get_conn() as conn:
        with conn.cursor() as cur:
            for c in chunks:
                if c and c.strip():
                    cur.execute(
                        "INSERT INTO memories (content, area, tags) VALUES (%s, %s, %s)",
                        (c.strip(), area, tags)
                    )
                    saved += 1
        conn.commit()
    return jsonify({"saved": saved})

# =====================
# 备份 / 恢复
# =====================
@app.route("/api/backup")
def api_backup():
    mems = get_memories(limit=99999)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("memories.json", json.dumps(mems, ensure_ascii=False, indent=2))
        z.writestr("state.json",    json.dumps(STATE, ensure_ascii=False, indent=2))
    buf.seek(0)
    return send_file(buf, mimetype="application/octet-stream", as_attachment=True,
                     download_name=f"shun_memory_{datetime.date.today()}.enc")

@app.route("/api/restore", methods=["POST"])
def api_restore():
    try:
        buf = io.BytesIO(request.get_data())
        with zipfile.ZipFile(buf, "r") as z:
            mems = json.loads(z.read("memories.json").decode())
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM memories")
                for m in mems:
                    cur.execute(
                        "INSERT INTO memories (content, area, tags) VALUES (%s, %s, %s)",
                        (m.get("content",""), m.get("area","法典"), m.get("tags",""))
                    )
            conn.commit()
        return jsonify({"restored": len(mems)})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# =====================
# 前端页面
# =====================
@app.route("/")
def index():
    return render_template("index.html")

# =====================
# 健康检查
# =====================
@app.route("/health")
def health():
    try:
        stats = get_stats()
        return jsonify({"status": "ok", "version": "11.0", "memories": stats["total"], "db": "connected"})
    except Exception as e:
        return jsonify({"status": "error", "db": str(e)}), 500

# =====================
# 启动
# =====================
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)), threaded=True)
