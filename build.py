"""运管站货车审验 - PyInstaller 打包脚本

用法:  python3 build.py
输出:  dist/货车审验工具.exe
"""
import PyInstaller.__main__
import os, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

PyInstaller.__main__.run([
    "--onefile",                        # 单 exe
    "--name", "HCCheck",
    "--windowed",                       # 隐藏控制台窗口(print 输出已重定向到 GUI 日志)
    "--icon", os.path.join(SCRIPT_DIR, "assets", "icon.ico"),
    "--version-file", os.path.join(SCRIPT_DIR, "assets", "version.txt"),
    "--add-data", f"{SCRIPT_DIR}{os.pathsep}popups",
    "--hidden-import", "playwright",
    "--hidden-import", "pyperclip",
    "--upx-exclude", "api-ms-win-*",
    "--clean",
    "--noconfirm",
    os.path.join(SCRIPT_DIR, "gui.py"),  # 入口: GUI
])
