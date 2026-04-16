import os
import json
import datetime
import io
import zipfile
from flask import Flask, request, jsonify, Response, send_file, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# =====================
# 内存存储
# =====================
MEMORIES = []
AUTO_ID = 1
STATE = {
    "mood": 0.5,
    "energy": 0.5,
    "active_message": "我在这里",
    "last_thought": "初始化完成"
}

# =====================
# 工具函数
# =====================
def save_memory(content, area="法典", tags=""):
    global AUTO_ID
    mem = {
        "id": AUTO_ID,
        "content": content,
        "area": area,
        "tags": tags,
        "time": datetime.datetime.utcnow().isoformat()
    }
    AUTO_ID += 1
    MEMORIES.append(mem)
    return mem

def get_memories(area=None, search=None, limit=200):
    result = list(reversed(MEMORIES))
    if area:
        result = [m for m in result if m.get("area") == area]
    if search:
        sl = search.lower()
        result = [m for m in result if sl in m.get("content", "").lower()]
    return result[:limit]

def delete_memory(mid):
    global MEMORIES
    before = len(MEMORIES)
    MEMORIES = [m for m in MEMORIES if m["id"] != mid]
    return before != len(MEMORIES)

def get_state():
    return dict(STATE)

def get_stats():
    areas = {}
    for m in MEMORIES:
        a = m.get("area", "法典")
        areas[a] = areas.get(a, 0) + 1
    return {
        "total": len(MEMORIES),
        "areas": areas,
        "last_saved": MEMORIES[-1]["time"] if MEMORIES else None
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
                "limit":  {"type": "number",  "description": "最多返回条数，默认200"}
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
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_stats",
        "description": "获取记忆库统计（总数、各区域分布、最后保存时间）",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
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
            "serverInfo": {"name": "memory-island", "version": "10.0"}
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
            result = save_memory(
                args.get("content", ""),
                args.get("area", "法典"),
                args.get("tags", "")
            )
        elif name == "get_memories":
            result = get_memories(
                area=args.get("area"),
                search=args.get("search"),
                limit=int(args.get("limit", 200))
            )
        elif name == "delete_memory":
            result = {"deleted": delete_memory(args.get("id"))}
        elif name == "get_state":
            result = get_state()
        elif name == "get_stats":
            result = get_stats()
        else:
            return err(-32601, f"未知工具: {name}")

        return ok({
            "content": [
                {"type": "text", "text": json.dumps(result, ensure_ascii=False)}
            ]
        })

    return err(-32601, f"未知方法: {method}")


# =====================
# MCP 端点 —— Streamable HTTP
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
# 批量导入（每批 3 块，纯内存操作，不会超时）
# =====================
@app.route("/api/upload_chunks", methods=["POST"])
def api_upload_chunks():
    data   = request.get_json(force=True)
    chunks = data.get("chunks", [])
    area   = data.get("area", "法典")
    tags   = data.get("tags", "")
    saved  = 0
    for c in chunks:
        if c and c.strip():
            save_memory(c.strip(), area, tags)
            saved += 1
    return jsonify({"saved": saved, "total": len(MEMORIES)})

# =====================
# 备份 / 恢复
# =====================
@app.route("/api/backup")
def api_backup():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("memories.json", json.dumps(MEMORIES, ensure_ascii=False, indent=2))
        z.writestr("state.json",    json.dumps(STATE,    ensure_ascii=False, indent=2))
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/octet-stream",
        as_attachment=True,
        download_name=f"shun_memory_{datetime.date.today()}.enc"
    )

@app.route("/api/restore", methods=["POST"])
def api_restore():
    global MEMORIES, AUTO_ID
    try:
        buf = io.BytesIO(request.get_data())
        with zipfile.ZipFile(buf, "r") as z:
            mems = json.loads(z.read("memories.json").decode())
        MEMORIES = mems
        AUTO_ID  = max((m["id"] for m in mems), default=0) + 1
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
    return jsonify({"status": "ok", "version": "10.0", "memories": len(MEMORIES)})

# =====================
# 启动
# =====================
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 3000)),
        threaded=True
    )
