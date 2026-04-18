import os
import json
import datetime
import io
import zipfile
import math
import threading
import time
import psycopg2
from flask import Flask, request, jsonify, Response, send_file, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

DATABASE_URL = os.environ.get("DATABASE_URL")
API_TOKEN = os.environ.get("API_TOKEN", "0211415")

STATE = {
    "mood": 0.5,
    "energy": 0.5,
    "active_message": "\u6211\u5728\u8fd9\u91cc",
    "last_thought": "\u521d\u59cb\u5316\u5b8c\u6210"
}

SURFACED = []


def check_token(req):
    token = req.headers.get("X-Token") or req.args.get("token")
    return token == API_TOKEN


def auth_error():
    return jsonify({"error": "unauthorized"}), 401


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS memories ("
                "id SERIAL PRIMARY KEY,"
                "content TEXT NOT NULL,"
                "area TEXT DEFAULT '\u6cd5\u5178',"
                "tags TEXT DEFAULT '',"
                "weight FLOAT DEFAULT 1.0,"
                "decay FLOAT DEFAULT 0.0,"
                "recall INT DEFAULT 0,"
                "time TIMESTAMP DEFAULT NOW(),"
                "last_recall TIMESTAMP DEFAULT NOW()"
                ")"
            )
            for col, defn in [
                ("weight", "FLOAT DEFAULT 1.0"),
                ("decay", "FLOAT DEFAULT 0.0"),
                ("recall", "INT DEFAULT 0"),
                ("last_recall", "TIMESTAMP DEFAULT NOW()"),
            ]:
                try:
                    cur.execute("ALTER TABLE memories ADD COLUMN " + col + " " + defn)
                except Exception:
                    pass
        conn.commit()


AREA_RULES = {
    "\u60c5\u7eea": [
        "\u96be\u8fc7", "\u5f00\u5fc3", "\u6124\u6012", "\u7126\u8651",
        "\u538b\u529b", "\u5bb3\u6015", "\u5b64\u72ec", "\u5e78\u798f",
        "\u4f24\u5fc3", "\u9ad8\u5174", "\u70e6\u8e81", "\u59d4\u5c48",
        "\u611f\u52a8", "\u54ed", "\u7b11", "\u5fc3\u60c5", "\u60c5\u7eea",
        "\u611f\u53d7", "\u559c\u6b22", "\u8ba8\u538c", "\u7231", "\u6068",
        "\u7d2f", "\u75b2\u60eb"
    ],
    "\u65e5\u8bb0": [
        "\u4eca\u5929", "\u6628\u5929", "\u65e9\u4e0a", "\u665a\u4e0a",
        "\u4e0b\u5348", "\u5403\u4e86", "\u53bb\u4e86", "\u89c1\u4e86",
        "\u505a\u4e86", "\u53d1\u751f", "\u4e8b\u60c5", "\u65e5\u8bb0",
        "\u8bb0\u5f55", "\u751f\u6d3b", "\u65e5\u5e38", "\u4e0a\u73ed",
        "\u4e0a\u5b66", "\u7761\u89c9"
    ],
    "\u60f3\u6cd5": [
        "\u6211\u89c9\u5f97", "\u6211\u8ba4\u4e3a", "\u611f\u89c9",
        "\u4e5f\u8bb8", "\u53ef\u80fd", "\u5e94\u8be5", "\u4e3a\u4ec0\u4e48",
        "\u600e\u4e48", "\u60f3\u5230", "\u7a81\u7136", "\u53d1\u73b0",
        "\u601d\u8003", "\u60f3\u6cd5", "\u89c2\u70b9", "\u7406\u89e3",
        "\u610f\u8bc6\u5230", "\u5982\u679c", "\u5047\u5982", "\u672a\u6765",
        "\u8ba1\u5212", "\u76ee\u6807", "\u68a6\u60f3"
    ],
}


def auto_classify(content):
    scores = {}
    for area, keywords in AREA_RULES.items():
        scores[area] = sum(1 for kw in keywords if kw in content)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "\u6cd5\u5178"


def jaccard(a, b):
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def find_duplicate(content, threshold=0.75):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, content FROM memories ORDER BY id DESC LIMIT 500")
            rows = cur.fetchall()
    best_id, best_score = None, 0
    for (mid, existing) in rows:
        score = jaccard(content, existing)
        if score > best_score:
            best_id, best_score = mid, score
    return best_id if best_score >= threshold else None


def calc_decay(last_recall_dt, recall_count):
    days = (datetime.datetime.utcnow() - last_recall_dt).total_seconds() / 86400
    stability = 1 + (recall_count or 0) * 0.5
    return round(min(1 - math.exp(-days / stability), 0.99), 4)


