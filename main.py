"""
服务器日志分析器 
Bilibili@碧叶晴天呀 设计
程序入口
"""
import flet as ft
from app import LogAnalyzerApp


def main():
    app = LogAnalyzerApp()
    ft.app(target=app.main)


if __name__ == "__main__":
    main()
