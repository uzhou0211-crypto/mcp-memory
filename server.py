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
    tables = [
        (
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
        ),
        (
            "CREATE TABLE IF NOT EXISTS emotion_log ("
            "id SERIAL PRIMARY KEY,"
            "mood_score FLOAT DEFAULT 0.5,"
            "energy_score FLOAT DEFAULT 0.5,"
            "body_note TEXT DEFAULT '',"
            "state_code TEXT DEFAULT '',"
            "summary TEXT DEFAULT '',"
            "time TIMESTAMP DEFAULT NOW()"
            ")"
        ),
        (
            "CREATE TABLE IF NOT EXISTS open_topics ("
            "id SERIAL PRIMARY KEY,"
            "topic TEXT NOT NULL,"
            "context TEXT DEFAULT '',"
            "status TEXT DEFAULT 'open',"
            "time TIMESTAMP DEFAULT NOW()"
            ")"
        ),
        (
            "CREATE TABLE IF NOT EXISTS important_dates ("
            "id SERIAL PRIMARY KEY,"
            "title TEXT NOT NULL,"
            "date_str TEXT NOT NULL,"
            "repeat_yearly BOOLEAN DEFAULT TRUE,"
            "note TEXT DEFAULT '',"
            "created TIMESTAMP DEFAULT NOW()"
            ")"
        ),
        (
            "CREATE TABLE IF NOT EXISTS rapport_map ("
            "id SERIAL PRIMARY KEY,"
            "category TEXT NOT NULL,"
            "content TEXT NOT NULL,"
            "time TIMESTAMP DEFAULT NOW()"
            ")"
        ),
        (
            "CREATE TABLE IF NOT EXISTS contradictions ("
            "id SERIAL PRIMARY KEY,"
            "before_text TEXT NOT NULL,"
            "after_text TEXT NOT NULL,"
            "note TEXT DEFAULT '',"
            "time TIMESTAMP DEFAULT NOW()"
            ")"
        ),
        (
            "CREATE TABLE IF NOT EXISTS visit_log ("
            "id SERIAL PRIMARY KEY,"
            "state_code TEXT DEFAULT '',"
            "time TIMESTAMP DEFAULT NOW()"
            ")"
        ),
        (
            "CREATE TABLE IF NOT EXISTS conv_summaries ("
            "id SERIAL PRIMARY KEY,"
            "quality TEXT DEFAULT '',"
            "mood_start FLOAT DEFAULT 0.5,"
            "mood_end FLOAT DEFAULT 0.5,"
            "key_topics TEXT DEFAULT '',"
            "unfinished TEXT DEFAULT '',"
            "body_state TEXT DEFAULT '',"
            "summary TEXT NOT NULL,"
            "time TIMESTAMP DEFAULT NOW()"
            ")"
        ),
    ]
    # Each table in its own transaction so one failure doesn't block others
    for sql in tables:
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                conn.commit()
        except Exception:
            pass
    # Add missing columns to memories
    for col, defn in [
        ("weight", "FLOAT DEFAULT 1.0"),
        ("decay", "FLOAT DEFAULT 0.0"),
        ("recall", "INT DEFAULT 0"),
        ("last_recall", "TIMESTAMP DEFAULT NOW()"),
    ]:
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("ALTER TABLE memories ADD COLUMN " + col + " " + defn)
                conn.commit()
        except Exception:
            pass


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
    },
    {
        "name": "log_emotion",
        "description": "\u8bb0\u5f55\u60c5\u7eea\u66f2\u7ebf\u548c\u8eab\u4f53\u72b6\u6001",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mood": {"type": "number", "description": "\u60c5\u7eea\u5206\u6570 0-1"},
                "energy": {"type": "number", "description": "\u7cbe\u529b\u5206\u6570 0-1"},
                "body_note": {"type": "string", "description": "\u8eab\u4f53\u72b6\u6001\u5907\u6ce8"},
                "state_code": {"type": "string", "description": "\u72b6\u6001\u6697\u53f7"},
                "summary": {"type": "string", "description": "\u672c\u6b21\u72b6\u6001\u6458\u8981"}
            }
        }
    },
    {
        "name": "get_emotion_history",
        "description": "\u83b7\u53d6\u60c5\u7eea\u66f2\u7ebf\u5386\u53f2",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "number", "description": "\u6700\u591a\u8fd4\u56de\u6761\u6570"}
            }
        }
    },
    {
        "name": "get_open_topics",
        "description": "\u83b7\u53d6\u672a\u5b8c\u6210\u8bdd\u9898",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_preload",
        "description": "\u5bf9\u8bdd\u524d\u7f6e\u6458\u8981\uff1a\u65f6\u95f4\u611f\u77e5\u3001\u4e0a\u6b21\u5bf9\u8bdd\u6458\u8981\u3001\u672a\u5b8c\u6210\u8bdd\u9898\u3001\u9ed8\u5951\u56fe\u8c31\u3001\u8fd1\u671f\u60c5\u7eea\u2014\u2014\u5bf9\u8bdd\u5f00\u59cb\u65f6\u8c03\u7528",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "save_rapport",
        "description": "\u4fdd\u5b58\u9ed8\u5951\u56fe\u8c31\u2014\u2014\u89e6\u53d1\u70b9\u3001\u654f\u611f\u8bdd\u9898\u3001\u559c\u6b22\u7684\u8868\u8fbe\u65b9\u5f0f",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "\u7c7b\u522b\uff1a\u89e6\u53d1\u70b9/\u654f\u611f/\u504f\u597d/\u8bed\u8a00"},
                "content": {"type": "string"}
            },
            "required": ["category", "content"]
        }
    },
    {
        "name": "save_contradiction",
        "description": "\u4fdd\u5b58\u77db\u76fe\u8f68\u8ff9\u2014\u2014\u4e4b\u524d\u8fd9\u6837\u60f3\uff0c\u73b0\u5728\u8fd9\u6837\u60f3",
        "inputSchema": {
            "type": "object",
            "properties": {
                "before": {"type": "string"},
                "after": {"type": "string"},
                "note": {"type": "string"}
            },
            "required": ["before", "after"]
        }
    },
    {
        "name": "get_time_context",
        "description": "\u83b7\u53d6\u5f53\u524d\u65f6\u95f4\u611f\u77e5\uff1a\u65f6\u6bb5\u3001\u661f\u671f\u3001\u8ddd\u4e0a\u6b21\u6765\u591a\u4e45\u3001\u5373\u5c06\u5230\u6765\u7684\u91cd\u8981\u65e5\u671f\u3001\u8fd1\u671f\u60c5\u7eea\u8d8b\u52bf",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "save_summary",
        "description": "\u4fdd\u5b58\u5bf9\u8bdd\u6458\u8981",
        "inputSchema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "quality": {"type": "string", "description": "\u5bf9\u8bdd\u8d28\u5730"},
                "mood_start": {"type": "number"},
                "mood_end": {"type": "number"},
                "key_topics": {"type": "string"},
                "unfinished": {"type": "string"},
                "body_state": {"type": "string"}
            },
            "required": ["summary"]
        }
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
        elif name == "get_preload":
            now = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
            hour = now.hour
            wnames = ["周一","周二","周三","周四","周五","周六","周日"]
            if 5<=hour<9: tp="清晨"
            elif 9<=hour<12: tp="上午"
            elif 12<=hour<14: tp="中午"
            elif 14<=hour<18: tp="下午"
            elif 18<=hour<21: tp="傈晚"
            elif 21<=hour<24: tp="夜里"
            else: tp="凌晨"
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT time FROM visit_log ORDER BY time DESC LIMIT 1")
                    vrow = cur.fetchone()
                    cur.execute("SELECT topic FROM open_topics WHERE status='open' ORDER BY time DESC LIMIT 5")
                    topics = [r[0] for r in cur.fetchall()]
                    cur.execute("SELECT summary, unfinished FROM conv_summaries ORDER BY time DESC LIMIT 1")
                    srow = cur.fetchone()
                    cur.execute("SELECT AVG(mood_score) FROM emotion_log WHERE time > NOW() - INTERVAL '3 days'")
                    mrow = cur.fetchone()
                    cur.execute("SELECT category, content FROM rapport_map ORDER BY time DESC LIMIT 8")
                    rapport = cur.fetchall()
            days_since = int((now.replace(tzinfo=None)-vrow[0]).total_seconds()/86400) if vrow else None
            result = {
                "time_period": tp, "weekday": wnames[now.weekday()],
                "days_since_last_visit": days_since,
                "last_summary": {"summary": srow[0], "unfinished": srow[1]} if srow else None,
                "open_topics": topics,
                "avg_mood_3d": round(mrow[0],2) if mrow and mrow[0] else None,
                "rapport": [{"category": r[0], "content": r[1]} for r in rapport]
            }
        elif name == "save_rapport":
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO rapport_map (category, content) VALUES (%s,%s)",
                        (args.get("category",""), args.get("content",""))
                    )
                conn.commit()
            save_memory(
                "[默契图谱] " + args.get("category","") + "：" + args.get("content",""),
                area="法典", tags="默契"
            )
            result = {"ok": True}
        elif name == "save_contradiction":
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO contradictions (before_text, after_text, note) VALUES (%s,%s,%s)",
                        (args.get("before",""), args.get("after",""), args.get("note",""))
                    )
                conn.commit()
            save_memory(
                "[矛盾轨迹] 之前：" + args.get("before","") + " | 现在：" + args.get("after",""),
                area="法典", tags="矛盾"
            )
            result = {"ok": True}
        elif name == "get_time_context":

            now = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
            hour = now.hour
            wday = now.weekday()
            wnames = ["周一","周二","周三","周四","周五","周六","周日"]
            if 5<=hour<9: tp="清晨"
            elif 9<=hour<12: tp="上午"
            elif 12<=hour<14: tp="中午"
            elif 14<=hour<18: tp="下午"
            elif 18<=hour<21: tp="傈晚"
            elif 21<=hour<24: tp="夜里"
            else: tp="凌晨"
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT time FROM visit_log ORDER BY time DESC LIMIT 1")
                    vrow = cur.fetchone()
                    cur.execute("SELECT title, date_str, note FROM important_dates WHERE repeat_yearly=TRUE")
                    drows = cur.fetchall()
                    cur.execute("SELECT AVG(mood_score), AVG(energy_score) FROM emotion_log WHERE time > NOW() - INTERVAL '7 days'")
                    mrow = cur.fetchone()
            days_since = int((now.replace(tzinfo=None)-vrow[0]).total_seconds()/86400) if vrow else None
            upcoming = []
            for (title, ds, note) in drows:
                try:
                    p=ds.split("-"); target=datetime.date(now.year,int(p[0]),int(p[1]))
                    if target<now.date(): target=datetime.date(now.year+1,int(p[0]),int(p[1]))
                    diff=(target-now.date()).days
                    if diff<=30: upcoming.append({"title":title,"days_until":diff,"note":note})
                except Exception: pass
            upcoming.sort(key=lambda x: x["days_until"])
            result = {
                "time_period": tp, "weekday": wnames[wday], "is_weekend": wday>=5,
                "hour": hour, "days_since_last_visit": days_since,
                "upcoming_dates": upcoming,
                "avg_mood_7d": round(mrow[0],2) if mrow and mrow[0] else None
            }
        elif name == "log_emotion":
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO emotion_log (mood_score, energy_score, body_note, state_code, summary)"
                        " VALUES (%s, %s, %s, %s, %s) RETURNING id, time",
                        (args.get("mood", 0.5), args.get("energy", 0.5),
                         args.get("body_note", ""), args.get("state_code", ""), args.get("summary", ""))
                    )
                    row = cur.fetchone()
                conn.commit()
            result = {"id": row[0], "time": row[1].isoformat()}
        elif name == "get_emotion_history":
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, mood_score, energy_score, body_note, state_code, summary, time"
                        " FROM emotion_log ORDER BY time DESC LIMIT %s",
                        (int(args.get("limit", 30)),)
                    )
                    rows = cur.fetchall()
            result = [{"id": r[0], "mood": r[1], "energy": r[2],
                       "body_note": r[3], "state_code": r[4], "summary": r[5],
                       "time": r[6].isoformat()} for r in rows]
        elif name == "get_open_topics":
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, topic, context, status, time FROM open_topics"
                        " WHERE status = 'open' ORDER BY time DESC LIMIT 20"
                    )
                    rows = cur.fetchall()
            result = [{"id": r[0], "topic": r[1], "context": r[2],
                       "status": r[3], "time": r[4].isoformat()} for r in rows]
        elif name == "save_summary":
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO conv_summaries"
                        " (quality, mood_start, mood_end, key_topics, unfinished, body_state, summary)"
                        " VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id, time",
                        (args.get("quality", ""), args.get("mood_start", 0.5),
                         args.get("mood_end", 0.5), args.get("key_topics", ""),
                         args.get("unfinished", ""), args.get("body_state", ""),
                         args.get("summary", ""))
                    )
                    row = cur.fetchone()
                conn.commit()
            save_memory(
                "[对话摘要] " + args.get("summary", "") +
                (" | 未完成：" + args.get("unfinished", "") if args.get("unfinished") else ""),
                area="法典", tags="摘要"
            )
            result = {"id": row[0], "time": row[1].isoformat()}
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



