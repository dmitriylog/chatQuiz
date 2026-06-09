"""Окно личного профиля."""

from __future__ import annotations

import base64
import io
import tkinter.filedialog as filedialog
from typing import Any, Callable

import customtkinter as ctk

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from client.theme import COLORS


class ProfileDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master: Any,
        profile: dict[str, Any],
        on_save: Callable[[str, str], None],
    ) -> None:
        super().__init__(master)
        self.title("Мой профиль")
        self.geometry("500x650")
        self.minsize(450, 550)
        self.resizable(True, True)
        self.configure(fg_color=COLORS["bg"])
        self._on_save = on_save
        self._profile = profile
        self._avatar_data: str | None = None  # Base64 encoded avatar
        self._master = master

        self.transient(master)
        self.after(100, lambda: self._do_grab())

        # Main container
        main_container = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg"])
        main_container.pack(fill="both", expand=True, padx=20, pady=20)

        card = ctk.CTkFrame(main_container, fg_color=COLORS["panel"], corner_radius=16)
        card.pack(fill="both", expand=True, padx=10, pady=10)

        # Avatar with upload/delete buttons
        self._build_avatar_section(card)

    def _build_avatar_section(self, parent: ctk.CTkFrame) -> None:
        """Создать секцию аватарки."""
        uname = self._profile.get("username", "?")
        display_name = self._profile.get("displayName", uname)
        initials = (display_name[:2] or "?").upper()
        
        # Avatar frame
        avatar_frame = ctk.CTkFrame(parent, fg_color="transparent")
        avatar_frame.pack(pady=(25, 10))
        
        # Avatar label (circle with initials or image)
        self.avatar_label = ctk.CTkLabel(
            avatar_frame,
            text=initials,
            width=80,
            height=80,
            fg_color=COLORS["accent"],
            text_color="white",
            corner_radius=40,
            font=ctk.CTkFont(size=28, weight="bold"),
        )
        self.avatar_label.pack()
        
        # Buttons frame
        btn_frame = ctk.CTkFrame(parent, fg_color="transparent")
        btn_frame.pack(pady=(0, 10))
        
        # Upload button
        ctk.CTkButton(
            btn_frame,
            text="📷 Загрузить",
            width=120,
            height=30,
            fg_color=COLORS["accent_soft"],
            text_color=COLORS["accent"],
            hover_color=COLORS["border"],
            font=ctk.CTkFont(size=11),
            command=self._upload_avatar,
        ).pack(side="left", padx=5)
        
        # Delete button
        ctk.CTkButton(
            btn_frame,
            text="🗑️ Удалить",
            width=120,
            height=30,
            fg_color=COLORS["border"],
            text_color=COLORS["text"],
            hover_color="#cbd5e1",
            font=ctk.CTkFont(size=11),
            command=self._delete_avatar,
        ).pack(side="left", padx=5)
        
        # Load existing avatar if has one
        if self._profile.get("has_avatar"):
            self._load_avatar()

        ctk.CTkLabel(
            parent, text=f"@{uname}", font=ctk.CTkFont(size=14), text_color=COLORS["muted"]
        ).pack()

        # Separator
        ctk.CTkFrame(parent, height=1, fg_color=COLORS["border"]).pack(fill="x", padx=20, pady=15)

        # Edit fields
        ctk.CTkLabel(parent, text="Oтображаемое имя", anchor="w", font=ctk.CTkFont(size=13, weight="bold")).pack(
            fill="x", padx=25, pady=(10, 0)
        )
        self.name_entry = ctk.CTkEntry(parent, height=40, fg_color=COLORS["input_bg"])
        self.name_entry.insert(0, self._profile.get("displayName", uname))
        self.name_entry.pack(fill="x", padx=25, pady=5)

        ctk.CTkLabel(parent, text="О себе", anchor="w", font=ctk.CTkFont(size=13, weight="bold")).pack(
            fill="x", padx=25, pady=(15, 0)
        )
        self.bio_entry = ctk.CTkTextbox(parent, height=100, fg_color=COLORS["input_bg"])
        self.bio_entry.insert("1.0", self._profile.get("bio", ""))
        self.bio_entry.pack(fill="x", padx=25, pady=5)

        # Separator
        ctk.CTkFrame(parent, height=1, fg_color=COLORS["border"]).pack(fill="x", padx=20, pady=15)

        # Statistics section
        stats_frame = ctk.CTkFrame(parent, fg_color=COLORS["quiz_bg"], corner_radius=12)
        stats_frame.pack(fill="x", padx=25, pady=10)

        ctk.CTkLabel(
            stats_frame,
            text="📊 Статистика викторины",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["success"]
        ).pack(anchor="w", padx=15, pady=(12, 8))

        # Stats grid
        stats_grid = ctk.CTkFrame(stats_frame, fg_color="transparent")
        stats_grid.pack(fill="x", padx=15, pady=(0, 12))

        # Row 1
        row1 = ctk.CTkFrame(stats_grid, fg_color="transparent")
        row1.pack(fill="x", pady=5)

        ctk.CTkLabel(row1, text="🏆 Игр сыграно:", width=120, anchor="w", font=ctk.CTkFont(size=12)).pack(side="left")
        ctk.CTkLabel(row1, text=str(self._profile.get('quizGames', 0)), font=ctk.CTkFont(size=12, weight="bold"), text_color=COLORS["accent"]).pack(side="left")

        # Row 2
        row2 = ctk.CTkFrame(stats_grid, fg_color="transparent")
        row2.pack(fill="x", pady=5)

        ctk.CTkLabel(row2, text="🥇 Побед:", width=120, anchor="w", font=ctk.CTkFont(size=12)).pack(side="left")
        ctk.CTkLabel(row2, text=str(self._profile.get('quizWins', 0)), font=ctk.CTkFont(size=12, weight="bold"), text_color=COLORS["success"]).pack(side="left")

        # Row 3
        row3 = ctk.CTkFrame(stats_grid, fg_color="transparent")
        row3.pack(fill="x", pady=5)

        ctk.CTkLabel(row3, text="⭐ Всего баллов:", width=120, anchor="w", font=ctk.CTkFont(size=12)).pack(side="left")
        ctk.CTkLabel(row3, text=str(self._profile.get('quizPoints', 0)), font=ctk.CTkFont(size=12, weight="bold"), text_color=COLORS["warning"]).pack(side="left")

        # Average score per game
        games = self._profile.get('quizGames', 0)
        points = self._profile.get('quizPoints', 0)
        avg = round(points / games, 1) if games > 0 else 0

        row4 = ctk.CTkFrame(stats_grid, fg_color="transparent")
        row4.pack(fill="x", pady=5)

        ctk.CTkLabel(row4, text="📈 Средний балл:", width=120, anchor="w", font=ctk.CTkFont(size=12)).pack(side="left")
        ctk.CTkLabel(row4, text=str(avg), font=ctk.CTkFont(size=12, weight="bold"), text_color=COLORS["accent"]).pack(side="left")

        # Separator
        ctk.CTkFrame(parent, height=1, fg_color=COLORS["border"]).pack(fill="x", padx=20, pady=15)

        # Buttons
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=25, pady=(10, 20))

        ctk.CTkButton(
            row,
            text="Отмена",
            width=100,
            height=40,
            fg_color=COLORS["border"],
            text_color=COLORS["text"],
            hover_color="#cbd5e1",
            command=self.destroy,
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            row,
            text="Сохранить",
            width=100,
            height=40,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self._save,
        ).pack(side="right")

    def _do_grab(self) -> None:
        try:
            self.grab_set()
        except Exception:
            pass

    def _save(self) -> None:
        name = self.name_entry.get().strip()
        bio = self.bio_entry.get("1.0", "end").strip()
        self._on_save(name, bio)
        self.destroy()

    def _upload_avatar(self) -> None:
        """Загрузить аватарку из файла."""
        file_path = filedialog.askopenfilename(
            title="Выберите изображение",
            filetypes=[("Изображения", "*.png *.jpg *.jpeg *.gif"), ("Все файлы", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            # Читаем файл и кодируем в base64
            with open(file_path, "rb") as f:
                image_data = f.read()
            
            # Проверяем размер (макс 1MB)
            if len(image_data) > 1024 * 1024:
                from tkinter import messagebox
                messagebox.showerror("Ошибка", "Файл слишком большой (макс 1MB)")
                return
            
            # Кодируем в base64
            self._avatar_data = f"data:image/png;base64,{base64.b64encode(image_data).decode('utf-8')}"
            
            # Отправляем на сервер
            if hasattr(self._master, '_conn') and self._master._connected:
                self._master._conn.send({
                    "type": "avatar_upload",
                    "avatar_data": self._avatar_data
                })
            
            # Обновляем отображение
            self._display_avatar(self._avatar_data)
            
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Ошибка", f"Не удалось загрузить аватарку: {e}")

    def _delete_avatar(self) -> None:
        """Удалить аватарку."""
        from tkinter import messagebox
        if not messagebox.askyesno("Удалить аватарку", "Вы уверены, что хотите удалить аватарку?"):
            return
        
        self._avatar_data = None
        
        # Отправляем на сервер
        if hasattr(self._master, '_conn') and self._master._connected:
            self._master._conn.send({"type": "avatar_delete"})
        
        # Восстанавливаем initials
        uname = self._profile.get("username", "?")
        display_name = self._profile.get("displayName", uname)
        initials = (display_name[:2] or "?").upper()
        
        self.avatar_label.configure(
            text=initials,
            image=None,
            fg_color=COLORS["accent"]
        )

    def _load_avatar(self) -> None:
        """Загрузить аватарку с сервера."""
        if hasattr(self._master, '_conn') and self._master._connected:
            username = self._profile.get("username", "")
            self._master._conn.send({
                "type": "get_avatar",
                "username": username
            })

    def _display_avatar(self, avatar_data: str) -> None:
        """Отобразить аватарку."""
        if not HAS_PIL:
            # Если PIL не установлен, просто показываем initials
            uname = self._profile.get("username", "?")
            display_name = self._profile.get("displayName", uname)
            initials = (display_name[:2] or "?").upper()
            self.avatar_label.configure(text=initials)
            return
        
        try:
            # Извлекаем base64 данные из data:image/...;base64,...
            if "," in avatar_data:
                b64_data = avatar_data.split(",", 1)[1]
            else:
                b64_data = avatar_data
            
            # Декодируем и создаем изображение
            image_bytes = base64.b64decode(b64_data)
            image = Image.open(io.BytesIO(image_bytes))
            
            # Изменяем размер до 80x80
            image = image.resize((80, 80), Image.Resampling.LANCZOS)
            
            # Создаем круглую маску
            mask = Image.new("L", (80, 80), 0)
            from PIL import ImageDraw
            draw = ImageDraw.Draw(mask)
            draw.ellipse([0, 0, 80, 80], fill=255)
            
            # Применяем маску
            image.put_alpha(mask)
            
            # Используем CTkImage вместо ImageTk.PhotoImage
            ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=(80, 80))
            
            # Сохраняем ссылку чтобы избежать сборки мусора
            self._avatar_image = ctk_image
            
            # Обновляем label
            self.avatar_label.configure(
                text="",
                image=ctk_image,
                fg_color="transparent"
            )
        except Exception as e:
            print(f"Error displaying avatar: {e}")
            # Возвращаем initials при ошибке
            uname = self._profile.get("username", "?")
            display_name = self._profile.get("displayName", uname)
            initials = (display_name[:2] or "?").upper()
            self.avatar_label.configure(text=initials)
