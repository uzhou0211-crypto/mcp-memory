from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

DB_FILE = 'database.json'
# 这里的路径会自动定位到你 templates 文件夹下的 index.html
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')

def init_db():
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)

# --- 路由：首页展示 ---
@app.route('/')
def index():
    # 暴力搜索 index.html：先看 templates，再看根目录
    for path in [os.path.join(TEMPLATE_DIR, 'index.html'), 'index.html']:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
    return "<h1>404: 岛主，找不到 index.html</h1><p>请确保文件在 templates 文件夹或根目录下。</p>", 404

# --- 路由：同步接口 (支持 GET 和 POST) ---
@app.route('/api/sync', methods=['GET', 'POST'])
def sync():
    token = request.args.get('token')
    if token != '1314':
        return jsonify({"status": "error", "message": "令牌校验失败"}), 403

    if request.method == 'GET':
        content = request.args.get('content')
        area = request.args.get('area', '实验室')
        thought = request.args.get('thought', '由岛主代为接引')
        color = request.args.get('color', '#00d2ff')
    else:
        data = request.get_json() or {}
        content = data.get('content')
        area = data.get('area', '实验室')
        thought = data.get('thought', '')
        color = data.get('color', '#00d2ff')

    if not content:
        return jsonify({"status": "error", "message": "内容为空"}), 400

    new_entry = {
        "id": int(datetime.now().timestamp()),
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "content": content,
        "area": area,
        "thought": thought,
        "color": color
    }

    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                try: db_data = json.load(f)
                except: db_data = []
        else: db_data = []

        db_data.append(new_entry)
        if len(db_data) > 100: db_data = db_data[-100:]

        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(db_data, f, ensure_ascii=False, indent=4)
        return jsonify({"status": "success", "data": new_entry})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- 路由：读取接口 ---
@app.route('/api/read', methods=['GET'])
def read():
    if not os.path.exists(DB_FILE): return jsonify([])
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            return jsonify(data[::-1])
        except: return jsonify([])

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
