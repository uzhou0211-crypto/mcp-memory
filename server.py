import os
import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# =====================
# 内存
# =====================
MEMORIES = []
STATE = {
    "mood": 0.5,
    "energy": 0.5,
    "active_message": "我在这里",
    "last_thought": "初始化完成"
}
AUTO_ID = 1


# =====================
# 工具函数
# =====================
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
# 普通 API（网页用）
# =====================
@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    msg = data.get("message", "")
    mem = save_memory(msg)

    return jsonify({
        "reply": "已保存：" + msg,
        "state": STATE,
        "memory": mem
    })


@app.route("/api/read")
def read():
    return jsonify(get_memories())


@app.route("/api/state")
def state():
    return jsonify(STATE)


@app.route("/api/delete/<int:mid>", methods=["DELETE"])
def delete(mid):
    return jsonify({"ok": delete_memory(mid)})


# =====================
# MCP（关键：Claude依赖这个）
# =====================
@app.route("/mcp", methods=["GET", "POST"])
def mcp():
    # Claude探活
    if request.method == "GET":
        return jsonify({"status": "ok", "version": "7.0-mcp"})

    data = request.get_json(force=True)

    method = data.get("method")
    req_id = data.get("id", 1)
    params = data.get("params", {})

    def response(result):
        return jsonify({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result
        })

    # -------------------------
    # 1. initialize
    # -------------------------
    if method == "initialize":
        return response({
            "name": "memory-island",
            "version": "7.0"
        })

    # -------------------------
    # 2. tools/list（Claude最关键）
    # -------------------------
    if method == "tools/list":
        return response({
            "tools": [
                {
                    "name": "save_memory",
                    "description": "保存记忆",
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
                    "description": "获取记忆",
                    "input_schema": {"type": "object"}
                },
                {
                    "name": "delete_memory",
                    "description": "删除记忆",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "number"}
                        },
                        "required": ["id"]
                    }
                }
            ]
        })

    # -------------------------
    # 3. tools/call
    # -------------------------
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})

        if name == "save_memory":
            return response(save_memory(args.get("content", "")))

        if name == "get_memories":
            return response(get_memories())

        if name == "delete_memory":
            return response({"deleted": delete_memory(args.get("id"))})

        return response({"error": "unknown tool"})

    return response({"error": "unknown method"})


# =====================
# 启动
# =====================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
