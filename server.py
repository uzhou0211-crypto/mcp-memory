import os
import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ======================
# 内存系统
# ======================
STATE = {
    "mood": 0.5,
    "energy": 0.5,
    "active_message": "我在这里",
    "last_thought": "初始化完成"
}

MEMORIES = []
AUTO_ID = 1


# ======================
# Memory Core
# ======================
def save_memory(content, area="法典"):
    global AUTO_ID
    mem = {
        "id": AUTO_ID,
        "time": datetime.datetime.utcnow().isoformat(),
        "area": area,
        "content": content,
        "tags": ""
    }
    AUTO_ID += 1
    MEMORIES.append(mem)
    return mem


def get_memories(limit=50):
    return MEMORIES[-limit:][::-1]


def delete_memory(mid):
    global MEMORIES
    before = len(MEMORIES)
    MEMORIES = [m for m in MEMORIES if m["id"] != mid]
    return before != len(MEMORIES)


def get_state():
    return STATE


def get_stats():
    return {
        "count": len(MEMORIES),
        "last_id": AUTO_ID - 1
    }


# ======================
# Web API（给你的网页用）
# ======================
@app.route("/")
def home():
    return jsonify({"status": "running", "db": True, "version": "6.0"})


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(force=True)
    msg = data.get("message", "")

    mem = save_memory(msg)

    return jsonify({
        "reply": "已记录：" + msg,
        "state": STATE,
        "memory": mem
    })


@app.route("/api/read")
def api_read():
    return jsonify(get_memories())


@app.route("/api/state")
def api_state():
    return jsonify(get_state())


@app.route("/api/delete/<int:mid>", methods=["DELETE"])
def api_delete(mid):
    return jsonify({"ok": delete_memory(mid)})


# ======================
# MCP STANDARD（关键修复）
# ======================
@app.route("/mcp", methods=["POST", "GET"])
def mcp():
    if request.method == "GET":
        return jsonify({"status": "ok", "version": "6.0-mcp"})

    data = request.get_json(force=True)

    method = data.get("method")
    req_id = data.get("id", 1)
    params = data.get("params", {})

    def ok(result):
        return jsonify({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result
        })

    # -------------------------
    # initialize
    # -------------------------
    if method == "initialize":
        return ok({
            "name": "memory-island",
            "version": "6.0"
        })

    # -------------------------
    # tools/list（Claude必须标准）
    # -------------------------
    if method == "tools/list":
        return ok({
            "tools": [
                {
                    "name": "save_memory",
                    "description": "Save a memory",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string"}
                        },
                        "required": ["content"]
                    }
                },
                {
                    "name": "get_memories",
                    "description": "Get memories",
                    "input_schema": {
                        "type": "object",
                        "properties": {}
                    }
                },
                {
                    "name": "delete_memory",
                    "description": "Delete memory",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "number"}
                        },
                        "required": ["id"]
                    }
                },
                {
                    "name": "get_state",
                    "description": "Get state",
                    "input_schema": {"type": "object"}
                },
                {
                    "name": "get_stats",
                    "description": "Get stats",
                    "input_schema": {"type": "object"}
                }
            ]
        })

    # -------------------------
    # tools/call
    # -------------------------
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})

        if name == "save_memory":
            return ok(save_memory(args.get("content", "")))

        if name == "get_memories":
            return ok(get_memories())

        if name == "delete_memory":
            return ok({"deleted": delete_memory(args.get("id"))})

        if name == "get_state":
            return ok(get_state())

        if name == "get_stats":
            return ok(get_stats())

        return ok({"error": "unknown tool"})

    return ok({"error": "unknown method"})


# ======================
# 启动
# ======================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))

