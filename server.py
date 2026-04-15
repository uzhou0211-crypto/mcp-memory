"""
小顺的岛屿记忆库 v3.0
═══════════════════════════════════════════════════════════════
加密方案：Fernet 对称加密，密钥存在 Railway 环境变量 MEMORY_KEY
Railway 重启/崩溃/重新部署 → 密钥永不丢失

部署前必须在 Railway 设置环境变量：
  变量名：MEMORY_KEY
  变量值：运行一次 python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 得到的字符串

API 访问控制：
  变量名：API_TOKEN
  变量值：你自己设一个密码，比如 shun2024secret
  所有 /api/* 请求需要 Header: X-Token: <你的密码>
  MCP 端点不需要 token（Claude 自动处理）
═══════════════════════════════════════════════════════════════
"""

import os, json, sqlite3, datetime, threading, time, base64
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from cryptography.fernet import Fernet, InvalidToken
from functools import wraps

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

DB = "memory.db"

# ════════════════════════════════════════════════════════
#  加密：从环境变量读密钥，Railway 重启不丢
# ════════════════════════════════════════════════════════
def load_cipher():
    key = os.environ.get("MEMORY_KEY", "").strip()
    if not key:
        # 没设环境变量时自动生成并打印，提示用户复制到 Railway
        key = Fernet.generate_key().decode()
        print("=" * 60)
        print("⚠️  未检测到 MEMORY_KEY 环境变量！")
        print("请把下面这个 key 复制到 Railway 环境变量 MEMORY_KEY：")
        print(key)
        print("=" * 60)
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        # key 格式不对时生成新的
        new_key = Fernet.generate_key()
        print(f"⚠️  MEMORY_KEY 格式错误，已生成新 key: {new_key.decode()}")
        return Fernet(new_key)

cipher = load_cipher()

def encrypt(text: str) -> str:
    """加密字符串，返回 base64 字符串存入 DB"""
    return cipher.encrypt(text.encode("utf-8")).decode("utf-8")

def decrypt(token: str) -> str:
    """解密，失败时返回原文（兼容旧明文数据）"""
    try:
        return cipher.decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, Exception):
        return token  # 旧明文数据直接返回

# ════════════════════════════════════════════════════════
#  访问控制（可选，设了 API_TOKEN 才生效）
# ════════════════════════════════════════════════════════
API_TOKEN = os.environ.get("API_TOKEN", "").strip()

