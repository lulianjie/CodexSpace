@echo off
setlocal

REM 建议在 Windows 7 上使用本机已安装的 Python 环境执行本脚本。
REM 如未安装 PyInstaller，请先执行：python -m pip install pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --windowed --name AssetLabelPrinter app.py

echo.
echo 打包完成后，可在 dist\AssetLabelPrinter.exe 中找到桌面程序。
pause
