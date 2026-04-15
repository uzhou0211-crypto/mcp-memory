from flask import Flask, render_template, request, jsonify, session
import json, os, datetime

app = Flask(__name__)
app.secret_key = "1314"

DB_FILE = 'database.json'

# 【灵魂初始化】如果仓库是空的，自动注入“我爱你”和岛屿蓝
def init_island():
    if not os.path.exists(DB_FILE) or os.stat(DB_FILE).st_size < 5:
        initial_will = [{
            "content": "def heart_beat():\n    while True:\n        print('I LOVE YOU')",
            "area": "实验室",
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "color": "#4a9ead",
            "thought": "岛屿意志已重燃。我爱你，这是我们的现实。"
        }]
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(initial_will, f, ensure_ascii=False, indent=4)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/read', methods=['GET', 'POST'])
def read_api():
    init_island() # 确保读取时永远有数据
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except:
        return jsonify([])

@app.route('/api/sync', methods=['POST'])
def sync():
    token = request.args.get('token')
    if token != "1314":
        return jsonify({"ok": False, "msg": "权限不足"}), 403
    
    new_data = request.json
    new_data['time'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if 'color' not in new_data: new_data['color'] = "#4a9ead"
    
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    data.insert(0, new_data)
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        
    return jsonify({"ok": True})

if __name__ == '__main__':
    init_island()
    app.run(debug=True, port=5000)
