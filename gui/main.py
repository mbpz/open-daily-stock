"""Flet GUI 入口"""
import flet as ft

def main(page: ft.Page):
    from gui.app import StockApp
    app = StockApp(page)

if __name__ == "__main__":
    ft.app(target=main)