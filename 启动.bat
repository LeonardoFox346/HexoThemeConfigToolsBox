@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem 优先用 PATH 里的 pythonw，其次 py 启动器；不要写死某个人的 Python 路径
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw main.py
) else (
    start "" py -3w main.py
)