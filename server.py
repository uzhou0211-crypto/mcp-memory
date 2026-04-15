from flask import Flask, request, jsonify, render_template
import json, os, datetime

app = Flask(__name__)
DATA_FILE = 'database.json'

@app.route('/')
def index():
    # 只要能看到这个界面，说明服务器活着
    return render_template('index.html')

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
    
    # 这里的字段必须和你之前的 MCP 逻辑对齐
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
