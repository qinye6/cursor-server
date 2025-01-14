# -*- coding: utf-8 -*-
import sys
import os
import atexit
from core.config import ConfigManager
from core.proxy import ProxyServer
from web_admin.admin import start_admin
import threading
import socket

def write_pid():
    """写入PID文件"""
    pid = str(os.getpid())
    with open('/var/run/proxy-server.pid', 'w') as f:
        f.write(pid)

def cleanup():
    """清理PID文件"""
    try:
        os.remove('/var/run/proxy-server.pid')
    except:
        pass

def check_config(config):
    """检查配置是否正确"""
    if not config.users or 'users' not in config.users:
        print("错误: 用户配置为空或格式不正确")
        return False
        
    users = config.users.get('users', {})
    if not users:
        print("错误: 没有配置任何用户")
        return False
        
    print("当前配置的用户:")
    for username, user in users.items():
        print("- {}:".format(username))
        print("  角色: {}".format(user.get('role', 'unknown')))
        print("  状态: {}".format('启用' if user.get('enabled', False) else '禁用'))
        print("  到期时间: {}".format(user.get('expires_at', '永不过期')))
    
    return True

def main():
    # 写入PID文件
    write_pid()
    # 注册退出时的清理函数
    atexit.register(cleanup)
    
    # 初始化配置管理器
    config = ConfigManager()
    
    # 检查配置
    if not check_config(config):
        print("配置检查失败，程序退出")
        sys.exit(1)
    
    # 创建必要的目录
    os.makedirs('logs', exist_ok=True)
    os.makedirs('config', exist_ok=True)
    
    # 检查端口是否被占用
    def check_port(port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('0.0.0.0', port))
            sock.close()
            return True
        except OSError:
            return False

    if not check_port(config.proxy_port):
        print("错误: 代理端口 {} 已被占用".format(config.proxy_port))
        sys.exit(1)

    try:
        # 创建代理服务器
        server = ProxyServer(config)
        # 保存代理服务器实例到配置管理器
        config.proxy_server = server
        
        # 启动Web管理界面
        admin_thread = threading.Thread(
            target=start_admin,
            args=(config,),
            kwargs={'port': 5000},
            daemon=True
        )
        admin_thread.start()
        
        # 启动代理服务器
        server.start()
    except KeyboardInterrupt:
        print("\n正在关闭服务器...")
        sys.exit(0)
    except Exception as e:
        print("错误: {}".format(e))
        sys.exit(1)

if __name__ == "__main__":
    main() 