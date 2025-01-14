import yaml
import os
from datetime import datetime, timedelta

class ConfigManager:
    def __init__(self, config_dir='config'):
        self.config_dir = config_dir
        self.config = self._load_yaml('config.yaml')
        self.users = self._load_yaml('users.yaml')
        
    def _load_yaml(self, filename):
        path = os.path.join(self.config_dir, filename)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                print(f"成功加载配置文件 {path}:")  # 添加调试信息
                print(data)
                return data
        except FileNotFoundError:
            print(f"警告: 未找到配置文件 {path}, 将创建默认配置")
            # 如果是 users.yaml，创建默认用户配置
            if filename == 'users.yaml':
                default_users = {
                    'users': {
                        'admin': {
                            'password': 'admin123',
                            'role': 'admin',
                            'enabled': True,
                            'created_at': datetime.now().strftime('%Y-%m-%d'),
                            'expires_at': None
                        }
                    }
                }
                # 保存默认配置
                os.makedirs(self.config_dir, exist_ok=True)
                with open(path, 'w', encoding='utf-8') as f:
                    yaml.safe_dump(default_users, f, allow_unicode=True)
                return default_users
            return {}
            
    def save_users(self):
        """保存用户配置"""
        try:
            with open('config/users.yaml', 'w', encoding='utf-8') as f:
                yaml.dump(self.users, f, allow_unicode=True)
                # 确保文件写入磁盘
                f.flush()
                os.fsync(f.fileno())
            return True
        except Exception as e:
            print(f"保存用户配置失败: {e}")
            return False
            
    def add_user(self, username, password, role='user', expires_days=30):
        """添加新用户"""
        if 'users' not in self.users:
            self.users['users'] = {}
            
        created_at = datetime.now().strftime('%Y-%m-%d')
        expires_at = (datetime.now() + timedelta(days=expires_days)).strftime('%Y-%m-%d') if expires_days else None
            
        self.users['users'][username] = {
            'password': password,
            'role': role,
            'enabled': True,
            'created_at': created_at,
            'expires_at': expires_at
        }
        self.save_users()
        
    def remove_user(self, username):
        """删除用户"""
        if username in self.users.get('users', {}):
            del self.users['users'][username]
            self.save_users()
            
    def get_user(self, username):
        """获取用户信息"""
        return self.users.get('users', {}).get(username)
        
    def verify_user(self, username, password):
        """验证用户凭据"""
        user = self.get_user(username)
        if not user or not user['enabled']:
            return False
            
        # 检查是否过期
        if user['expires_at']:
            try:
                expires_at = datetime.strptime(user['expires_at'], '%Y-%m-%d')
                if datetime.now() > expires_at:
                    print(f"用户 {username} 已过期")
                    return False
            except ValueError:
                pass
                
        return user['password'] == password
        
    @property
    def proxy_port(self):
        return self.config.get('server', {}).get('proxy_port', 6880)
        
    @property
    def local_port(self):
        return self.config.get('server', {}).get('local_port', 18030)
        
    @property
    def buffer_size(self):
        return self.config.get('server', {}).get('buffer_size', 32768)
        
    @property
    def connection_timeout(self):
        return self.config.get('server', {}).get('connection_timeout', 120)
        
    @property
    def local_host(self):
        """获取远程服务器地址"""
        return self.config.get('server', {}).get('local_host', '129.226.72.101') 