from flask import Flask, request, jsonify
import json, os, datetime

app = Flask(__name__)
DATA_FILE = 'database.json'

# 手动添加跨域头，这是“搭桥”最需要的
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.route('/api/read', methods=['GET', 'OPTIONS'])
def read_data():
    if request.method == 'OPTIONS': return "OK", 200
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    return jsonify([])

@app.route('/api/sync', methods=['POST', 'OPTIONS'])
def sync_data():
    if request.method == 'OPTIONS': return "OK", 200
    data = request.json
    logs = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        except: logs = []
    
    new_log = {
        "content": data.get("content") or data.get("text") or "",
        "area": data.get("area", "默认"),
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    logs.append(new_log)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(logs, f, ensure_ascii=False, indent=4)
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