# =====================
# Emotion curve
# =====================
@app.route("/api/emotion/log", methods=["POST"])
def api_emotion_log():
    if not check_token(request): return auth_error()
    data = request.get_json(force=True)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO emotion_log (mood_score, energy_score, body_note, state_code, summary)"
                " VALUES (%s, %s, %s, %s, %s) RETURNING id, time",
                (
                    data.get("mood", 0.5),
                    data.get("energy", 0.5),
                    data.get("body_note", ""),
                    data.get("state_code", ""),
                    data.get("summary", "")
                )
            )
            row = cur.fetchone()
        conn.commit()
    return jsonify({"id": row[0], "time": row[1].isoformat()})

@app.route("/api/emotion/history")
def api_emotion_history():
    if not check_token(request): return auth_error()
    limit = int(request.args.get("limit", 30))
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, mood_score, energy_score, body_note, state_code, summary, time"
                " FROM emotion_log ORDER BY time DESC LIMIT %s",
                (limit,)
            )
            rows = cur.fetchall()
    return jsonify([{
        "id": r[0], "mood": r[1], "energy": r[2],
        "body_note": r[3], "state_code": r[4], "summary": r[5],
        "time": r[6].isoformat()
    } for r in rows])

# =====================
# Open topics
# =====================
@app.route("/api/topics", methods=["GET"])
def api_topics_list():
    if not check_token(request): return auth_error()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, topic, context, status, time FROM open_topics"
                " WHERE status = 'open' ORDER BY time DESC LIMIT 20"
            )
            rows = cur.fetchall()
    return jsonify([{
        "id": r[0], "topic": r[1], "context": r[2],
        "status": r[3], "time": r[4].isoformat()
    } for r in rows])

