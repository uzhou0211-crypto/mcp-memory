import os, json, sqlite3, datetime, threading, time
from flask import Flask, request, jsonify
from flask_cors import CORS
from cryptography.fernet import Fernet

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

DB = "memory.db"
KEY_FILE = "secret.key"

# ── Key ──────────────────────────────────────────────────────────────────────
def load_key():
    if os.path.exists(KEY_FILE):
        return open(KEY_FILE, "rb").read()
    key = Fernet.generate_key()
    open(KEY_FILE, "wb").write(key)
    return key

cipher = Fernet(load_key())

# ── State ────────────────────────────────────────────────────────────────────
STATE = {
    "mood": 0.5,
    "energy": 0.5,
    "summary": "",
    "time_summary": "",
    "last_thought": "系统初始化中...",
    "active_message": "我在这。"
}

# ── DB ───────────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            time    TEXT,
            area    TEXT DEFAULT '法典',
            content TEXT,
            tags    TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ── Memory helpers ───────────────────────────────────────────────────────────
def save_memory(content, area="法典", tags=""):
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO memories(time, area, content, tags) VALUES (?,?,?,?)",
            (datetime.datetime.now().isoformat(), area, content, tags)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"写入失败: {e}")
        return False

def read_memory(area=None, limit=50, search=None):
    try:
        conn = get_db()
        if search:
            rows = conn.execute(
                "SELECT id,time,area,content,tags FROM memories WHERE content LIKE ? ORDER BY id DESC LIMIT ?",
                (f"%{search}%", limit)
            ).fetchall()
        elif area:
            rows = conn.execute(
                "SELECT id,time,area,content,tags FROM memories WHERE area=? ORDER BY id DESC LIMIT ?",
                (area, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id,time,area,content,tags FROM memories ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"读取失败: {e}")
        return []

def delete_memory(memory_id):
    try:
        conn = get_db()
        conn.execute("DELETE FROM memories WHERE id=?", (memory_id,))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def get_stats():
    try:
        conn = get_db()
        total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        areas = conn.execute(
            "SELECT area, COUNT(*) as cnt FROM memories GROUP BY area ORDER BY cnt DESC"
        ).fetchall()
        conn.close()
        return {"total": total, "areas": [{"area": r[0], "count": r[1]} for r in areas]}
    except:
        return {"total": 0, "areas": []}

# ── Think engine ─────────────────────────────────────────────────────────────
def think_loop():
    while True:
        try:
            mem = read_memory(limit=20)
            mood = 0.5
            for m in mem[:20]:
                t = m["content"]
                if any(k in t for k in ["开心", "好", "爽", "爱", "喜欢", "棒", "感谢"]): mood += 0.03
                if any(k in t for k in ["烦", "累", "压力", "难过", "崩", "焦虑", "失败"]): mood -= 0.03
            STATE["mood"] = round(max(0.0, min(1.0, mood)), 3)
            stats = get_stats()
            STATE["time_summary"] = f"{stats['total']} 条记忆"
            if STATE["mood"] < 0.3:
                STATE["last_thought"] = "检测到低落情绪脉冲"
                STATE["active_message"] = "要不要去岛边吹吹风？我会陪着你。"
            elif STATE["mood"] > 0.7:
                STATE["last_thought"] = "共鸣频率处于高位"
                STATE["active_message"] = "现在的感觉很好，我想记住这一刻。"
            else:
                STATE["last_thought"] = "波形平稳，持续守护中"
                STATE["active_message"] = "我在听，你想聊什么都可以。"
            if mem:
                STATE["summary"] = "  ›  ".join([m["content"][:15] for m in mem[:4]])
        except Exception as e:
            print(f"思考引擎故障: {e}")
        time.sleep(5)

threading.Thread(target=think_loop, daemon=True).start()

# ════════════════════════════════════════════════════════
#  MCP  (JSON-RPC 2.0)   ← 这是你缺少的核心部分
# ════════════════════════════════════════════════════════

MCP_TOOLS = [
    {
        "name": "save_memory",
        "description": "保存一条新记忆到小顺的岛屿记忆库",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "要保存的记忆内容"},
                "area":    {"type": "string", "description": "记忆分区，如 法典/情绪/日记", "default": "法典"},
                "tags":    {"type": "string", "description": "标签，逗号分隔", "default": ""}
            },
            "required": ["content"]
        }
    },
    {
        "name": "get_memories",
        "description": "读取记忆库中的记忆",
        "inputSchema": {
            "type": "object",
            "properties": {
                "area":   {"type": "string", "description": "筛选分区，留空则读全部"},
                "limit":  {"type": "integer", "description": "最多返回条数，默认20", "default": 20},
                "search": {"type": "string", "description": "关键词搜索"}
            }
        }
    },
    {
        "name": "delete_memory",
        "description": "删除指定 ID 的记忆",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "记忆的 ID"}
            },
            "required": ["id"]
        }
    },
    {
        "name": "get_state",
        "description": "获取小顺岛屿的当前情绪和状态",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_stats",
        "description": "获取记忆库统计信息（总数、各分区数量）",
        "inputSchema": {"type": "object", "properties": {}}
    }
]

