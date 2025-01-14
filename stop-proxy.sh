#!/bin/bash

echo "正在停止服务..."

# 停止systemd服务
systemctl stop proxy-server

# 查找并杀死所有相关进程
echo "清理所有相关进程..."
pkill -9 -f "python.*main.py"
pkill -9 -f "proxy-server"
pkill -9 -f "flask"

# 清理PID文件
echo "清理PID文件..."
rm -f /var/run/proxy-server.pid

# 查找并杀死占用端口的进程
echo "检查并释放端口..."
for port in 6880 5000 5800; do
    pid=$(lsof -t -i:$port 2>/dev/null)
    if [ ! -z "$pid" ]; then
        echo "正在结束端口 $port 的进程 (PID: $pid)..."
        kill -9 $pid
    fi
done

# 等待进程完全停止
echo "等待系统资源释放..."
sleep 2

# 再次检查端口
echo "验证端口状态..."
for port in 6880 5000 5800; do
    if lsof -i:$port >/dev/null 2>&1; then
        echo "警告: 端口 $port 仍被占用!"
        lsof -i:$port
    else
        echo "端口 $port 已释放"
    fi
done

# 验证服务已停止
echo "验证服务状态..."
if systemctl is-active proxy-server >/dev/null 2>&1; then
    echo "警告: 服务仍在运行"
else
    echo "服务已停止"
fi 