import os
import uuid
import json
from flask import Flask, render_template, request, send_from_directory, jsonify
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_very_secret_key_that_should_be_changed'
UPLOAD_FOLDER = 'uploads'
MAPPING_FILE = 'file_mapping.json'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
socketio = SocketIO(app)

# --- Helper functions for our JSON mapping ---
def load_mapping():
    if not os.path.exists(MAPPING_FILE):
        return {}
    with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
        # Handle empty file case
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_mapping(data):
    with open(MAPPING_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """处理文件上传 (已修复 UnboundLocalError)"""
    # 【关键修复】第一步：检查 'file' key 是否存在
    if 'file' not in request.files:
        return jsonify(success=False, error='No file part in the request'), 400
    
    # 【关键修复】第二步：安全地获取 file 对象
    file = request.files['file']

    # 【关键修复】第三步：现在才检查 filename
    if file.filename == '':
        return jsonify(success=False, error='No file selected'), 400
    
    original_filename = file.filename
    _, extension = os.path.splitext(original_filename)
    unique_filename = f"{uuid.uuid4().hex}{extension}"
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
    
    file.save(save_path)
    
    mapping = load_mapping()
    mapping[unique_filename] = original_filename
    save_mapping(mapping)
    
    sid = request.headers.get('X-SocketIO-SID')
    socketio.emit('file_uploaded', {
        'original_filename': original_filename,
        'saved_filename': unique_filename,
        'sid': sid
    })
    return jsonify(success=True, filename=original_filename)

@app.route('/uploads/<path:filename>')
def download_file(filename):
    mapping = load_mapping()
    original_filename = mapping.get(filename, filename)
    
    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        filename,
        as_attachment=True,
        download_name=original_filename
    )

@app.route('/list_files', methods=['GET'])
def list_files():
    mapping = load_mapping()
    file_list = [{"saved": saved, "original": original} for saved, original in mapping.items()]
    return jsonify(files=file_list, success=True)

# --- Socket.IO Handlers ---
@socketio.on('connect')
def handle_connect():
    emit('session_id', {'sid': request.sid})

@socketio.on('message')
def handle_message(message):
    emit('message_response', {'text': message, 'sid': request.sid}, broadcast=True)

if __name__ == '__main__':
    print("服务器已启动。")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)