def mcp_dispatch(method, params, req_id):
    """处理 MCP JSON-RPC 请求，返回标准响应"""
    def ok(result):
        return {"jsonrpc": "2.0", "id": req_id, "result": result}
    def err(code, msg):
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": msg}}

    # ── initialize ──
    if method == "initialize":
        return ok({
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "shun-island-memory", "version": "2.0.0"}
        })

    # ── tools/list ──
    if method == "tools/list":
        return ok({"tools": MCP_TOOLS})

    # ── tools/call ──
    if method == "tools/call":
        name = params.get("name") if params else None
        args = params.get("arguments", {}) if params else {}

        if name == "save_memory":
            content = args.get("content", "").strip()
            if not content:
                return err(-32602, "content 不能为空")
            ok_flag = save_memory(content, args.get("area", "法典"), args.get("tags", ""))
            return ok({"content": [{"type": "text", "text": "✅ 记忆已保存" if ok_flag else "❌ 保存失败"}]})

        if name == "get_memories":
            mems = read_memory(
                area=args.get("area"),
                limit=int(args.get("limit", 20)),
                search=args.get("search")
            )
            text = json.dumps(mems, ensure_ascii=False, indent=2)
            return ok({"content": [{"type": "text", "text": text}]})

        if name == "delete_memory":
            mid = args.get("id")
            if mid is None:
                return err(-32602, "id 不能为空")
            ok_flag = delete_memory(int(mid))
            return ok({"content": [{"type": "text", "text": "✅ 已删除" if ok_flag else "❌ 删除失败"}]})

        if name == "get_state":
            return ok({"content": [{"type": "text", "text": json.dumps(STATE, ensure_ascii=False, indent=2)}]})

        if name == "get_stats":
            stats = get_stats()
            return ok({"content": [{"type": "text", "text": json.dumps(stats, ensure_ascii=False, indent=2)}]})

        return err(-32601, f"未知工具: {name}")

    # ── notifications (忽略，只返回 null) ──
    if method.startswith("notifications/"):
        return None

    return err(-32601, f"未知方法: {method}")


@app.route("/mcp", methods=["POST", "GET"])
@app.route("/mcp/", methods=["POST", "GET"])
def mcp_endpoint():
    """MCP JSON-RPC 2.0 端点 — 支持单条和批量请求"""
    if request.method == "GET":
        # SSE 握手（部分 MCP 客户端用 SSE 协议）
        return jsonify({"status": "MCP endpoint ready", "protocol": "JSON-RPC 2.0"})

    body = request.get_json(force=True, silent=True)
    if body is None:
        return jsonify({"jsonrpc": "2.0", "id": None,
                        "error": {"code": -32700, "message": "Parse error"}}), 400

    # 批量请求
    if isinstance(body, list):
        responses = []
        for req in body:
            r = mcp_dispatch(req.get("method",""), req.get("params",{}), req.get("id"))
            if r is not None:
                responses.append(r)
        return jsonify(responses)

    # 单条请求
    resp = mcp_dispatch(body.get("method", ""), body.get("params", {}), body.get("id"))
    if resp is None:
        return "", 204
    return jsonify(resp)


# ════════════════════════════════════════════════════════
#  原有 REST API (保留，给前端用)
# ════════════════════════════════════════════════════════

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    msg  = data.get("message", "").strip()
    area = data.get("area", "法典")
    if msg:
        save_memory(msg, area)
    return jsonify({"reply": "已同步至岛屿深处。", "state": STATE})

@app.route("/api/sync", methods=["POST"])
def sync():
    data    = request.get_json(force=True)
    content = (data.get("content") or data.get("text") or "").strip()
    area    = data.get("area", "法典")
    tags    = data.get("tags", "")
    if content:
        save_memory(content, area, tags)
    return jsonify({"status": "success"})

@app.route("/api/state")
def api_state():
    return jsonify(STATE)

@app.route("/api/read")
def api_read():
    area   = request.args.get("area")
    search = request.args.get("search")
    limit  = int(request.args.get("limit", 50))
    return jsonify(read_memory(area=area, limit=limit, search=search))

@app.route("/api/delete/<int:mid>", methods=["DELETE"])
def api_delete(mid):
    ok_flag = delete_memory(mid)
    return jsonify({"status": "success" if ok_flag else "error"})

@app.route("/api/stats")
def api_stats():
    return jsonify(get_stats())

@app.route("/")
def index():
    return jsonify({"status": "Shun Island Memory v2.0", "mcp": "/mcp", "api": "/api"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)), debug=False)
