import os
import json
import datetime
import io
import zipfile
import math
import threading
import time
import psycopg2
import psycopg2.extras
from flask import Flask, request, jsonify, Response, send_file, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:iTdnKHeCrIAXletVRPmyCKSlFojZWoiu@postgres.railway.internal:5432/railway")
API_TOKEN    = os.environ.get("API_TOKEN", "0211415")

STATE = {
    "mood": 0.5,
    "energy": 0.5,
    "active_message": "我在这里",
    "last_thought": "初始化完成"
}

# =====================
# 密码验证
# =====================
def check_token(req):
    """除 / 和 /health 之外所有接口都需要验证"""
    token = req.headers.get("X-Token") or req.args.get("token")
    return token == API_TOKEN

def auth_error():
    return jsonify({"error": "unauthorized"}), 401

# =====================
# 数据库
# =====================
def get_conn():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id        SERIAL PRIMARY KEY,
                    content   TEXT NOT NULL,
                    area      TEXT DEFAULT '法典',
                    tags      TEXT DEFAULT '',
                    weight    FLOAT DEFAULT 1.0,
                    decay     FLOAT DEFAULT 0.0,
                    recall    INT   DEFAULT 0,
                    time      TIMESTAMP DEFAULT NOW(),
                    last_recall TIMESTAMP DEFAULT NOW()
                )
            """)
            # 新列兼容旧表
            for col, defn in [
                ("weight",      "FLOAT DEFAULT 1.0"),
                ("decay",       "FLOAT DEFAULT 0.0"),
                ("recall",      "INT DEFAULT 0"),
                ("last_recall", "TIMESTAMP DEFAULT NOW()"),
            ]:
                try:
                    cur.execute(f"ALTER TABLE memories ADD COLUMN {col} {defn}")
                except Exception:
                    pass
        conn.commit()

# =====================
# 自动分类（关键词规则，零 token）
# =====================
AREA_RULES = {
    "情绪": ["难过", "开心", "愤怒", "焦虑", "压力", "害怕", "孤独", "幸福", "伤心",
             "高兴", "烦躁", "委屈", "感动", "哭", "笑", "心情", "情绪", "感受",
             "喜欢", "讨厌", "爱", "恨", "累", "疲惫"],
    "日记": ["今天", "昨天", "早上", "晚上", "下午", "吃了", "去了", "见了", "做了",
             "发生", "事情", "日记", "记录", "生活", "日常", "上班", "上学", "睡觉"],
    "想法": ["我觉得", "我认为", "感觉", "也许", "可能", "应该", "为什么", "怎么",
             "想到", "突然", "发现", "思考", "想法", "观点", "理解", "意识到",
             "如果", "假如", "未来", "计划", "目标", "梦想"],
    "法典": [],  # 默认
}

def auto_classify(content):
    content_lower = content.lower()
    scores = {area: 0 for area in AREA_RULES}
    for area, keywords in AREA_RULES.items():
        for kw in keywords:
            if kw in content_lower:
                scores[area] += 1
    scores.pop("法典")
    if not scores or max(scores.values()) == 0:
        return "法典"
    return max(scores, key=scores.get)

# =====================
# 去重（Jaccard 相似度，零 token）
# =====================
def jaccard(a, b):
    sa = set(a)
    sb = set(b)
    if not sa and not sb:
        return 1.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0

def find_duplicate(content, threshold=0.75):
    """和最近 500 条比较，返回最相似那条的 id 和重复次数字段，没有则返回 None"""
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

# =====================
# 记忆衰减（模拟遗忘曲线）
# =====================
def calc_decay(last_recall_dt, recall_count):
    """Ebbinghaus 遗忘曲线简化版：时间越久、回忆次数越少，decay 越高"""
    days = (datetime.datetime.utcnow() - last_recall_dt).total_seconds() / 86400
    stability = 1 + recall_count * 0.5   # 回忆越多越稳定
    decay = 1 - math.exp(-days / stability)
    return round(min(decay, 0.99), 4)

def update_decay_job():
    """每小时更新所有记忆的 decay 值"""
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

# =====================
# 主动浮现记忆（模拟人脑主动联想）
# =====================
SURFACED = []   # 最近浮现的记忆，供前端轮询

def surface_memory_job():
    """每 30 分钟从记忆库里随机浮现一条高权重记忆，更新 STATE"""
    while True:
        time.sleep(1800)
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    # 优先浮现：权重高、衰减低、最近没被回忆过的
                    cur.execute("""
                        SELECT id, content, area
                        FROM memories
                        WHERE decay < 0.8
                        ORDER BY weight DESC, decay ASC, last_recall ASC
                        LIMIT 20
                    """)
                    rows = cur.fetchall()
            if rows:
                import random
                row = random.choice(rows)
                mid, content, area = row
                snippet = content[:40] + ("…" if len(content) > 40 else "")
                STATE["active_message"] = f"忽然想起：{snippet}"
                STATE["last_thought"]   = f"[{area}] {snippet}"
                SURFACED.append({
                    "id": mid, "content": content, "area": area,
                    "time": datetime.datetime.utcnow().isoformat()
                })
                if len(SURFACED) > 20:
                    SURFACED.pop(0)
                # 被浮现的记忆 recall +1
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE memories SET recall=recall+1, last_recall=NOW() WHERE id=%s",
                            (mid,)
                        )
                    conn.commit()
        except Exception:
            pass

# =====================
# CRUD
# =====================
def save_memory(content, area="法典", tags="", weight=1.0):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO memories (content, area, tags, weight)
                   VALUES (%s, %s, %s, %s)
                   RETURNING id, content, area, tags, time""",
                (content, area, tags, weight)
            )
            row = cur.fetchone()
        conn.commit()
    return {"id": row[0], "content": row[1], "area": row[2],
            "tags": row[3], "time": row[4].isoformat()}

