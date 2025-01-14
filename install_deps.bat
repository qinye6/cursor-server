@echo off
chcp 65001
echo 正在安装依赖...

:: 下载 get-pip.py
echo 下载 pip 安装程序...
powershell -Command "Invoke-WebRequest -Uri https://bootstrap.pypa.io/get-pip.py -OutFile get-pip.py"

:: 安装 pip
echo 安装 pip...
python get-pip.py

:: 安装其他依赖
echo 安装其他依赖包...
python -m pip install flask flask-login pyyaml

:: 清理
del get-pip.py

echo 安装完成！
pause 