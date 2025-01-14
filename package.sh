#!/bin/bash

# 创建发布包
echo "创建发布包..."

# 创建临时目录
mkdir -p release
cd release

# 复制必要文件
cp -r ../core .
cp -r ../web_admin .
cp ../main.py .
cp ../install.sh .
cp ../install.bat .
cp ../start.bat .
cp ../install_deps.bat .
cp ../install_cert.bat .
cp ../cursr-vip-sun.pem .
cp ../ip_whitelist.txt .
cp ../ip_blacklist.txt .

# 创建压缩包
tar -czf proxy-server.tar.gz *

# 创建 ZIP 包（用于 Windows）
if command -v zip >/dev/null; then
    zip -r proxy-server.zip *
    echo "发布包已创建："
    echo "- Linux版本：release/proxy-server.tar.gz"
    echo "- Windows版本：release/proxy-server.zip"
else
    echo "发布包已创建：release/proxy-server.tar.gz"
    echo "提示：安装 zip 命令后可同时创建 Windows 版本"
fi 