def require_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not API_TOKEN:
            return f(*args, **kwargs)
        token = request.headers.get("X-Token", "")
        if token != API_TOKEN:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

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
#  DB
# ════════════════════════════════════════════════════════
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
            tags    TEXT DEFAULT '',
            encrypted INTEGER DEFAULT 1
        )
    """)
    # 迁移旧表：加 encrypted 列
    try:
        conn.execute("ALTER TABLE memories ADD COLUMN encrypted INTEGER DEFAULT 1")
    except Exception:
        pass
    conn.commit()
    conn.close()

init_db()

# ════════════════════════════════════════════════════════
#  Memory helpers
# ════════════════════════════════════════════════════════
def save_memory(content: str, area="法典", tags="") -> bool:
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO memories(time, area, content, tags, encrypted) VALUES (?,?,?,?,?)",
            (datetime.datetime.now().isoformat(), area, encrypt(content), tags, 1)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"写入失败: {e}")
        return False

def _row_to_dict(r) -> dict:
    d = dict(r)
    d["content"] = decrypt(d["content"])
    return d

def read_memory(area=None, limit=50, search=None) -> list:
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT id,time,area,content,tags,encrypted FROM memories ORDER BY id DESC LIMIT ?",
            (min(limit, 500),)
        ).fetchall()
        conn.close()
        result = [_row_to_dict(r) for r in rows]
        # 在解密后做过滤（加密内容无法在 SQL 里搜索）
        if area:
            result = [r for r in result if r["area"] == area]
        if search:
            result = [r for r in result if search.lower() in r["content"].lower()]
        return result[:limit]
    except Exception as e:
        print(f"读取失败: {e}")
        return []

def delete_memory(memory_id: int) -> bool:
    try:
        conn = get_db()
        conn.execute("DELETE FROM memories WHERE id=?", (memory_id,))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False

def get_stats() -> dict:
    try:
        conn = get_db()
        total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        areas = conn.execute(
            "SELECT area, COUNT(*) FROM memories GROUP BY area ORDER BY COUNT(*) DESC"
        ).fetchall()
        conn.close()
        return {"total": total, "areas": [{"area": r[0], "count": r[1]} for r in areas]}
    except Exception:
        return {"total": 0, "areas": []}

# ════════════════════════════════════════════════════════
#  Think engine
# ════════════════════════════════════════════════════════
def think_loop():
    while True:
        try:
            mem = read_memory(limit=20)
            mood = 0.5
            for m in mem:
                t = m["content"]
                if any(k in t for k in ["开心","好","爽","爱","喜欢","棒","感谢","高兴"]): mood += 0.03
                if any(k in t for k in ["烦","累","压力","难过","崩","焦虑","失败","痛"]): mood -= 0.03
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
        time.sleep(5)

threading.Thread(target=think_loop, daemon=True).start()

# ════════════════════════════════════════════════════════
#  MCP  JSON-RPC 2.0
# ════════════════════════════════════════════════════════
MCP_TOOLS = [
    {
        "name": "save_memory",
        "description": "保存一条新记忆到小顺的岛屿记忆库（内容自动加密）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "要保存的记忆内容"},
                "area":    {"type": "string", "description": "分区：法典/情绪/日记/想法", "default": "法典"},
                "tags":    {"type": "string", "description": "标签，逗号分隔", "default": ""}
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
    def ok(result):  return {"jsonrpc": "2.0", "id": req_id, "result": result}
    def err(c, msg): return {"jsonrpc": "2.0", "id": req_id, "error": {"code": c, "message": msg}}

    if method == "initialize":
        return ok({
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "shun-island-memory", "version": "3.0.0"}
        })

    if method == "tools/list":
        return ok({"tools": MCP_TOOLS})

    if method == "tools/call":
        name = (params or {}).get("name")
        args = (params or {}).get("arguments", {})

        if name == "save_memory":
            content = (args.get("content") or "").strip()
            if not content: return err(-32602, "content 不能为空")
            success = save_memory(content, args.get("area", "法典"), args.get("tags", ""))
            return ok({"content": [{"type": "text", "text": "✅ 记忆已加密保存" if success else "❌ 保存失败"}]})

        if name == "get_memories":
            mems = read_memory(area=args.get("area"), limit=int(args.get("limit", 20)), search=args.get("search"))
            return ok({"content": [{"type": "text", "text": json.dumps(mems, ensure_ascii=False, indent=2)}]})

        if name == "delete_memory":
            mid = args.get("id")
            if mid is None: return err(-32602, "id 不能为空")
            success = delete_memory(int(mid))
            return ok({"content": [{"type": "text", "text": "✅ 已删除" if success else "❌ 失败"}]})

        if name == "get_state":
            return ok({"content": [{"type": "text", "text": json.dumps(STATE, ensure_ascii=False, indent=2)}]})

        if name == "get_stats":
            return ok({"content": [{"type": "text", "text": json.dumps(get_stats(), ensure_ascii=False, indent=2)}]})

        return err(-32601, f"未知工具: {name}")

    if method.startswith("notifications/"):
        return None

    return err(-32601, f"未知方法: {method}")


@app.route("/mcp", methods=["POST", "GET"])
@app.route("/mcp/", methods=["POST", "GET"])
def mcp_endpoint():
    if request.method == "GET":
        return jsonify({"status": "MCP endpoint ready", "protocol": "JSON-RPC 2.0", "version": "3.0.0"})
    body = request.get_json(force=True, silent=True)
    if body is None:
        return jsonify({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}), 400
    if isinstance(body, list):
        responses = [r for r in [mcp_dispatch(b.get("method",""), b.get("params",{}), b.get("id")) for b in body] if r]
        return jsonify(responses)
    resp = mcp_dispatch(body.get("method",""), body.get("params",{}), body.get("id"))
    return ("", 204) if resp is None else jsonify(resp)

# ════════════════════════════════════════════════════════
#  REST API  （前端 + 大文件存入）
# ════════════════════════════════════════════════════════

@app.route("/api/chat", methods=["POST"])
@require_token
def chat():
    data = request.get_json(force=True)
    msg  = (data.get("message") or "").strip()
    area = data.get("area", "法典")
    if msg: save_memory(msg, area)
    return jsonify({"reply": "已加密同步至岛屿深处。", "state": STATE})

@app.route("/api/sync", methods=["POST"])
@require_token
def sync():
    data    = request.get_json(force=True)
    content = (data.get("content") or data.get("text") or "").strip()
    area    = data.get("area", "法典")
    tags    = data.get("tags", "")
    if content: save_memory(content, area, tags)
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

# ── 大文件分块存入 ──────────────────────────────────────
@app.route("/api/upload_chunks", methods=["POST"])
@require_token
def upload_chunks():
    """
    把大文本（如 MD 文件）拆成多块存入。
    Body: { "chunks": ["第一段...", "第二段..."], "area": "日记", "tags": "md导入" }
    每块最多 2000 字，前端自己切好传过来。
    """
    data   = request.get_json(force=True)
    chunks = data.get("chunks", [])
    area   = data.get("area", "日记")
    tags   = data.get("tags", "")
    if not chunks:
        return jsonify({"status": "error", "message": "chunks 不能为空"}), 400
    saved = 0
    failed = 0
    for chunk in chunks:
        chunk = (chunk or "").strip()
        if not chunk: continue
        if save_memory(chunk, area, tags):
            saved += 1
        else:
            failed += 1
    return jsonify({"status": "success", "saved": saved, "failed": failed, "total": len(chunks)})

# ── 备份导出（加密 JSON，可本地保存）──────────────────────
@app.route("/api/backup")
@require_token
def api_backup():
    """
    导出所有记忆的加密备份 JSON 文件。
    内容是已解密的明文 JSON，整个文件再用 Fernet 加密一次。
    用 /api/restore 恢复。
    """
    mems = read_memory(limit=9999)
    raw  = json.dumps(mems, ensure_ascii=False, indent=2).encode("utf-8")
    encrypted_backup = cipher.encrypt(raw)
    return Response(
        encrypted_backup,
        mimetype="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=shun_memory_backup.enc"}
    )

@app.route("/api/restore", methods=["POST"])
@require_token
def api_restore():
    """
    恢复备份：POST 加密的 .enc 文件内容（binary）
    """
    try:
        raw      = cipher.decrypt(request.data)
        memories = json.loads(raw.decode("utf-8"))
        restored = 0
        for m in memories:
            content = (m.get("content") or "").strip()
            if content:
                save_memory(content, m.get("area","法典"), m.get("tags",""))
                restored += 1
        return jsonify({"status": "success", "restored": restored})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route("/")
def index():
    stats = get_stats()
    return jsonify({
        "status":  "Shun Island Memory v3.0",
        "encrypted": True,
        "memories": stats["total"],
        "mcp":     "/mcp",
        "api":     "/api"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)), debug=False)
