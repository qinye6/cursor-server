from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import os
from datetime import datetime, timedelta
import logging
import socket

# 禁用 Flask 默认的日志处理
app = Flask(__name__)
app.logger.disabled = True
log = logging.getLogger('werkzeug')
log.disabled = True

# 自定义日志格式
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

app.secret_key = os.urandom(24)  # 用于session加密
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# 这个变量将在main.py中被设置
config_manager = None

class User(UserMixin):
    def __init__(self, username, role):
        self.id = username
        self.role = role

@login_manager.user_loader
def load_user(username):
    user_info = config_manager.get_user(username)
    if user_info:
        return User(username, user_info['role'])
    return None

def get_user_stats(connections, username):
    """计算��户的总流量和最后连接时间"""
    total_sent = 0
    total_received = 0
    last_connect_time = None
    
    for conn in connections.values():
        if conn['username'] == username:
            total_sent += conn['bytes_sent']
            total_received += conn['bytes_received']
            if last_connect_time is None or conn['connect_time'] > last_connect_time:
                last_connect_time = conn['connect_time']
    
    return {
        'total_sent': total_sent,
        'total_received': total_received,
        'last_connect_time': last_connect_time or ''
    }

@app.route('/')
@login_required
def index():
    if current_user.role == 'admin':
        # 管理员看到原来的界面
        return admin_index()
    else:
        # 普通用户看到用户主页
        return user_home()

def admin_index():
    # 原来的管理员首页代码
    try:
        connection_stats = {'connections': {}, 'total_connections': 0, 'user_connections': {}, 'max_total': 0, 'max_per_user': 0}
        if hasattr(config_manager, 'proxy_server'):
            connection_stats = config_manager.proxy_server.get_active_connections()
        
        return render_template('index.html', 
                             users=config_manager.users.get('users', {}),
                             server_config=config_manager.config['server'],
                             connection_stats=connection_stats,
                             get_user_stats=get_user_stats)
    except Exception as e:
        app.logger.error('Error in index route: %s', e)
        return render_template('error.html', error=str(e)), 500

def user_home():
    # 获取用户信息
    user_info = config_manager.get_user(current_user.id)
    
    # 获取服务器信息
    server_info = {
        'host': config_manager.config['server'].get('proxy_host', config_manager.config['server']['local_host']),
        'port': config_manager.config['server']['proxy_port']
    }
    
    # 获取用户统计信息
    user_stats = {'connections': 0, 'upload_mb': 0, 'download_mb': 0, 'last_active': '-'}
    if hasattr(config_manager, 'proxy_server'):
        connection_stats = config_manager.proxy_server.get_active_connections()
        if current_user.id in connection_stats['user_connections']:
            stats = get_user_stats(connection_stats['connections'], current_user.id)
            user_stats.update({
                'connections': connection_stats['user_connections'][current_user.id],
                'upload_mb': stats['total_sent'] / 1024 / 1024,
                'download_mb': stats['total_received'] / 1024 / 1024,
                'last_active': stats['last_connect_time']
            })
    
    return render_template('user_home.html',
                         user_info=user_info,
                         server_info=server_info,
                         user_stats=user_stats)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if config_manager.verify_user(username, password):
            user_info = config_manager.get_user(username)
            user = User(username, user_info['role'])
            login_user(user)
            return redirect(url_for('index'))
        flash('用户名或密码错误')
    return render_template('login.html', year=datetime.now().year)

@app.route('/users')
@login_required
def users():
    if current_user.role != 'admin':
        flash('需要管理员权限')
        return redirect(url_for('index'))
    
    # 添加当前时间供模板使用
    now = datetime.now().strftime('%Y-%m-%d')
    
    return render_template('users.html', 
                         users=config_manager.users.get('users', {}),
                         now=now)  # 传递当前时间到模板

@app.route('/api/users', methods=['POST'])
@login_required
def add_user():
    if current_user.role != 'admin':
        return jsonify({'error': '需要管理��权限'}), 403
    data = request.json
    config_manager.add_user(
        data['username'],
        data['password'],
        data.get('role', 'user')
    )
    return jsonify({'status': 'success'})

@app.route('/api/users/<username>', methods=['DELETE'])
@login_required
def delete_user(username):
    if current_user.role != 'admin':
        return jsonify({'error': '需要管理员权限'}), 403
    config_manager.remove_user(username)
    return jsonify({'status': 'success'})

@app.route('/api/users/<username>/toggle', methods=['POST'])
@login_required
def toggle_user(username):
    if current_user.role != 'admin':
        return jsonify({'error': '需要管理员权限'}), 403
    user = config_manager.get_user(username)
    if user:
        user['enabled'] = not user['enabled']
        config_manager.save_users()
        return jsonify({'status': 'success'})
    return jsonify({'error': '用户不存在'}), 404

