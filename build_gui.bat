@echo off
echo 正在打包 GUI 应用为 exe 文件...
echo.

REM 检查 PyInstaller 是否安装
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller 未安装，正在安装...
    pip install pyinstaller
    if errorlevel 1 (
        echo 安装 PyInstaller 失败！
        pause
        exit /b 1
    )
)

echo 开始打包...
pyinstaller build_gui.spec --clean

if errorlevel 1 (
    echo 打包失败！
    pause
    exit /b 1
)

echo.
echo 打包完成！
echo exe 文件位置: dist\GUI.exe
echo.
pause

