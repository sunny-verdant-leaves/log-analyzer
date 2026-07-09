"""
程序入口
"""
import flet as ft
from app import LogAnalyzerApp


def main():
    app = LogAnalyzerApp()
    ft.app(target=app.main)


if __name__ == "__main__":
    main()
