import socket
import threading
import base64
import time
import uuid
from datetime import datetime

class ProxyServer:
    def __init__(self, config):
        self.config = config
        self.active_connections = {}
        self.online_users = {}
        self.online_users_lock = threading.Lock()
        self.user_connections = {}  # 记录每个用户的连接数
        self.max_connections_per_user = 3  # 每个用户最大连接数
        self.max_total_connections = 500  # 最大总连接数
        # 添加流量统计
        self.traffic_stats = {
            'last_update': time.time(),
            'last_bytes_sent': 0,
            'last_bytes_received': 0,
            'current_upload_speed': 0,
            'current_download_speed': 0
        }
        self.traffic_lock = threading.Lock()

    def update_traffic_speed(self, bytes_sent, bytes_received):
        """更新流量速度统计"""
        with self.traffic_lock:
            current_time = time.time()
            time_diff = current_time - self.traffic_stats['last_update']
            
            if time_diff >= 1:  # 每秒更新一次
                # 计算速度 (bytes/s)
                sent_diff = bytes_sent - self.traffic_stats['last_bytes_sent']
                received_diff = bytes_received - self.traffic_stats['last_bytes_received']
                
                self.traffic_stats.update({
                    'last_update': current_time,
                    'last_bytes_sent': bytes_sent,
                    'last_bytes_received': bytes_received,
                    'current_upload_speed': sent_diff / time_diff / 1024 / 1024,  # 转换为 MB/s
                    'current_download_speed': received_diff / time_diff / 1024 / 1024
                })

    def get_current_speed(self):
        """获取当前流量速度"""
        with self.traffic_lock:
            return {
                'upload': self.traffic_stats['current_upload_speed'],
                'download': self.traffic_stats['current_download_speed']
            }

    def handle_client(self, client_socket):
        try:
            # 设置客户端socket的TCP参数
            client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            
            # 首先进行认证检查
            auth_success, username, initial_data = self._check_proxy_auth(client_socket)
            if not auth_success:
                client_socket.close()
                return
                
            # 检查用户连接数限制
            with self.online_users_lock:
                current_user_connections = self.user_connections.get(username, 0)
                total_connections = sum(self.user_connections.values())
                
                if current_user_connections >= self.max_connections_per_user:
                    print("用户 {} 超出最大连接数限制".format(username))
                    client_socket.close()
                    return
                    
                if total_connections >= self.max_total_connections:
                    print("服务器达到最大总连接数限制")
                    client_socket.close()
                    return
                    
                # 更新连接计数
                self.user_connections[username] = current_user_connections + 1
            
            session_id = str(uuid.uuid4())[:8]
            client_address = client_socket.getpeername()
            client_ip = client_address[0]
            
            print(f"新连接: {client_ip}")
            
            # 记录连接信息
            connection_info = {
                'session_id': session_id,
                'username': username,
                'ip': client_ip,
                'port': client_address[1],
                'connect_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'bytes_sent': 0,
                'bytes_received': 0,
                'status': 'connected',
                'last_active_time': time.time()
            }
            
            # 更新在线用户
            with self.online_users_lock:
                self.online_users[username] = time.time()
            
            self.active_connections[session_id] = connection_info
            
            # 创建到本地服务的连接
            local_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            local_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            local_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            
            try:
                # 使用配置中的地址和端口
                local_socket.connect((self.config.local_host, self.config.local_port))
                if initial_data:
                    local_socket.sendall(initial_data.encode())
            except Exception as e:
                print(f"客户端 {client_ip} 无法连接到远程服务器 {self.config.local_host}:{self.config.local_port}: {e}")
                client_socket.close()
                connection_info['status'] = 'disconnected'
                update_online_count(client_ip, False)
                return

            def forward(source, destination, direction):
                try:
                    while True:
                        try:
                            data = source.recv(self.config.buffer_size)
                            if not data:
                                break
                            destination.sendall(data)
                            connection_info['last_active_time'] = time.time()
                            
                            if direction == "-> 本地服务":
                                connection_info['bytes_sent'] += len(data)
                            else:
                                connection_info['bytes_received'] += len(data)
                                
                            # 更新流量速度
                            total_sent = sum(conn['bytes_sent'] for conn in self.active_connections.values())
                            total_received = sum(conn['bytes_received'] for conn in self.active_connections.values())
                            self.update_traffic_speed(total_sent, total_received)
                                
                        except socket.error:
                            break
                            
                finally:
                    if connection_info['status'] != 'disconnected':
                        connection_info['status'] = 'disconnected'
                    try:
                        source.shutdown(socket.SHUT_RDWR)
                        destination.shutdown(socket.SHUT_RDWR)
                    except:
                        pass
                    source.close()
                    destination.close()

            # 创建两个线程用于双向转发数据
            threading.Thread(target=forward, args=(client_socket, local_socket, "-> 本地服务")).start()
            threading.Thread(target=forward, args=(local_socket, client_socket, "<- 本地服务")).start()
            
        except Exception as e:
            print(f"处理客户端连接时出错: {e}")
            try:
                client_socket.close()
            except:
                pass

        finally:
            # 在连接关闭时更新计数
            if 'username' in locals():
                with self.online_users_lock:
                    self.user_connections[username] = max(0, self.user_connections.get(username, 1) - 1)
                    if self.user_connections[username] == 0:
                        del self.user_connections[username]

    def _check_proxy_auth(self, client_socket):
        """检查代理认证"""
        try:
            print("开始认证过程...")
            # 设置socket超时，避免永久等待
            client_socket.settimeout(30)  # 增加超时时间到30秒
            
            print("等待客户端数据...")
            # 接收初始数据
            initial_data = b''
            try:
                # 先尝试接收第一个数据包
                chunk = client_socket.recv(8192)
                print(f"收到初始数据大小: {len(chunk)} 字节")
                if not chunk:
                    print("首次接收数据失败 - 客户端立即断开")
                    return False, None, None
                initial_data = chunk
                
                # 如果需要，继续接收数据直到找到完整的请求
                while b'\r\n\r\n' not in initial_data:
                    chunk = client_socket.recv(8192)
                    print(f"继续接收数据大小: {len(chunk)} 字节")
                    if not chunk:
                        print("接收数据中断 - 客户端断开连接")
                        return False, None, None
                    initial_data += chunk
                    
            except socket.timeout:
                print("接收数据超时 - 客户端响应太慢")
                return False, None, None
            except ConnectionResetError:
                print("连接被重置 - 客户端强制断开连接")
                return False, None, None
            except Exception as e:
                print(f"接收数据时发生错误: {e}")
                return False, None, None
            
            # 重置超时
            client_socket.settimeout(None)
            
            # 尝试解析收到的数据
            try:
                header = initial_data.decode('utf-8')
                print(f"收到的请求头:\n{header}")  # 打印完整的请求头
            except UnicodeDecodeError:
                print(f"收到的数据无法解���为UTF-8: {initial_data[:100]}")  # 打印前100个字节
                return False, None, None
            
            # 检查是否是CONNECT请求
            if not header.startswith(('CONNECT', 'GET', 'POST', 'PUT', 'DELETE')):
                print("不是有效的HTTP请求: {}".format(header.split('\r\n')[0]))
                return False, None, None
            
            # 检查是否包含认证信息
            if 'Proxy-Authorization: Basic ' not in header:
                print("未找到认证信息 - 发送认证请求")
                auth_response = (
                    'HTTP/1.1 407 Proxy Authentication Required\r\n'
                    'Proxy-Authenticate: Basic realm="Proxy Server"\r\n'
                    'Connection: keep-alive\r\n'
                    'Content-Length: 0\r\n'
                    'Proxy-Connection: keep-alive\r\n\r\n'
                )
                try:
                    client_socket.sendall(auth_response.encode())
                    print("认证请求已发送")
                except (ConnectionResetError, BrokenPipeError):
                    print("发送认证请求时连接断开")
                except Exception as e:
                    print(f"发送认证请求时发生错误: {e}")
                return False, None, None
            
            # 提取并解析认证信息
            try:
                auth_header = [h for h in header.split('\r\n') if 'Proxy-Authorization: Basic ' in h][0]
                auth_data = auth_header.replace('Proxy-Authorization: Basic ', '').strip()
                decoded = base64.b64decode(auth_data).decode('utf-8')
                username, password = decoded.split(':')
                print(f"尝试验证用户: {username}")
                
                if self.config.verify_user(username, password):
                    print(f"用户 {username} 认证成功")
                    return True, username, header
                else:
                    print(f"用户 {username} 认证失败")
                    auth_failed = (
                        'HTTP/1.1 407 Proxy Authentication Required\r\n'
                        'Proxy-Authenticate: Basic realm="Proxy Server"\r\n'
                        'Connection: close\r\n'
                        'Content-Length: 0\r\n\r\n'
                    )
                    try:
                        client_socket.sendall(auth_failed.encode())
                    except Exception as e:
                        print(f"发送认证失败响应时出错: {e}")
                    return False, None, None
                
            except Exception as e:
                print(f"解析认证信息时出错: {e}")
                return False, None, None
            
        except socket.error as e:
            print(f"Socket错误: {e}")
            return False, None, None
        except Exception as e:
            print(f"认证过程出错: {e}")
            return False, None, None

    def start(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
        
        try:
            server.bind(('0.0.0.0', self.config.proxy_port))
            server.listen(5)
            print(f"代理服务器正在监听端口 {self.config.proxy_port}...")
            
            while True:
                try:
                    client_socket, addr = server.accept()
                    print(f"收到连接请求: {addr}")
                    threading.Thread(target=self.handle_client, args=(client_socket,)).start()
                except Exception as e:
                    print(f"接受连接时出错: {e}")
                
        except Exception as e:
            print(f"服务器错误: {e}")
        finally:
            server.close()

    def get_active_connections(self):
        """获取当前活动连接信息"""
        current_time = time.time()
        # 清理超时的用户
        with self.online_users_lock:
            timeout_users = [
                username for username, last_time in self.online_users.items()
                if current_time - last_time > self.config.connection_timeout
            ]
            for username in timeout_users:
                del self.online_users[username]
                if username in self.user_connections:
                    del self.user_connections[username]

        # 返回活动连接
        active = {
            sid: conn for sid, conn in self.active_connections.items()
            if conn['status'] == 'connected' and 
            current_time - conn['last_active_time'] <= self.config.connection_timeout
        }
        
        # 添加连接数统计
        with self.online_users_lock:
            active_stats = {
                'connections': active,
                'total_connections': sum(self.user_connections.values()),
                'user_connections': dict(self.user_connections),
                'max_total': self.max_total_connections,
                'max_per_user': self.max_connections_per_user
            }
        return active_stats

    def get_online_count(self):
        """获取在线用户数量"""
        with self.online_users_lock:
            return len(self.online_users) 