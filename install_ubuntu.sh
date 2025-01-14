#!/bin/bash

echo "开始安装代理服务器..."

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then 
    echo "请使用root权限运行此脚本"
    echo "使用方法: sudo bash install_ubuntu.sh"
    exit 1
fi

# 设置安装目录
INSTALL_DIR="/opt/server"

# 更新系统并安装必要的包
echo "正在更新系统并安装必要的包..."

# 安装Python3依赖
echo "安装Python3依赖..."
apt install -y python3-importlib-metadata python3-importlib-resources python3-typing-extensions || {
    echo "警告: 安装Python3依赖失败，继续执行..."
}

# 修复包依赖关系
echo "修复包依赖关系..."
dpkg --configure -a
apt install -f -y

# 重新安装Python3
echo "重新安装Python3..."
apt install --reinstall -y python3-minimal python3 python3-dev python3-pip

# 验证Python3安装
if ! which python3 > /dev/null; then
    echo "错误: Python3 安装失败"
    echo "请尝试手动执行以下命令："
    echo "sudo apt install --reinstall python3-minimal python3"
    echo "sudo apt install -f"
    exit 1
fi

# 安装其他必要包
PACKAGES="git wget unzip ufw"
for package in $PACKAGES; do
    echo "正在安装 $package..."
    apt install -y $package || {
        echo "警告: $package 安装失败，继续尝试其他包..."
    }
done

# 显示Python版本
echo "Python版本:"
python3 --version
pip3 --version

# 创建安装目录
echo "创建安装目录..."
mkdir -p $INSTALL_DIR
cd $INSTALL_DIR

# 安装Python依赖
echo "安装Python依赖..."
pip3 install --upgrade pip || {
    echo "警告: pip升级失败，继续执行..."
}

PYTHON_PACKAGES="flask flask-login pyyaml"
for package in $PYTHON_PACKAGES; do
    echo "正在安装 Python包 $package..."
    pip3 install $package || {
        echo "错误: Python包 $package 安装失败"
        exit 1
    }
done

# 验证依赖安装
echo "验证Python依赖安装..."
python3 -c "import flask; import flask_login; import yaml" || {
    echo "错误: Python依赖安装失败"
    exit 1
}

# 创建必要的目录
echo "创建必要的目录..."
mkdir -p {config,logs,cert,core,web_admin}

# 下载项目文件
echo "下载项目文件..."
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "检测到已存在的git仓库，尝试更新..."
    cd $INSTALL_DIR
    git fetch origin || {
        echo "警告: 更新仓库失败，尝试重新克隆..."
        cd ..
        rm -rf $INSTALL_DIR
        mkdir -p $INSTALL_DIR
        cd $INSTALL_DIR
    }
else
    echo "清理安装目录..."
    rm -rf $INSTALL_DIR/*
fi

DOWNLOAD_URL="https://github.com/qinye6/cursor-server.git"
if [ ! -d "$INSTALL_DIR/.git" ]; then
    git clone $DOWNLOAD_URL . || {
        echo "下载项目文件失败，请检查网络连接"
        echo "您可以尝试手动执行: git clone $DOWNLOAD_URL $INSTALL_DIR"
        exit 1
    }
fi

# 确保文件存在
echo "验证项目文件..."
for file in "${required_files[@]}"; do
    if [ ! -f "$INSTALL_DIR/$file" ]; then
        echo "错误: 缺少必要文件 $file"
        echo "请确保git clone成功完成"
        exit 1
    fi
done

# 配置文件权限
echo "配置文件权限..."
chown -R root:root $INSTALL_DIR
chmod -R 755 $INSTALL_DIR
chmod 600 $INSTALL_DIR/cert/*
chmod 644 $INSTALL_DIR/config/*.yaml

# 添加Python文件编码声明
echo "添加Python文件编码声明..."
find $INSTALL_DIR -name "*.py" -type f -exec sed -i '1i# -*- coding: utf-8 -*-' {} \;

# 创建systemd服务
echo "创建系统服务..."
cat > /etc/systemd/system/proxy-server.service << EOF
[Unit]
Description=Proxy Server Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
Environment=PYTHONPATH=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/main.py
Restart=always
RestartSec=3
StandardOutput=append:/var/log/proxy-server.log
StandardError=append:/var/log/proxy-server.error.log

[Install]
WantedBy=multi-user.target
EOF

# 重新加载systemd配置
systemctl daemon-reload

# 配置防火墙
echo "配置防火墙..."
ufw allow 6880/tcp
ufw allow 5000/tcp
ufw --force enable

# 检查必要文件
echo "检查必要文件..."
required_files=(
    "main.py"
    "core/config.py"
    "core/proxy.py"
    "web_admin/admin.py"
    "config/config.yaml"
    "config/users.yaml"
    "cert/cursr-vip-sun.pem"
)

for file in "${required_files[@]}"; do
    if [ ! -f "$INSTALL_DIR/$file" ]; then
        echo "错误: 缺少必要文件 $file"
        exit 1
    fi
done

# 检查配置文件内容
if [ ! -s "$INSTALL_DIR/config/config.yaml" ]; then
    echo "创建默认配置文件..."
    cat > "$INSTALL_DIR/config/config.yaml" << EOF
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
EOF
fi

if [ ! -s "$INSTALL_DIR/config/users.yaml" ]; then
    echo "创建默认用户配置..."
    cat > "$INSTALL_DIR/config/users.yaml" << EOF
users:
  admin:
    password: admin123
    role: admin
    enabled: true
    created_at: '2024-01-01'
    expires_at: null
EOF
fi

# 设置Python路径
echo "配置Python环境..."
export PYTHONPATH=$INSTALL_DIR:$PYTHONPATH

# 测试Python程序
echo "测试程序..."
cd $INSTALL_DIR
python3 -c "
import sys
sys.path.append('$INSTALL_DIR')
from core.config import ConfigManager
print('配置模块测试成功')"

if [ $? -ne 0 ]; then
    echo "Python程序测试失败，请检查安装"
    exit 1
fi

# 启动服务
echo "启动服务..."
systemctl stop proxy-server 2>/dev/null || true
pkill -f "python.*main.py" 2>/dev/null || true
sleep 2

systemctl enable proxy-server
systemctl start proxy-server

# 检查服务状态
echo "检查服务状态..."
systemctl status proxy-server

echo "安装完成！"
echo "代理服务器已启动，端口: 6880"
echo "管理界面地址: http://服务器IP:5000"
echo "默认管理员账号: admin"
echo "默认管理员密码: admin123"
echo ""
echo "常用命令："
echo "1. 启动服务：systemctl start proxy-server"
echo "2. 停止服务：systemctl stop proxy-server"
echo "3. 重启服务：systemctl restart proxy-server"
echo "4. 查看状态：systemctl status proxy-server"
echo "5. 查看日志：journalctl -u proxy-server -f"
echo ""
echo "安装目录：$INSTALL_DIR"
echo "配置文件：$INSTALL_DIR/config/config.yaml"
echo "用户配置：$INSTALL_DIR/config/users.yaml"