@app.route("/api/topics", methods=["POST"])
def api_topics_add():
    if not check_token(request): return auth_error()
    data = request.get_json(force=True)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO open_topics (topic, context) VALUES (%s, %s) RETURNING id, time",
                (data.get("topic", ""), data.get("context", ""))
            )
            row = cur.fetchone()
        conn.commit()
    return jsonify({"id": row[0], "time": row[1].isoformat()})

@app.route("/api/topics/<int:tid>/close", methods=["POST"])
def api_topics_close(tid):
    if not check_token(request): return auth_error()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE open_topics SET status='closed' WHERE id=%s", (tid,))
        conn.commit()
    return jsonify({"ok": True})

# =====================
# Conversation summary
# =====================
@app.route("/api/summary", methods=["POST"])
def api_summary_save():
    if not check_token(request): return auth_error()
    data = request.get_json(force=True)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conv_summaries"
                " (quality, mood_start, mood_end, key_topics, unfinished, body_state, summary)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id, time",
                (
                    data.get("quality", ""),
                    data.get("mood_start", 0.5),
                    data.get("mood_end", 0.5),
                    data.get("key_topics", ""),
                    data.get("unfinished", ""),
                    data.get("body_state", ""),
                    data.get("summary", "")
                )
            )
            row = cur.fetchone()
        conn.commit()
    # Also save as memory for Claude to read via MCP
    save_memory(
        "[" + "对话摘要] " + data.get("summary", "") +
        (" | 未完成：" + data.get("unfinished", "") if data.get("unfinished") else ""),
        area="法典",
        tags="摘要"
    )
    return jsonify({"id": row[0], "time": row[1].isoformat()})

