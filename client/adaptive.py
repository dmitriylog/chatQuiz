"""Адаптивные размеры для поддержки разных экранов."""

from __future__ import annotations

import tkinter as tk
from typing import Tuple


class AdaptiveUI:
    """Класс для адаптивного масштабирования UI элементов."""
    
    # Базовое разрешение, для которого designed интерфейс
    BASE_WIDTH = 1140
    BASE_HEIGHT = 720
    BASE_FONT_SIZE = 13
    
    # Минимальные размеры для мобильных
    MIN_WIDTH = 360
    MIN_HEIGHT = 640
    
    def __init__(self, root: tk.Tk) -> None:
        """Инициализация адаптивного UI."""
        self.root = root
        
        # Получаем размеры экрана
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        
        # Получаем DPI масштаб (примерно)
        try:
            dpi = root.winfo_fpixels('1i')
            self.dpi_scale = dpi / 96.0  # Относительно стандартных 96 DPI
        except:
            self.dpi_scale = 1.0
        
        # Вычисляем масштаб относительно базового разрешения
        width_scale = screen_width / self.BASE_WIDTH
        height_scale = screen_height / self.BASE_HEIGHT
        
        # Используем минимальный масштаб для сохранения пропорций
        self.scale = min(width_scale, height_scale, 2.0)  # Ограничиваем 2x
        
        # Для маленьких экранов (смартфоны, планшеты)
        self.is_mobile = screen_width < 768
        self.is_tablet = 768 <= screen_width < 1024
        self.is_desktop = screen_width >= 1024
        
        # Вычисляем итоговый масштаб с учетом DPI
        self.font_scale = self.scale * self.dpi_scale
        
        # Размеры окна
        if self.is_mobile:
            # Для мобильных - используем большую часть экрана
            win_width = int(screen_width * 0.95)
            win_height = int(screen_height * 0.92)
            # Но не меньше минимальных
            win_width = max(win_width, self.MIN_WIDTH)
            win_height = max(win_height, self.MIN_HEIGHT)
        elif self.is_tablet:
            win_width = int(screen_width * 0.85)
            win_height = int(screen_height * 0.85)
        else:
            # Для десктопа - базовые размеры с ограничением
            win_width = min(int(self.BASE_WIDTH * self.scale), screen_width - 40)
            win_height = min(int(self.BASE_HEIGHT * self.scale), screen_height - 80)
        
        self.window_width = max(win_width, self.MIN_WIDTH)
        self.window_height = max(win_height, self.MIN_HEIGHT)
        
        # Пропорции для layout
        if self.is_mobile:
            self.sidebar_ratio = 1.0  # На мобильных sidebar на всю ширину сверху
            self.content_ratio = 1.0
        elif self.is_tablet:
            self.sidebar_ratio = 0.25
            self.content_ratio = 0.75
        else:
            self.sidebar_ratio = 0.22
            self.content_ratio = 0.78
    
    def font(self, size: int | None = None, weight: str = "normal") -> tuple[str, int, str]:
        """Возвращает параметры шрифта с масштабированием."""
        if size is None:
            size = self.BASE_FONT_SIZE
        scaled_size = max(int(size * self.font_scale), 10)  # Минимум 10pt
        return ("Inter", "Segoe UI", scaled_size, weight)
    
    def font_size(self, size: int) -> int:
        """Возвращает масштабированный размер шрифта."""
        return max(int(size * self.font_scale), 10)
    
    def scale_value(self, value: int) -> int:
        """Масштабирует произвольное значение."""
        return max(int(value * self.scale), int(value * 0.5))
    
    def width(self, value: int) -> int:
        """Масштабирует ширину."""
        if value == 0:
            return 0
        return max(int(value * self.scale), 20)
    
    def height(self, value: int) -> int:
        """Масштабирует высоту."""
        if value == 0:
            return 0
        return max(int(value * self.scale), 20)
    
    def padding(self, value: int) -> int:
        """Масштабирует отступы."""
        return max(int(value * self.scale), 3)
    
    def sidebar_width(self) -> int:
        """Возвращает ширину sidebar."""
        if self.is_mobile:
            return self.window_width  # На всю ширину
        return max(int(self.window_width * self.sidebar_ratio), 200)
    
    def get_window_geometry(self) -> str:
        """Возвращает строку геометрии окна."""
        # Центрируем окно
        x = (self.root.winfo_screenwidth() - self.window_width) // 2
        y = (self.root.winfo_screenheight() - self.window_height) // 2
        return f"{self.window_width}x{self.window_height}+{x}+{y}"
    
    def get_min_size(self) -> Tuple[int, int]:
        """Возвращает минимальные размеры окна."""
        if self.is_mobile:
            return (self.MIN_WIDTH, self.MIN_HEIGHT)
        return (
            max(int(self.BASE_WIDTH * 0.7 * self.scale), 600),
            max(int(self.BASE_HEIGHT * 0.7 * self.scale), 450)
        )
    
    def button_size(self, width: int, height: int) -> Tuple[int, int]:
        """Масштабирует размеры кнопки."""
        return (self.width(width), self.height(height))
    
    def entry_height(self) -> int:
        """Возвращает высоту для полей ввода."""
        return self.height(40)
    
    def is_compact(self) -> bool:
        """Возвращает True для компактного режима (мобильные/планшеты)."""
        return self.is_mobile or self.is_tablet


# Глобальный экземпляр (будет инициализирован в приложении)
_adaptive: AdaptiveUI | None = None


def get_adaptive() -> AdaptiveUI:
    """Получить глобальный экземпляр AdaptiveUI."""
    if _adaptive is None:
        raise RuntimeError("AdaptiveUI not initialized. Call init_adaptive() first.")
    return _adaptive


def init_adaptive(root: tk.Tk) -> AdaptiveUI:
    """Инициализировать глобальный экземпляр AdaptiveUI."""
    global _adaptive
    _adaptive = AdaptiveUI(root)
    return _adaptive