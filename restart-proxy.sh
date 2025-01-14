#!/bin/bash

echo "正在停止服务..."

# 停止systemd服务
systemctl stop proxy-server

# 查找并杀死所有相关进程
echo "清理所有相关进程..."
pkill -9 -f "python.*main.py"
pkill -9 -f "proxy-server"

# 清理PID文件
echo "清理PID文件..."
rm -f /var/run/proxy-server.pid

# 检查端口是否被占用
check_port() {
    local port=$1
    if netstat -tuln | grep -q ":$port "; then
        echo "端口 $port 仍然被占用，尝试释放..."
        pid=$(lsof -t -i:$port)
        if [ ! -z "$pid" ]; then
            kill -9 $pid
        fi
    fi
}

# 检查并释放端口
echo "检查端口..."
check_port 6880  # 代理端口
check_port 5000  # 管理界面端口

# 等待进程完全停止和端口释放
echo "等待系统资源释放..."
sleep 2

# 重新加载systemd配置
echo "重新加载systemd配置..."
systemctl daemon-reload

# 启动服务
echo "启动服务..."
systemctl start proxy-server

# 等待服务启动
echo "等待服务启动..."
sleep 2

# 检查服务状态
echo "检查服务状态..."
systemctl status proxy-server

# 检查错误日志
echo "检查错误日志..."
tail -n 20 /var/log/proxy-server.error.log

# 验证端口
echo "验证端口状态..."
netstat -tuln | grep -E ':(6880|5000)' 