@app.route('/api/users/<username>/extend', methods=['POST'])
@login_required
def extend_user(username):
    if current_user.role != 'admin':
        return jsonify({'error': '需要管理员权限'}), 403
        
    data = request.json
    days = data.get('days', 30)
    
    user = config_manager.get_user(username)
    if user:
        # 计算新的到期时间
        if user['expires_at']:
            try:
                current_expiry = datetime.strptime(user['expires_at'], '%Y-%m-%d')
                if current_expiry < datetime.now():
                    current_expiry = datetime.now()
            except ValueError:
                current_expiry = datetime.now()
        else:
            current_expiry = datetime.now()
            
        user['expires_at'] = (current_expiry + timedelta(days=days)).strftime('%Y-%m-%d')
        config_manager.save_users()
        return jsonify({'status': 'success'})
        
    return jsonify({'error': '用户不存在'}), 404

@app.route('/api/users/<username>/expiry', methods=['POST'])
@login_required
def set_user_expiry(username):
    if current_user.role != 'admin':
        return jsonify({'error': '需要管理员权限'}), 403
        
    data = request.json
    expires_at = data.get('expires_at')
    
    user = config_manager.get_user(username)
    if user:
        user['expires_at'] = expires_at
        config_manager.save_users()
        return jsonify({'status': 'success'})
        
    return jsonify({'error': '用户不存在'}), 404

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

def start_admin(config, port=5001):
    global config_manager
    config_manager = config
    
    def is_port_in_use(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('0.0.0.0', port))
                return False
            except OSError:
                return True
    
    # 检查端口是否被占用
    if is_port_in_use(port):
        print("警告: 管理界面端口 {} 已被占用，尝试使用其他端口".format(port))
        # 尝试其他端口
        for p in range(5001, 5010):
            if not is_port_in_use(p):
                port = p
                break
    
    print(f"管理界面将使用端口 {port}")

    app.run(host='0.0.0.0', port=port) 

@app.errorhandler(500)
def internal_error(error):
    app.logger.error('Server Error: %s', error)
    return render_template('error.html', error=error), 500

@app.errorhandler(Exception)
def handle_exception(e):
    app.logger.error('Unhandled Exception: %s', e)
    return render_template('error.html', error=str(e)), 500 

@app.route('/api/stats')
@login_required
def get_stats():
    stats = {
        'total_connections': 0,
        'max_total': 0,
        'user_connections': {},
        'upload_speed': 0,
        'download_speed': 0
    }
    
    if hasattr(config_manager, 'proxy_server'):
        connection_stats = config_manager.proxy_server.get_active_connections()
        stats.update({
            'total_connections': connection_stats['total_connections'],
            'max_total': connection_stats['max_total'],
            'user_connections': connection_stats['user_connections'],
            'upload_speed': config_manager.proxy_server.get_current_speed()['upload'],
            'download_speed': config_manager.proxy_server.get_current_speed()['download']
        })
    
    return jsonify(stats)

@app.route('/api/users')
@login_required
def get_users():
    users_stats = {}
    if hasattr(config_manager, 'proxy_server'):
        connection_stats = config_manager.proxy_server.get_active_connections()
        for username, count in connection_stats['user_connections'].items():
            user_stats = get_user_stats(connection_stats['connections'], username)
            users_stats[username] = {
                'last_active': user_stats['last_connect_time'],
                'connections': count,
                'upload_mb': user_stats['total_sent'] / 1024 / 1024,
                'download_mb': user_stats['total_received'] / 1024 / 1024
            }
    
    return jsonify(users_stats) 

@app.route('/api/users/<username>/password', methods=['POST'])
@login_required
def change_password(username):
    if current_user.role != 'admin':
        return jsonify({'error': '需要管理员权限'}), 403
        
    data = request.json
    if not data or 'password' not in data:
        return jsonify({'error': '缺少密码参数'}), 400
        
    user = config_manager.get_user(username)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
        
    try:
        user['password'] = data['password']
        config_manager.save_users()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500 

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('两次输入的密码不一致')
            return redirect(url_for('register'))
            
        if config_manager.get_user(username):
            flash('用户名已存在')
            return redirect(url_for('register'))
            
        # 创建新用户
        config_manager.add_user(
            username=username,
            password=password,
            role='user',  # 默认为普通用户
            expires_days=3   # 默认3天有效期
        )
        
        flash('注册成功，请登录')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/download/<path:filename>')
@login_required
def download_file(filename):
    return send_from_directory('/opt/server', filename) 

@app.route('/api/user/password', methods=['POST'])
@login_required
def change_user_password():
    data = request.json
    if not data or 'old_password' not in data or 'new_password' not in data:
        return jsonify({'error': '缺少必要参数'}), 400
        
    user = config_manager.get_user(current_user.id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
        
    # 验证旧密码
    if user['password'] != data['old_password']:
        return jsonify({'error': '当前密码错误'}), 403
        
    try:
        # 更新密码
        user['password'] = data['new_password']
        config_manager.save_users()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500 