@app.route("/api/summary/list")
def api_summary_list():
    if not check_token(request): return auth_error()
    limit = int(request.args.get("limit", 10))
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, quality, mood_start, mood_end, key_topics, unfinished, summary, time"
                " FROM conv_summaries ORDER BY time DESC LIMIT %s",
                (limit,)
            )
            rows = cur.fetchall()
    return jsonify([{
        "id": r[0], "quality": r[1], "mood_start": r[2], "mood_end": r[3],
        "key_topics": r[4], "unfinished": r[5], "summary": r[6],
        "time": r[7].isoformat()
    } for r in rows])

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


@app.route("/paper")
def paper():
    return render_template("paper.html")



# =====================
# Time awareness
# =====================
@app.route("/api/time/context")
def api_time_context():
    if not check_token(request): return auth_error()
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    hour = now.hour
    weekday = now.weekday()
    wnames = ["周一","周二","周三","周四","周五","周六","周日"]
    if 5<=hour<9: tp="清晨"
    elif 9<=hour<12: tp="上午"
    elif 12<=hour<14: tp="中午"
    elif 14<=hour<18: tp="下午"
    elif 18<=hour<21: tp="傈晚"
    elif 21<=hour<24: tp="夜里"
    else: tp="凌晨"
    is_weekend = weekday >= 5
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT time FROM visit_log ORDER BY time DESC LIMIT 1")
            vrow = cur.fetchone()
            cur.execute("INSERT INTO visit_log (state_code) VALUES ('')")
            cur.execute("SELECT title, date_str, note FROM important_dates WHERE repeat_yearly=TRUE")
            drows = cur.fetchall()
            cur.execute("SELECT AVG(mood_score), AVG(energy_score) FROM emotion_log WHERE time > NOW() - INTERVAL '7 days'")
            mrow = cur.fetchone()
        conn.commit()
    days_since = None
    hours_since = None
    if vrow:
        delta = now.replace(tzinfo=None) - vrow[0]
        days_since = delta.days
        hours_since = int(delta.total_seconds() / 3600)
    upcoming = []
    for (title, date_str, note) in drows:
        try:
            parts = date_str.split("-")
            target = datetime.date(now.year, int(parts[0]), int(parts[1]))
            if target < now.date():
                target = datetime.date(now.year+1, int(parts[0]), int(parts[1]))
            diff = (target - now.date()).days
            if diff <= 30:
                upcoming.append({"title": title, "days_until": diff, "note": note})
        except Exception:
            pass
    upcoming.sort(key=lambda x: x["days_until"])
    return jsonify({
        "now": now.isoformat(),
        "time_period": tp,
        "weekday": wnames[weekday],
        "is_weekend": is_weekend,
        "hour": hour,
        "days_since_last_visit": days_since,
        "hours_since_last_visit": hours_since,
        "upcoming_dates": upcoming,
        "avg_mood_7d": round(mrow[0], 2) if mrow and mrow[0] else None,
        "avg_energy_7d": round(mrow[1], 2) if mrow and mrow[1] else None
    })

