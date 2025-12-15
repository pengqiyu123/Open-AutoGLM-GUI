@echo off
chcp 65001 >nul
echo ========================================
echo   GUI 应用打包工具（带进度显示）
echo ========================================
echo.

REM 检查 PyInstaller 是否安装
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo [1/3] 正在安装 PyInstaller...
    pip install pyinstaller -q
    if errorlevel 1 (
        echo ❌ 安装 PyInstaller 失败！
        pause
        exit /b 1
    )
    echo ✅ PyInstaller 安装完成
    echo.
)

echo [2/3] 开始打包，请稍候...
echo.
echo 打包进度说明：
echo   - 正在分析依赖...
echo   - 正在收集文件...
echo   - 正在生成 exe...
echo   - 正在压缩文件...
echo.
echo 提示：打包过程可能需要 10-20 分钟，请耐心等待...
echo.

REM 记录开始时间
set start_time=%time%

REM 执行打包，显示详细信息
pyinstaller build_gui.spec --clean --noconfirm --log-level=INFO

REM 记录结束时间
set end_time=%time%

echo.
echo ========================================
if exist "dist\GUI.exe" (
    echo ✅ 打包成功！
    echo.
    echo 文件信息：
    for %%F in ("dist\GUI.exe") do (
        echo   文件名: %%~nxF
        echo   大小: %%~zF 字节 (约 %%~zF / 1048576 MB)
        echo   位置: %%~dpF
    )
    echo.
    echo 开始时间: %start_time%
    echo 结束时间: %end_time%
) else (
    echo ❌ 打包失败！
    echo.
    echo 请检查错误信息，常见问题：
    echo   1. 缺少依赖库
    echo   2. 模块导入错误
    echo   3. 文件路径问题
)
echo ========================================
echo.
pause

