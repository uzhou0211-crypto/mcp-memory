import os
import json
import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ========== 内存 ==========
STATE = {
    "mood": 0.5,
    "energy": 0.5,
    "last_thought": "初始化完成",
    "active_message": "我在这里"
}

MEMORIES = []
AUTO_ID = 1

# ========== 5个核心功能 ==========

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
    return len(MEMORIES) != before

def get_state():
    return STATE

def get_stats():
    return {
        "count": len(MEMORIES),
        "last_id": AUTO_ID - 1
    }

# ========== MCP ==========
@app.route("/mcp", methods=["POST", "GET"])
def mcp():
    if request.method == "GET":
        return jsonify({"status": "ok", "version": "5.0-mcp"})

    data = request.get_json(force=True)
    method = data.get("method")
    params = data.get("params", {})
    req_id = data.get("id")

    def ok(result):
        return jsonify({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result
        })

    # 初始化
    if method == "initialize":
        return ok({
            "name": "memory-server",
            "version": "5.0"
        })

    # 工具列表（关键）
    if method == "tools/list":
        return ok({
            "tools": [
                {"name": "save_memory"},
                {"name": "get_memories"},
                {"name": "delete_memory"},
                {"name": "get_state"},
                {"name": "get_stats"}
            ]
        })

    # 调用工具
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})

        if name == "save_memory":
            m = save_memory(args.get("content", ""))
            return ok(m)

        if name == "get_memories":
            return ok(get_memories())

        if name == "delete_memory":
            return ok(delete_memory(args.get("id")))

        if name == "get_state":
            return ok(get_state())

        if name == "get_stats":
            return ok(get_stats())

        return ok({"error": "unknown tool"})

    return ok({"error": "unknown method"})


# ========== 给你网页用的API（关键） ==========
@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    msg = data.get("message")

    mem = save_memory(msg)

    return jsonify({
        "reply": "已保存：" + msg,
        "state": STATE
    })


@app.route("/api/read")
def read():
    return jsonify(get_memories())


@app.route("/api/state")
def state():
    return jsonify(get_state())


@app.route("/api/delete/<int:mid>", methods=["DELETE"])
def delete(mid):
    return jsonify({"ok": delete_memory(mid)})


@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "db": True,
        "version": "5.0"
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
