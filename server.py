import os
import json
import datetime
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# =====================
# 内存存储
# =====================
MEMORIES = []
AUTO_ID = 1

def save_memory(content):
    global AUTO_ID
    mem = {
        "id": AUTO_ID,
        "content": content,
        "time": datetime.datetime.utcnow().isoformat(),
        "area": "法典"
    }
    AUTO_ID += 1
    MEMORIES.append(mem)
    return mem

def get_memories():
    return list(reversed(MEMORIES))

def delete_memory(mid):
    global MEMORIES
    before = len(MEMORIES)
    MEMORIES = [m for m in MEMORIES if m["id"] != mid]
    return before != len(MEMORIES)

# =====================
# MCP 工具定义
# =====================
TOOLS = [
    {
        "name": "save_memory",
        "description": "保存一条记忆到记忆岛",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "要保存的记忆内容"}
            },
            "required": ["content"]
        }
    },
    {
        "name": "get_memories",
        "description": "读取所有已保存的记忆",
        "inputSchema": {
            "type": "object",
            "properties": {}
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
    }
]

# =====================
# JSON-RPC 处理
# =====================
def handle_rpc(data):
    method = data.get("method", "")
    req_id = data.get("id")
    params = data.get("params", {})

    def ok(result):
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def err(code, message):
        return {"jsonrpc": "2.0", "id": req_id,
                "error": {"code": code, "message": message}}

    if method == "initialize":
        return ok({
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "memory-island", "version": "9.0"}
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
            result = save_memory(args.get("content", ""))
        elif name == "get_memories":
            result = get_memories()
        elif name == "delete_memory":
            result = {"deleted": delete_memory(args.get("id"))}
        else:
            return err(-32601, f"未知工具: {name}")

        return ok({
            "content": [
                {"type": "text", "text": json.dumps(result, ensure_ascii=False)}
            ]
        })

    return err(-32601, f"未知方法: {method}")


# =====================
# MCP 主端点 —— Streamable HTTP 模式
# =====================
@app.route("/mcp", methods=["GET", "POST", "OPTIONS"])
def mcp():
    if request.method == "OPTIONS":
        return _cors_response("", 204)

    if request.method == "GET":
        return _cors_response("", 204)

    raw = request.get_data(as_text=True)
    try:
        data = json.loads(raw)
    except Exception:
        resp_body = json.dumps({
            "jsonrpc": "2.0", "id": None,
            "error": {"code": -32700, "message": "Parse error"}
        })
        return _cors_response(resp_body, 400, "application/json")

    if isinstance(data, list):
        results = [handle_rpc(item) for item in data]
        results = [r for r in results if r is not None]
        if not results:
            return _cors_response("", 202)
        return _cors_response(json.dumps(results, ensure_ascii=False), 200, "application/json")

    result = handle_rpc(data)
    if result is None:
        return _cors_response("", 202)

    return _cors_response(json.dumps(result, ensure_ascii=False), 200, "application/json")


def _cors_response(body, status=200, content_type="text/plain"):
    resp = Response(body, status=status, content_type=content_type)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Mcp-Session-Id"
    return resp


# =====================
# 普通 REST API
# =====================
@app.route("/api/read")
def api_read():
    return jsonify(get_memories())

@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(force=True)
    msg = data.get("message", "")
    mem = save_memory(msg)
    return jsonify({"reply": "已保存：" + msg, "memory": mem})

@app.route("/api/delete/<int:mid>", methods=["DELETE"])
def api_delete(mid):
    return jsonify({"ok": delete_memory(mid)})

@app.route("/health")
def health():
    return jsonify({"status": "ok", "version": "9.0", "memories": len(MEMORIES)})


# =====================
# 启动
# =====================
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 3000)),
        threaded=True
    )
