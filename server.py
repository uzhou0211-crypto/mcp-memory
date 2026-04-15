from flask import Flask, request, jsonify
import json, os, datetime

app = Flask(__name__)
DATA_FILE = 'database.json'

# 1. 确保数据库文件一定存在，且格式正确
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump([], f)

@app.route('/')
def home():
    return "SERVER IS LIVE"

# 2. 核心：还原你最原始的读取接口
@app.route('/api/read', methods=['GET'])
def read_data():
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            content = json.load(f)
            return jsonify(content)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 3. 核心：还原你最原始的同步接口（兼容所有字段）
@app.route('/api/sync', methods=['POST'])
def sync_data():
    try:
        data = request.json
        with open(DATA_FILE, 'r+', encoding='utf-8') as f:
            logs = json.load(f)
            
            # 这里我写得极其暴力，管你原来代码叫什么，全都接住
            new_log = {
                "content": data.get("content") or data.get("text") or data.get("data") or "",
                "area": data.get("area", "默认"),
                "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            logs.append(new_log)
            f.seek(0)
            json.dump(logs, f, ensure_ascii=False, indent=4)
            f.truncate()
        return "OK", 200
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
