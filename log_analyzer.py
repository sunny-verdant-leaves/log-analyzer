"""
服务器日志分析器 
Bilibili@碧叶晴天呀 设计
兼容入口 - 保留旧文件名，实际实现已迁移到 app.py + plugins.py
现在直接运行本文件与运行 main.py 行为一致
"""
from app import LogAnalyzerApp
from plugins import PluginManager, LogAnalysisPlugin


def main():
    import flet as ft
    app = LogAnalyzerApp()
    ft.app(target=app.main)


if __name__ == "__main__":
    main()