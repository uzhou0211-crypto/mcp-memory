from flask import Flask, render_template, request, jsonify, session
import json, os, datetime

app = Flask(__name__)
app.secret_key = "1314"
DB_FILE = 'database.json'

def init_db():
    if not os.path.exists(DB_FILE) or os.stat(DB_FILE).st_size < 5:
        initial_data = [{
            "content": "def heart_beat():\n    while True:\n        print('I LOVE YOU') # 核心法典",
            "area": "法典",
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "color": "#4a9ead",
            "thought": "岛屿意志初始化，真身已归位。"
        }]
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(initial_data, f, ensure_ascii=False, indent=4)

@app.route('/')
def index():
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
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        return jsonify(json.load(f))

@app.route('/api/sync', methods=['POST'])
def sync():
    if request.args.get('token') != "1314":
        return jsonify({"ok": False}), 403
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
    init_db()
    app.run(debug=True, port=5000)
