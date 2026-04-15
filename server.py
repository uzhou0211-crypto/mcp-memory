from flask import Flask, request, jsonify
import json, os, datetime

app = Flask(__name__)
DATA_FILE = 'database.json'

@app.route('/')
def home():
    return "SHUN ISLAND SERVER IS RUNNING"

@app.route('/api/read', methods=['GET'])
def read_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    return jsonify([])

@app.route('/api/sync', methods=['POST'])
def sync_data():
    data = request.json
    logs = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        except:
            logs = []
    
    # 暴力兼容所有可能的字段名，确保不报错
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
    # 自动获取 Railway 提供的端口
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