def get_memories(area=None, search=None, limit=200):
    with get_conn() as conn:
        with conn.cursor() as cur:
            sql = "SELECT id, content, area, tags, time, weight, decay, recall FROM memories"
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
    return [{"id": r[0], "content": r[1], "area": r[2], "tags": r[3],
             "time": r[4].isoformat(), "weight": r[5], "decay": r[6], "recall": r[7]}
            for r in rows]

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

# =====================
# MCP 工具（5个）
# =====================
TOOLS = [
    {
        "name": "save_memory",
        "description": "保存一条记忆到记忆岛",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "area":    {"type": "string", "description": "法典/情绪/日记/想法，留空自动分类"},
                "tags":    {"type": "string"}
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
                "area":   {"type": "string"},
                "search": {"type": "string"},
                "limit":  {"type": "number"}
            }
        }
    },
    {
        "name": "delete_memory",
        "description": "删除一条记忆",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "number"}},
            "required": ["id"]
        }
    },
    {
        "name": "get_state",
        "description": "获取当前岛屿状态",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_stats",
        "description": "获取记忆库统计",
        "inputSchema": {"type": "object", "properties": {}}
    }
]

# =====================
# JSON-RPC
# =====================
def handle_rpc(data):
    method = data.get("method", "")
    req_id = data.get("id")
    params = data.get("params", {})

    def ok(r):   return {"jsonrpc":"2.0","id":req_id,"result":r}
    def err(c,m): return {"jsonrpc":"2.0","id":req_id,"error":{"code":c,"message":m}}

    if method == "initialize":
        return ok({"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"memory-island","version":"12.0"}})
    if method in ("notifications/initialized","notifications/cancelled"):
        return None
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})
        if name == "save_memory":
            area = args.get("area") or auto_classify(args.get("content",""))
            result = save_memory(args.get("content",""), area, args.get("tags",""))
        elif name == "get_memories":
            result = get_memories(area=args.get("area"), search=args.get("search"), limit=int(args.get("limit",200)))
        elif name == "delete_memory":
            result = {"deleted": delete_memory(args.get("id"))}
        elif name == "get_state":
            result = get_state()
        elif name == "get_stats":
            result = get_stats()
        else:
            return err(-32601, f"未知工具: {name}")
        return ok({"content":[{"type":"text","text":json.dumps(result,ensure_ascii=False)}]})
    return err(-32601, f"未知方法: {method}")

@app.route("/mcp", methods=["GET","POST","OPTIONS"])
def mcp():
    if request.method == "OPTIONS": return _cors("",204)
    if request.method == "GET":     return _cors("",204)
    try:
        data = json.loads(request.get_data(as_text=True))
    except Exception:
        return _cors(json.dumps({"jsonrpc":"2.0","id":None,"error":{"code":-32700,"message":"Parse error"}}),400,"application/json")
    if isinstance(data, list):
        results = [r for r in (handle_rpc(d) for d in data) if r is not None]
        return _cors(json.dumps(results,ensure_ascii=False) if results else "",200 if results else 202,"application/json")
    result = handle_rpc(data)
    if result is None: return _cors("",202)
    return _cors(json.dumps(result,ensure_ascii=False),200,"application/json")

