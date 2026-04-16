import os
import json
import datetime
import queue
import threading
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# =====================
# 内存存储
# =====================
MEMORIES = []
STATE = {"mood": 0.5, "energy": 0.5, "active_message": "我在这里", "last_thought": "初始化完成"}
AUTO_ID = 1
SSE_QUEUES = {}
SSE_LOCK = threading.Lock()

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
# JSON-RPC 处理核心
# =====================
def handle_rpc(data):
    method = data.get("method", "")
    req_id = data.get("id", 1)
    params = data.get("params", {})

    def ok(result):
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def err(code, message):
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}

    # 握手
    if method == "initialize":
        return ok({
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "memory-island", "version": "8.0"}
        })

    # 初始化通知，不需要回复
    if method == "notifications/initialized":
        return None

    # 列出工具
    if method == "tools/list":
        return ok({"tools": TOOLS})

    # 调用工具
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

    # ping/pong
    if method == "ping":
        return ok({})

    return err(-32601, f"未知方法: {method}")


# =====================
# SSE 端点（Claude.ai 连接入口）
# =====================
@app.route("/mcp", methods=["GET"])
def mcp_sse():
    session_id = os.urandom(8).hex()
    msg_queue = queue.Queue()

    with SSE_LOCK:
        SSE_QUEUES[session_id] = msg_queue

    def generate():
        try:
            # 告诉 Claude 消息要 POST 到哪里
            endpoint_url = request.host_url.rstrip("/") + f"/mcp/message?session={session_id}"
            yield f"event: endpoint\ndata: {endpoint_url}\n\n"

            # 保持连接
            while True:
                try:
                    msg = msg_queue.get(timeout=25)
                    yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                except queue.Empty:
                    yield ": ping\n\n"  # 心跳，防止 Railway / nginx 断连
        finally:
            with SSE_LOCK:
                SSE_QUEUES.pop(session_id, None)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


# =====================
# 消息接收端点
# =====================
@app.route("/mcp/message", methods=["POST"])
def mcp_message():
    session_id = request.args.get("session")
    data = request.get_json(force=True)

    result = handle_rpc(data)

    if result is None:
        return "", 202

    # 如果有 SSE 会话就通过队列推送，否则直接 HTTP 返回
    if session_id:
        with SSE_LOCK:
            q = SSE_QUEUES.get(session_id)
        if q:
            q.put(result)
            return "", 202

    return jsonify(result)


# =====================
# 普通 REST API（网页/调试用）
# =====================
@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    msg = data.get("message", "")
    mem = save_memory(msg)
    return jsonify({"reply": "已保存：" + msg, "state": STATE, "memory": mem})

@app.route("/api/read")
def read():
    return jsonify(get_memories())

@app.route("/api/state")
def api_state():
    return jsonify(STATE)

@app.route("/api/delete/<int:mid>", methods=["DELETE"])
def api_delete(mid):
    return jsonify({"ok": delete_memory(mid)})

@app.route("/health")
def health():
    return jsonify({"status": "ok", "version": "8.0", "memories": len(MEMORIES)})


# =====================
# 启动
# =====================
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 3000)),
        threaded=True   # 必须开多线程，SSE 长连接才不会阻塞其他请求
    )