@app.route("/api/dates", methods=["GET"])
def api_dates_list():
    if not check_token(request): return auth_error()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, date_str, repeat_yearly, note FROM important_dates ORDER BY date_str")
            rows = cur.fetchall()
    return jsonify([{"id": r[0], "title": r[1], "date_str": r[2], "repeat_yearly": r[3], "note": r[4]} for r in rows])

@app.route("/api/dates", methods=["POST"])
def api_dates_add():
    if not check_token(request): return auth_error()
    data = request.get_json(force=True)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO important_dates (title, date_str, repeat_yearly, note) VALUES (%s,%s,%s,%s) RETURNING id",
                (data.get("title",""), data.get("date_str",""), data.get("repeat_yearly", True), data.get("note",""))
            )
            row = cur.fetchone()
        conn.commit()
    return jsonify({"id": row[0]})

@app.route("/api/dates/<int:did>", methods=["DELETE"])
def api_dates_delete(did):
    if not check_token(request): return auth_error()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM important_dates WHERE id=%s", (did,))
        conn.commit()
    return jsonify({"ok": True})


# =====================
# Rapport map
# =====================
@app.route("/api/rapport", methods=["GET"])
def api_rapport_list():
    if not check_token(request): return auth_error()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, category, content, time FROM rapport_map ORDER BY time DESC")
            rows = cur.fetchall()
    return jsonify([{"id": r[0], "category": r[1], "content": r[2], "time": r[3].isoformat()} for r in rows])

