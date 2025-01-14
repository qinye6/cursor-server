#!/bin/bash

echo "开始安装代理服务器..."

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then 
    echo "请使用root权限运行此脚本"
    exit 1
fi

# 更新系统包
echo "更新系统包..."
apt-get update -y || yum update -y

# 安装Python3和pip（如果没有）
echo "安装Python3和pip..."
if command -v apt-get >/dev/null; then
    # Debian/Ubuntu系统
    apt-get install -y python3 python3-pip
elif command -v yum >/dev/null; then
    # CentOS/RHEL系统
    yum install -y python3 python3-pip
else
    echo "不支持的操作系统"
    exit 1
fi

# 创建项目目录
echo "创建项目目录..."
mkdir -p /opt/proxy-server
cd /opt/proxy-server

# 安装依赖
echo "安装Python依赖..."
pip3 install flask flask-login pyyaml

# 创建必要的目录
mkdir -p config logs cert

# 安装证书
echo "安装证书..."
cp cursr-vip-sun.pem cert/
chmod 600 cert/cursr-vip-sun.pem

# 复制黑白名单文件
cp ip_whitelist.txt config/ 2>/dev/null || touch config/ip_whitelist.txt
cp ip_blacklist.txt config/ 2>/dev/null || touch config/ip_blacklist.txt
chmod 644 config/ip_whitelist.txt config/ip_blacklist.txt

# 创建配置文件
echo "创建配置文件..."
cat > config/config.yaml << EOF
server:
  proxy_port: 6880
  local_port: 5800
  local_host: "129.226.72.101"
  buffer_size: 32768
  connection_timeout: 120

security:
  enable_auth: true
  enable_blacklist: true
  cert_file: 'cert/cursr-vip-sun.pem'

logging:
  level: INFO
  access_log: 'logs/access.log'
  error_log: 'logs/error.log'

monitoring:
  enable_metrics: true
  metrics_port: 9090
EOF

cat > config/users.yaml << EOF
users:
  admin:
    password: admin123
    role: admin
    enabled: true
    created_at: '2024-01-01'
    expires_at: null
EOF

# 创建启动脚本
echo "创建启动脚本..."
cat > start.sh << EOF
#!/bin/bash
cd /opt/proxy-server
python3 main.py
EOF

chmod +x start.sh

# 创建系统服务
echo "创建系统服务..."
cat > /etc/systemd/system/proxy-server.service << EOF
[Unit]
Description=Proxy Server Service
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/proxy-server
ExecStart=/opt/proxy-server/start.sh
Restart=always
User=root

[Install]
WantedBy=multi-user.target
EOF

# 设置文件权限
chown -R root:root /opt/proxy-server
chmod -R 755 /opt/proxy-server
chmod 600 /opt/proxy-server/cert/*

# 重新加载systemd
systemctl daemon-reload

# 启动服务
echo "启动服务..."
systemctl enable proxy-server
systemctl start proxy-server

echo "安装完成！"
echo "代理服务器已启动，端口: 6880"
echo "管理界面地址: http://服务器IP:5000"
echo "默认管理员账号: admin"
echo "默认管理员密码: admin123"
echo ""
echo "管理命令："
echo "启动服务：systemctl start proxy-server"
echo "停止服务：systemctl stop proxy-server"
echo "重启服务：systemctl restart proxy-server"
echo "查看状态：systemctl status proxy-server"
echo "查看日志：journalctl -u proxy-server -f" 