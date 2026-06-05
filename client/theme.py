"""Темная тема оформления с приятными цветами (улучшенная читаемость)."""

from __future__ import annotations

import customtkinter as ctk

# Улучшенная цветовая палитра с повышенной читаемостью
COLORS = {
    # Основной фон - темный, но не черный
    "bg": "#1a1a2e",
    "panel": "#16213e",
    "panel_alt": "#0f3460",
    
    # Акцент - приглушенный сине-зеленый (не ярко-зеленый)
    "accent": "#4ecca3",
    "accent_hover": "#3db892",
    "accent_soft": "#1a3a2a",
    
    # Текст - светлый, хорошо читаемый
    "text": "#eaeaea",
    "text_dim": "#a0a0a0",
    
    # Границы
    "border": "#2a2a4a",
    
    # Приглушенный текст
    "muted": "#6b6b8d",
    
    # Сообщения
    "system": "#4ecca3",
    "own": "#4ecca3",
    "other": "#c3c3c3",
    "dm": "#ffd700",
    "meta": "#6b6b8d",
    
    # Статусы
    "success": "#4ecca3",
    "warning": "#f39c12",
    "danger": "#e74c3c",
    "info": "#3498db",
    
    # Фон ввода
    "input_bg": "#0f0f23",
    
    # Фон викторины
    "quiz_bg": "#1a2a3a",
}


def apply_theme() -> None:
    """Применить тему к customtkinter."""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")