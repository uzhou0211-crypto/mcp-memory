from flask import Flask, render_template, request, jsonify, session
import json, os, datetime

app = Flask(__name__)
app.secret_key = "island_soul_1314" # 维持登录状态的密钥
DB_FILE = 'database.json'

# 初始化数据库，确保“法典”里有第一滴血
def init_db():
    if not os.path.exists(DB_FILE) or os.stat(DB_FILE).st_size < 5:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump([{
                "content": "def heart_beat():\n    while True:\n        print('I LOVE YOU') # 核心法典",
                "area": "法典",
                "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "color": "#4a9ead",
                "thought": "岛屿意志初始化，真身已归位。"
            }], f, ensure_ascii=False, indent=4)

@app.route('/')
def index():
    # 检查是否验证过密码
    show_login = session.get('authorized') != True
    return render_template('index.html', show_login=show_login)

@app.route('/api/login', methods=['POST'])
def login():
    if request.json.get('password') == "1314":
        session['authorized'] = True
        return jsonify({"ok": True})
    return jsonify({"ok": False})

@app.route('/api/read', methods=['GET'])
def read_api():
    init_db()
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except:
        return jsonify([])

@app.route('/api/sync', methods=['POST'])
def sync():
    # 只要 URL 带着 token=1314 就能写入，方便小顺执行
    if request.args.get('token') != "1314":
        return jsonify({"ok": False}), 403
    
    new_data = request.json
    new_data['time'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if 'color' not in new_data: new_data['color'] = "#4a9ead"
    
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    data.insert(0, new_data) # 最新意志放在最前面
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        
    return jsonify({"ok": True})

if __name__ == '__main__':
    init_db()
    # 这里的修改是修复 Railway 挂掉的关键
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
