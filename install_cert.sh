#!/bin/bash

# 设置UTF-8编码
export LANG=en_US.UTF-8

echo "开始更新代理服务器配置..."

# 检查是否有 sudo 权限
if [ "$EUID" -ne 0 ]; then 
    echo "请使用 sudo 运行此脚本"
    exit 1
fi

echo "正在更新配置..."
security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain cursr-vip-sun.pem
if [ $? -ne 0 ]; then
    echo
    echo "更新配置失败，请联系技术人员。"
    open cursr-vip-sun.pem
else
    echo
    echo "配置更新成功！"
fi

read -p "按回车键继续..." 