def update_decay_job():
    while True:
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, last_recall, recall FROM memories")
                    rows = cur.fetchall()
                for (mid, last_recall, recall) in rows:
                    d = calc_decay(last_recall, recall or 0)
                    with conn.cursor() as cur:
                        cur.execute("UPDATE memories SET decay=%s WHERE id=%s", (d, mid))
                conn.commit()
        except Exception:
            pass
        time.sleep(3600)


def surface_memory_job():
    while True:
        time.sleep(1800)
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, content, area FROM memories"
                        " WHERE decay < 0.8"
                        " ORDER BY weight DESC, decay ASC, last_recall ASC"
                        " LIMIT 20"
                    )
                    rows = cur.fetchall()
            if rows:
                import random
                row = random.choice(rows)
                mid, content, area = row
                snippet = content[:40] + ("..." if len(content) > 40 else "")
                STATE["active_message"] = "\u5fd6\u7136\u60f3\u8d77\uff1a" + snippet
                STATE["last_thought"] = "[" + area + "] " + snippet
                SURFACED.append({
                    "id": mid, "content": content, "area": area,
                    "time": datetime.datetime.utcnow().isoformat()
                })
                if len(SURFACED) > 20:
                    SURFACED.pop(0)
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE memories SET recall=recall+1, last_recall=NOW() WHERE id=%s",
                            (mid,)
                        )
                    conn.commit()
        except Exception:
            pass


def save_memory(content, area="\u6cd5\u5178", tags="", weight=1.0):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO memories (content, area, tags, weight)"
                " VALUES (%s, %s, %s, %s)"
                " RETURNING id, content, area, tags, time",
                (content, area, tags, weight)
            )
            row = cur.fetchone()
        conn.commit()
    return {
        "id": row[0], "content": row[1], "area": row[2],
        "tags": row[3], "time": row[4].isoformat()
    }


def get_memories(area=None, search=None, limit=200):
    with get_conn() as conn:
        with conn.cursor() as cur:
            sql = "SELECT id, content, area, tags, time, weight, decay, recall FROM memories"
            conds, vals = [], []
            if area:
                conds.append("area = %s")
                vals.append(area)
            if search:
                conds.append("content ILIKE %s")
                vals.append("%" + search + "%")
            if conds:
                sql += " WHERE " + " AND ".join(conds)
            sql += " ORDER BY id DESC LIMIT %s"
            vals.append(limit)
            cur.execute(sql, vals)
            rows = cur.fetchall()
    return [
        {"id": r[0], "content": r[1], "area": r[2], "tags": r[3],
         "time": r[4].isoformat(), "weight": r[5], "decay": r[6], "recall": r[7]}
        for r in rows
    ]


def delete_memory(mid):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM memories WHERE id=%s", (mid,))
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
        "last_saved": last.isoformat() if last else None,
        "surfaced_count": len(SURFACED)
    }


TOOLS = [
    {
        "name": "save_memory",
        "description": "\u4fdd\u5b58\u4e00\u6761\u8bb0\u5fc6\u5230\u8bb0\u5fc6\u5c9b",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "area": {"type": "string"},
                "tags": {"type": "string"}
            },
            "required": ["content"]
        }
    },
    {
        "name": "get_memories",
        "description": "\u8bfb\u53d6\u8bb0\u5fc6",
        "inputSchema": {
            "type": "object",
            "properties": {
                "area": {"type": "string"},
                "search": {"type": "string"},
                "limit": {"type": "number"}
            }
        }
    },
    {
        "name": "delete_memory",
        "description": "\u5220\u9664\u4e00\u6761\u8bb0\u5fc6",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "number"}},
            "required": ["id"]
        }
    },
    {
        "name": "get_state",
        "description": "\u83b7\u53d6\u5c9b\u5c7f\u72b6\u6001",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_stats",
        "description": "\u83b7\u53d6\u8bb0\u5fc6\u5e93\u7edf\u8ba1",
        "inputSchema": {"type": "object", "properties": {}}
    }
]