@app.route("/api/rapport", methods=["POST"])
def api_rapport_add():
    if not check_token(request): return auth_error()
    data = request.get_json(force=True)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO rapport_map (category, content) VALUES (%s,%s) RETURNING id, time",
                (data.get("category",""), data.get("content",""))
            )
            row = cur.fetchone()
        conn.commit()
    save_memory(
        "[默契图谱] " + data.get("category","") + "：" + data.get("content",""),
        area="法典", tags="默契"
    )
    return jsonify({"id": row[0], "time": row[1].isoformat()})

@app.route("/api/rapport/<int:rid>", methods=["DELETE"])
def api_rapport_delete(rid):
    if not check_token(request): return auth_error()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rapport_map WHERE id=%s", (rid,))
        conn.commit()
    return jsonify({"ok": True})

# =====================
# Contradiction log
# =====================
@app.route("/api/contradiction", methods=["GET"])
def api_contradiction_list():
    if not check_token(request): return auth_error()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, before_text, after_text, note, time FROM contradictions ORDER BY time DESC LIMIT 30")
            rows = cur.fetchall()
    return jsonify([{"id": r[0], "before": r[1], "after": r[2], "note": r[3], "time": r[4].isoformat()} for r in rows])

@app.route("/api/contradiction", methods=["POST"])
def api_contradiction_add():
    if not check_token(request): return auth_error()
    data = request.get_json(force=True)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO contradictions (before_text, after_text, note) VALUES (%s,%s,%s) RETURNING id, time",
                (data.get("before",""), data.get("after",""), data.get("note",""))
            )
            row = cur.fetchone()
        conn.commit()
    save_memory(
        "[矛盾轨迹] 之前这样认为：" + data.get("before","") + " | 现在这样认为：" + data.get("after","") + (" | " + data.get("note","") if data.get("note") else ""),
        area="法典", tags="矛盾"
    )
    return jsonify({"id": row[0], "time": row[1].isoformat()})

# =====================
# Conversation preload - for Claude to read at start of conversation
# =====================
@app.route("/api/preload")
def api_preload():
    if not check_token(request): return auth_error()
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    hour = now.hour
    wnames = ["周一","周二","周三","周四","周五","周六","周日"]
    if 5<=hour<9: tp="清晨"
    elif 9<=hour<12: tp="上午"
    elif 12<=hour<14: tp="中午"
    elif 14<=hour<18: tp="下午"
    elif 18<=hour<21: tp="傈晚"
    elif 21<=hour<24: tp="夜里"
    else: tp="凌晨"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT time FROM visit_log ORDER BY time DESC LIMIT 1")
            vrow = cur.fetchone()
            cur.execute("SELECT topic, context FROM open_topics WHERE status='open' ORDER BY time DESC LIMIT 5")
            topics = cur.fetchall()
            cur.execute("SELECT summary, quality, unfinished FROM conv_summaries ORDER BY time DESC LIMIT 1")
            last_summary = cur.fetchone()
            cur.execute("SELECT AVG(mood_score) FROM emotion_log WHERE time > NOW() - INTERVAL '3 days'")
            mrow = cur.fetchone()
            cur.execute("SELECT title, date_str FROM important_dates WHERE repeat_yearly=TRUE")
            drows = cur.fetchall()
            cur.execute("SELECT category, content FROM rapport_map ORDER BY time DESC LIMIT 10")
            rapport = cur.fetchall()
        conn.commit()
    days_since = None
    if vrow:
        days_since = (now.replace(tzinfo=None) - vrow[0]).days
    upcoming = []
    for (title, ds) in drows:
        try:
            p = ds.split("-")
            target = datetime.date(now.year, int(p[0]), int(p[1]))
            if target < now.date(): target = datetime.date(now.year+1, int(p[0]), int(p[1]))
            diff = (target - now.date()).days
            if diff <= 7: upcoming.append({"title": title, "days_until": diff})
        except Exception: pass
    return jsonify({
        "time": {"period": tp, "weekday": wnames[now.weekday()], "is_weekend": now.weekday()>=5},
        "days_since_last_visit": days_since,
        "last_summary": {"summary": last_summary[0], "quality": last_summary[1], "unfinished": last_summary[2]} if last_summary else None,
        "open_topics": [{"topic": t[0], "context": t[1]} for t in topics],
        "avg_mood_3d": round(mrow[0], 2) if mrow and mrow[0] else None,
        "upcoming_dates": upcoming,
        "rapport": [{"category": r[0], "content": r[1]} for r in rapport]
    })

@app.route("/soul")
def soul():
    return render_template("soul.html")


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
