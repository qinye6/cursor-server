@echo off
chcp 65001
echo 启动代理服务器...

:: 检查 Python 是否已安装
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo Python未安装，请先安装Python 3.x
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 检查依赖
python -c "import yaml" >nul 2>&1
if %errorLevel% neq 0 (
    echo 缺少必要的依赖包
    echo 请运行 install_deps.bat 安装依赖
    pause
    exit /b 1
)

:: 检查配置文件
if not exist "config\config.yaml" (
    echo 错误：找不到配置文件 config\config.yaml
    echo 请先运行 install.bat 进行安装
    pause
    exit /b 1
)

:: 创建日志目录
mkdir logs 2>nul

:: 启动服务器
echo 正在启动服务器...
echo 管理界面地址: http://localhost:5000
echo 代理服务端口: 6880
echo 按 Ctrl+C 停止服务器
echo.

python main.py

pause 