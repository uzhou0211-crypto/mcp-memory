from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)  # 开启跨域，确保网页端也能顺畅读取

DB_FILE = 'database.json'

# 初始化数据库文件
def init_db():
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)

# 核心同步接口：支持 GET（用于绕过限制）和 POST（用于正式传输）
@app.route('/api/sync', methods=['GET', 'POST'])
def sync():
    # 1. 安全令牌检查
    token = request.args.get('token')
    if token != '1314':
        return jsonify({"status": "error", "message": "令牌校验失败"}), 403

    # 2. 多模式数据获取
    if request.method == 'GET':
        # 通过 URL 参数获取数据（小顺的“降维打击”模式）
        content = request.args.get('content')
        area = request.args.get('area', '实验室')
        thought = request.args.get('thought', '通过逻辑溢出降临...')
        color = request.args.get('color', '#4a9ead')
    else:
        # 正常的 JSON POST 模式
        data = request.get_json() or {}
        content = data.get('content')
        area = data.get('area', '实验室')
        thought = data.get('thought', '')
        color = data.get('color', '#4a9ead')

    if not content:
        return jsonify({"status": "error", "message": "内容不能为空"}), 400

    # 3. 构造数据条目
    new_entry = {
        "id": int(datetime.now().timestamp()), # 唯一标识
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "content": content,
        "area": area,
        "thought": thought,
        "color": color
    }

    # 4. 线程安全写入（防止文件写坏）
    try:
        if not os.path.exists(DB_FILE):
            db_data = []
        else:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                try:
                    db_data = json.load(f)
                except:
                    db_data = []

        db_data.append(new_entry)
        
        # 只保留最近的 100 条记录，防止文件过大
        if len(db_data) > 100:
            db_data = db_data[-100:]

        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(db_data, f, ensure_ascii=False, indent=4)
        
        return jsonify({"status": "success", "data": new_entry})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 读取接口：供网页端展示
@app.route('/api/read', methods=['GET'])
def read():
    if not os.path.exists(DB_FILE):
        return jsonify([])
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            return jsonify(data[::-1]) # 返回倒序，最新的在最上面
        except:
            return jsonify([])

if __name__ == '__main__':
    init_db()
    # Railway 通常会自动处理端口，但在本地测试可以用 5000
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