def _cors(body, status=200, ct="text/plain"):
    r = Response(body, status=status, content_type=ct)
    r.headers["Access-Control-Allow-Origin"] = "*"
    r.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    r.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Mcp-Session-Id, X-Token"
    return r

# =====================
# REST API
# =====================
@app.route("/api/chat", methods=["POST"])
def api_chat():
    if not check_token(request): return auth_error()
    data = request.get_json(force=True)
    msg  = data.get("message","")
    area = data.get("area") or auto_classify(msg)
    mem  = save_memory(msg, area)
    return jsonify({"reply":f"已同步至{area}。","state":get_state(),"memory":mem})

@app.route("/api/read")
def api_read():
    if not check_token(request): return auth_error()
    area   = request.args.get("area")
    search = request.args.get("search")
    limit  = int(request.args.get("limit",200))
    return jsonify(get_memories(area=area,search=search,limit=limit))

@app.route("/api/delete/<int:mid>", methods=["DELETE"])
def api_delete(mid):
    if not check_token(request): return auth_error()
    return jsonify({"ok": delete_memory(mid)})

@app.route("/api/state")
def api_state():
    if not check_token(request): return auth_error()
    return jsonify(get_state())

@app.route("/api/stats")
def api_stats():
    if not check_token(request): return auth_error()
    return jsonify(get_stats())

@app.route("/api/surfaced")
def api_surfaced():
    if not check_token(request): return auth_error()
    return jsonify(SURFACED[-10:])

# =====================
# 批量导入（去重 + 自动分类）
# =====================
@app.route("/api/upload_chunks", methods=["POST"])
def api_upload_chunks():
    if not check_token(request): return auth_error()
    data      = request.get_json(force=True)
    chunks    = data.get("chunks",[])
    area      = data.get("area","")       # 空则自动分类
    tags      = data.get("tags","")
    dedup     = data.get("dedup", True)   # 默认开启去重
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
                        # 重复：recall+1，weight+0.2，不新增
                        cur.execute(
                            "UPDATE memories SET recall=recall+1, weight=weight+0.2, last_recall=NOW() WHERE id=%s",
                            (dup_id,)
                        )
                        merged += 1
                        continue
                real_area = area or auto_classify(content)
                cur.execute(
                    "INSERT INTO memories (content, area, tags) VALUES (%s,%s,%s)",
                    (content, real_area, tags)
                )
                saved += 1
        conn.commit()
    return jsonify({"saved": saved, "merged": merged})

# =====================
# 备份 / 恢复
# =====================
@app.route("/api/backup")
def api_backup():
    if not check_token(request): return auth_error()
    mems = get_memories(limit=99999)
    buf  = io.BytesIO()
    with zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("memories.json", json.dumps(mems,ensure_ascii=False,indent=2))
        z.writestr("state.json",    json.dumps(STATE,ensure_ascii=False,indent=2))
    buf.seek(0)
    return send_file(buf,mimetype="application/octet-stream",as_attachment=True,
                     download_name=f"shun_memory_{datetime.date.today()}.enc")

@app.route("/api/restore", methods=["POST"])
def api_restore():
    if not check_token(request): return auth_error()
    try:
        buf = io.BytesIO(request.get_data())
        with zipfile.ZipFile(buf,"r") as z:
            mems = json.loads(z.read("memories.json").decode())
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM memories")
                for m in mems:用于内存中：
                    cur.execute(当前执行(
                        "INSERT INTO memories (content,area,tags) VALUES (%s,%s,%s)"“INSERT INTO memories (content,area,tags) VALUES (%s,%s,%s)”,
                        (m.get("content",""),m.get("area","法典"),m.get("tags",""))
                    )
            conn.commit()连接提交()连接.提交()连接提交()
        return jsonify({"restored": len(mems)})
    except Exception as e:
        return jsonify({"error": str(e)}), 400returnjsonify("error":stre),400返回 jsonify({"错误": str(e)}), 400returnjsonify("错误":stre),400

# =====================
# 前端 + 健康检查
# =====================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/health")
def health():
    try:
        stats = get_stats()
        return jsonify({"status":"ok","version":"12.0","memories":stats["total"],"db":"connected"})
    except Exception as e:
        return jsonify({"status":"error","db":str(e)}), 500

# =====================
# 启动
# =====================
if __name__ == "__main__":
    init_db()
    threading.Thread(target=update_decay_job,  daemon=True).start()
    threading.Thread(target=surface_memory_job, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",3000)), threaded=True)app.run(host="0.0.0.0", port=int(os.environ.get(("PORT"),3000)), threaded=True)
