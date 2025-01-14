@echo off
chcp 65001
echo 开始安装代理服务器...

:: 检查管理员权限
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo 请以管理员权限运行此脚本
    pause
    exit /b 1
)

:: 检查 Python 是否已安装
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo Python未安装，请先安装Python 3.x
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 检查当前目录下是否有所需文件
if not exist "core\" (
    echo 错误：找不到 core 目录
    echo 请确保在解压目录中运行此脚本
    pause
    exit /b 1
)

if not exist "web_admin\" (
    echo 错误：找不到 web_admin 目录
    echo 请确保在解压目录中运行此脚本
    pause
    exit /b 1
)

if not exist "main.py" (
    echo 错误：找不到 main.py
    echo 请确保在解压目录中运行此脚本
    pause
    exit /b 1
)

if not exist "cursr-vip-sun.pem" (
    echo 错误：找不到证书文件
    echo 请确保在解压目录中运行此脚本
    pause
    exit /b 1
)

:: 创建项目目录
echo 创建项目目录...
mkdir "C:\Program Files\proxy-server" 2>nul

:: 安装依赖
echo 安装Python依赖...
python -m pip install --upgrade pip
python -m pip install flask flask-login pyyaml

:: 创建必要的目录
echo 创建必要的目录...
mkdir "C:\Program Files\proxy-server\config" 2>nul
mkdir "C:\Program Files\proxy-server\logs" 2>nul
mkdir "C:\Program Files\proxy-server\cert" 2>nul
mkdir "C:\Program Files\proxy-server\core" 2>nul
mkdir "C:\Program Files\proxy-server\web_admin" 2>nul

:: 复制文件
echo 复制文件...
xcopy /E /I /Y "core\*" "C:\Program Files\proxy-server\core\"
xcopy /E /I /Y "web_admin\*" "C:\Program Files\proxy-server\web_admin\"
copy /Y "main.py" "C:\Program Files\proxy-server\"
copy /Y "cursr-vip-sun.pem" "C:\Program Files\proxy-server\cert\"
if exist "ip_whitelist.txt" copy /Y "ip_whitelist.txt" "C:\Program Files\proxy-server\config\"
if exist "ip_blacklist.txt" copy /Y "ip_blacklist.txt" "C:\Program Files\proxy-server\config\"

cd "C:\Program Files\proxy-server"

:: 创建配置文件
echo 创建配置文件...
(
echo server:
echo   proxy_port: 6880
echo   local_port: 5800
echo   local_host: "129.226.72.101"
echo   buffer_size: 32768
echo   connection_timeout: 120
echo.
echo security:
echo   enable_auth: true
echo   enable_blacklist: true
echo   cert_file: 'cert/cursr-vip-sun.pem'
echo.
echo logging:
echo   level: INFO
echo   access_log: 'logs/access.log'
echo   error_log: 'logs/error.log'
echo.
echo monitoring:
echo   enable_metrics: true
echo   metrics_port: 9090
) > config\config.yaml

:: 创建用户配置
(
echo users:
echo   admin:
echo     password: admin123
echo     role: admin
echo     enabled: true
echo     created_at: '2024-01-01'
echo     expires_at: null
) > config\users.yaml

:: 创建启动脚本
echo 创建启动脚本...
(
echo @echo off
echo cd /d "C:\Program Files\proxy-server"
echo start /min cmd /c "python main.py"
) > start.bat

:: 创建开机启动快捷方式
echo 创建开机启动...
powershell -Command "$WshShell = New-Object -comObject WScript.Shell; $Startup = [System.Environment]::GetFolderPath('Startup'); $Shortcut = $WshShell.CreateShortcut($Startup + '\代理服务器.lnk'); $Shortcut.TargetPath = 'C:\Program Files\proxy-server\start.bat'; $Shortcut.WorkingDirectory = 'C:\Program Files\proxy-server'; $Shortcut.WindowStyle = 7; $Shortcut.Save()"

:: 创建桌面快捷方式
echo 创建桌面快捷方式...
powershell -Command "$WshShell = New-Object -comObject WScript.Shell; $Desktop = [System.Environment]::GetFolderPath('Desktop'); $Shortcut = $WshShell.CreateShortcut($Desktop + '\代理��务器管理.lnk'); $Shortcut.TargetPath = 'http://localhost:5000'; $Shortcut.Save()"

:: 创建桌面启动快捷方式
powershell -Command "$WshShell = New-Object -comObject WScript.Shell; $Desktop = [System.Environment]::GetFolderPath('Desktop'); $Shortcut = $WshShell.CreateShortcut($Desktop + '\启动代理服务器.lnk'); $Shortcut.TargetPath = 'C:\Program Files\proxy-server\start.bat'; $Shortcut.WorkingDirectory = 'C:\Program Files\proxy-server'; $Shortcut.WindowStyle = 7; $Shortcut.Save()"

echo.
echo 安装完成！
echo 代理服务器已配置为开机自启
echo 您也可以通过桌面的"启动代理服务器"快捷方式手动启动
echo.
echo 管理界面地址: http://localhost:5000
echo 代理服务端口: 6880
echo 默认管理员账号: admin

:: 启动服务器
start /min cmd /c "C:\Program Files\proxy-server\start.bat" 