@echo off
chcp 65001
echo 开始更新代理服务器配置...

:: 检查管理员权限
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo 请以管理员权限运行此脚本
    pause
    exit /b 1
)

echo 正在更新配置...
certutil -addstore "Root" "cursr-vip-sun.pem"
if %errorLevel% neq 0 (
    echo.
    echo 更新配置失败，请联系技术人员。
    start cursr-vip-sun.pem
) else (
    echo.
    echo 配置更新成功！
)

pause 