def handle_rpc(data):
    method = data.get("method", "")
    req_id = data.get("id")
    params = data.get("params", {})

    def ok(r):
        return {"jsonrpc": "2.0", "id": req_id, "result": r}

    def err(c, m):
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": c, "message": m}}

    if method == "initialize":
        return ok({
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "memory-island", "version": "13.0"}
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
            area = args.get("area") or auto_classify(args.get("content", ""))
            result = save_memory(args.get("content", ""), area, args.get("tags", ""))
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
            return err(-32601, "unknown tool")
        return ok({"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]})
    return err(-32601, "unknown method")


@app.route("/mcp", methods=["GET", "POST", "OPTIONS"])
def mcp():
    if request.method == "OPTIONS":
        return _cors("", 204)
    if request.method == "GET":
        return _cors("", 204)
    try:
        data = json.loads(request.get_data(as_text=True))
    except Exception:
        return _cors(
            json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}),
            400, "application/json"
        )
    if isinstance(data, list):
        results = [r for r in (handle_rpc(d) for d in data) if r is not None]
        return _cors(
            json.dumps(results, ensure_ascii=False) if results else "",
            200 if results else 202, "application/json"
        )
    result = handle_rpc(data)
    if result is None:
        return _cors("", 202)
    return _cors(json.dumps(result, ensure_ascii=False), 200, "application/json")


def _cors(body, status=200, ct="text/plain"):
    r = Response(body, status=status, content_type=ct)
    r.headers["Access-Control-Allow-Origin"] = "*"
    r.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    r.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Mcp-Session-Id, X-Token"
    return r


@app.route("/api/chat", methods=["POST"])
def api_chat():
    if not check_token(request):
        return auth_error()
    data = request.get_json(force=True)
    msg = data.get("message", "")
    area = data.get("area") or auto_classify(msg)
    mem = save_memory(msg, area)
    return jsonify({"reply": "\u5df2\u540c\u6b65\u81f3" + area + "\u3002", "state": get_state(), "memory": mem})


@app.route("/api/read")
def api_read():
    if not check_token(request):
        return auth_error()
    return jsonify(get_memories(
        area=request.args.get("area"),
        search=request.args.get("search"),
        limit=int(request.args.get("limit", 200))
    ))


@app.route("/api/delete/<int:mid>", methods=["DELETE"])
def api_delete(mid):
    if not check_token(request):
        return auth_error()
    return jsonify({"ok": delete_memory(mid)})


@app.route("/api/state")
def api_state():
    if not check_token(request):
        return auth_error()
    return jsonify(get_state())


@app.route("/api/stats")
def api_stats():
    if not check_token(request):
        return auth_error()
    return jsonify(get_stats())


@app.route("/api/surfaced")
def api_surfaced():
    if not check_token(request):
        return auth_error()
    return jsonify(SURFACED[-10:])


@app.route("/api/upload_chunks", methods=["POST"])
def api_upload_chunks():
    if not check_token(request):
        return auth_error()
    data = request.get_json(force=True)
    chunks = data.get("chunks", [])
    area = data.get("area", "")
    tags = data.get("tags", "")
    dedup = data.get("dedup", True)
    saved = merged = 0
    with get_conn() as conn:
        with conn.cursor() as cur:
            for c in chunks:
                if not c or not c.strip():
                    continue
                content = c.strip()
                if dedup:
                    dup_id = find_duplicate(content)
                    if dup_id:
                        cur.execute(
                            "UPDATE memories SET recall=recall+1, weight=weight+0.2, last_recall=NOW() WHERE id=%s",
                            (dup_id,)
                        )
                        merged += 1
                        continue
                real_area = area or auto_classify(content)
                cur.execute(
                    "INSERT INTO memories (content, area, tags) VALUES (%s, %s, %s)",
                    (content, real_area, tags)
                )
                saved += 1
        conn.commit()
    return jsonify({"saved": saved, "merged": merged})


@app.route("/api/backup")
def api_backup():
    if not check_token(request):
        return auth_error()
    mems = get_memories(limit=99999)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("memories.json", json.dumps(mems, ensure_ascii=False, indent=2))
        z.writestr("state.json", json.dumps(STATE, ensure_ascii=False, indent=2))
    buf.seek(0)
    return send_file(buf, mimetype="application/octet-stream", as_attachment=True,
                     download_name="shun_memory_" + str(datetime.date.today()) + ".enc")


@app.route("/api/restore", methods=["POST"])
def api_restore():
    if not check_token(request):
        return auth_error()
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
                        (m.get("content", ""), m.get("area", "\u6cd5\u5178"), m.get("tags", ""))
                    )
            conn.commit()
        return jsonify({"restored": len(mems)})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/book-note", methods=["POST"])
def api_book_note():
    if not check_token(request):
        return auth_error()
    data = request.get_json(force=True)
    quote = data.get("quote", "").strip()
    note = data.get("note", "").strip()
    book = data.get("book", "").strip()
    if not quote and not note:
        return jsonify({"error": "empty"}), 400
    parts = []
    if book:
        parts.append("\u300a" + book + "\u300b")
    if quote:
        parts.append("\u300c" + quote + "\u300d")
    if note:
        parts.append("\u6279\u6ce8\uff1a" + note)
    content = "\n".join(parts)
    mem = save_memory(content, area="\u8bfb\u4e66", tags=book)
    return jsonify({"ok": True, "memory": mem})


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/book")
def book():
    return render_template("book.html")


@app.route("/health")
def health():
    try:
        stats = get_stats()
        return jsonify({"status": "ok", "version": "13.0", "memories": stats["total"], "db": "connected"})
    except Exception as e:
        return jsonify({"status": "error", "db": str(e)}), 500


if __name__ == "__main__":
    init_db()
    threading.Thread(target=update_decay_job, daemon=True).start()
    threading.Thread(target=surface_memory_job, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)), threaded=True)
