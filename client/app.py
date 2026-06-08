"""Десктопный клиент: чат, профиль, викторина."""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import messagebox
from typing import Any

import customtkinter as ctk

from client.adaptive import init_adaptive, get_adaptive
from client.config import load_settings, save_settings
from client.connection import ChatConnection, parse_server_address
from client.profile_dialog import ProfileDialog
from client.quiz_window import QuizWindow
from client.theme import COLORS

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class ChatApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        
        # Инициализация адаптивного UI (должна быть первой!)
        self.adaptive = init_adaptive(self)
        
        # Моноширинный шрифт для хакерского стиля (создается после инициализации tkinter)
        self.HACKER_FONT = ctk.CTkFont(family="Courier New", size=12)
        self.HACKER_FONT_BOLD = ctk.CTkFont(family="Courier New", size=12, weight="bold")
        self.HACKER_FONT_LARGE = ctk.CTkFont(family="Courier New", size=16, weight="bold")
        
        # Установка размеров окна на основе адаптивной системы
        self.title("Чат и викторина")
        self.geometry(self.adaptive.get_window_geometry())
        self.minsize(*self.adaptive.get_min_size())
        self.configure(fg_color=COLORS["bg"])

        self.user_id: str | None = None
        self.username: str = ""
        self.account: str = ""
        self.profile: dict[str, Any] = {}
        self.users: list[dict[str, str]] = []
        self.chat_mode = "general"
        self.dm_target: dict[str, str] | None = None
        self._connected = False
        self._histories: dict[str, list[dict[str, Any]]] = {}
        self._auth_mode = "login"
        self.friends_list = []

        settings = load_settings()
        self._conn = ChatConnection(self._on_ws_message, self._on_ws_state)

        self._build_login()
        self._build_chat()
        # Don't create quiz window immediately - create on demand
        self.quiz_window = None
        self._show_login()

        if settings.get("username"):
            self.login_user.insert(0, settings["username"])
        if settings.get("server"):
            self.login_server.insert(0, settings["server"])
        if settings.get("use_ssl"):
            self.login_ssl.select()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_login(self) -> None:
        self.login_frame = ctk.CTkFrame(
            self, fg_color=COLORS["panel"], corner_radius=20,
            border_width=1, border_color=COLORS["border"],
        )
        self.login_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.44, relheight=0.78)

        ctk.CTkLabel(
            self.login_frame, text="Чат-квиз по футболу",
            font=ctk.CTkFont(size=26, weight="bold"), text_color=COLORS["text"],
        ).pack(pady=(28, 4))
        ctk.CTkLabel(
            self.login_frame, text="Войдите или зарегистрируйтесь",
            font=ctk.CTkFont(size=16), text_color=COLORS["muted"],
        ).pack(pady=(0, 16))

        self.auth_seg = ctk.CTkSegmentedButton(
            self.login_frame,
            values=["Вход", "Регистрация"],
            command=self._on_auth_seg,
            fg_color=COLORS["input_bg"],
            selected_color=COLORS["accent"],
        )
        self.auth_seg.pack(padx=28, pady=(0, 12))
        self.auth_seg.set("Вход")

        form = ctk.CTkFrame(self.login_frame, fg_color="transparent")
        form.pack(fill="x", padx=28)

        ctk.CTkLabel(form, text="Адрес сервера", anchor="w", text_color=COLORS["muted"]).pack(fill="x")
        self.login_server = ctk.CTkEntry(form, placeholder_text="127.0.0.1", fg_color=COLORS["input_bg"])
        self.login_server.pack(fill="x", pady=(2, 10))

        ctk.CTkLabel(form, text="Логин", anchor="w", text_color=COLORS["muted"]).pack(fill="x")
        self.login_user = ctk.CTkEntry(form, placeholder_text="ivan", fg_color=COLORS["input_bg"])
        self.login_user.pack(fill="x", pady=(2, 10))

        self.display_name_label = ctk.CTkLabel(
            form, text="Отображаемое имя", anchor="w", text_color=COLORS["muted"]
        )
        self.login_display = ctk.CTkEntry(form, placeholder_text="Иван", fg_color=COLORS["input_bg"])

        ctk.CTkLabel(form, text="Пароль", anchor="w", text_color=COLORS["muted"]).pack(fill="x")
        self.login_password = ctk.CTkEntry(form, show="•", placeholder_text="••••", fg_color=COLORS["input_bg"])
        self.login_password.pack(fill="x", pady=(2, 10))

        self.login_server_pwd = ""
        self.login_ssl = False

        self.login_status = ctk.CTkLabel(
            form, text="", text_color=COLORS["muted"], font=ctk.CTkFont(size=11), wraplength=340
        )
        self.login_status.pack(pady=6)

        self.login_btn = ctk.CTkButton(
            form, text="Войти", height=42, fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"], command=self._do_login,
        )
        self.login_btn.pack(fill="x", pady=(4, 20))
        self._on_auth_seg("Вход")

    def _ensure_quiz_window(self) -> None:
        """Create quiz window if it doesn't exist or was destroyed."""
        try:
            if self.quiz_window is None or not self.quiz_window.winfo_exists():
                self.quiz_window = QuizWindow(
                    self,
                    on_answer=self._quiz_answer,
                    on_send_message=self._send_from_quiz
                )
                self.quiz_window.withdraw()
        except (tk.TclError, AttributeError):
            self.quiz_window = QuizWindow(
                self,
                on_answer=self._quiz_answer,
                on_send_message=self._send_from_quiz
            )
            self.quiz_window.withdraw()

    def _on_auth_seg(self, value: str) -> None:
        self._auth_mode = "register" if value == "Регистрация" else "login"
        if self._auth_mode == "register":
            self.display_name_label.pack(fill="x", before=self.login_password)
            self.login_display.pack(fill="x", pady=(2, 10), before=self.login_password)
            self.login_btn.configure(text="Зарегистрироваться")
        else:
            self.display_name_label.pack_forget()
            self.login_display.pack_forget()
            self.login_btn.configure(text="Войти")

    def _build_chat(self) -> None:
        self.chat_frame = ctk.CTkFrame(self, fg_color="transparent")

        # Top bar - адаптивная высота
        top_height = self.adaptive.height(56)
        top = ctk.CTkFrame(
            self.chat_frame, fg_color=COLORS["panel"], height=top_height,
            corner_radius=0, border_width=0,
        )
        top.pack(fill="x")
        top.pack_propagate(False)

        # Заголовок с адаптивным шрифтом
        title_size = self.adaptive.font_size(17)
        self.header_title = ctk.CTkLabel(
            top, text="Общий чат", font=ctk.CTkFont(size=title_size, weight="bold"),
        )
        self.header_title.pack(side="left", padx=self.adaptive.padding(16), pady=self.adaptive.padding(14))

        # Статус с адаптивным шрифтом
        status_size = self.adaptive.font_size(12)
        self.header_status = ctk.CTkLabel(
            top, text="Отключено", text_color=COLORS["muted"], font=ctk.CTkFont(size=status_size),
        )
        self.header_status.pack(side="left")

        # Кнопки в шапке - адаптивные размеры
        btn_width = self.adaptive.width(100)
        btn_height = self.adaptive.height(36)
        font_size = self.adaptive.font_size(12)

        # Button to return to general chat (hidden when already in general chat)
        self.general_chat_btn = ctk.CTkButton(
            top, text="📢 Общий чат", width=btn_width, height=btn_height,
            fg_color=COLORS["accent_soft"], text_color=COLORS["accent"],
            hover_color=COLORS["border"], font=ctk.CTkFont(size=font_size),
            command=self._open_general,
        )
        self.general_chat_btn.pack(side="right", padx=(0, self.adaptive.padding(6)), pady=self.adaptive.padding(10))
        self.general_chat_btn.pack_forget()  # Hide by default

        # Кнопка профиля
        profile_width = self.adaptive.width(88)
        ctk.CTkButton(
            top, text="Профиль", width=profile_width, height=btn_height,
            fg_color=COLORS["accent_soft"], text_color=COLORS["accent"],
            hover_color=COLORS["border"], font=ctk.CTkFont(size=font_size),
            command=self._open_profile,
        ).pack(side="right", padx=(0, self.adaptive.padding(6)), pady=self.adaptive.padding(10))

        # Кнопка викторины
        quiz_width = self.adaptive.width(110)
        ctk.CTkButton(
            top, text="⚽ Викторина", width=quiz_width, height=btn_height,
            fg_color=COLORS["success"], hover_color="#047857",
            font=ctk.CTkFont(size=font_size), command=self._quiz_start,
        ).pack(side="right", padx=self.adaptive.padding(6), pady=self.adaptive.padding(10))

        # Кнопка выхода
        logout_width = self.adaptive.width(80)
        ctk.CTkButton(
            top, text="Выйти", width=logout_width, height=btn_height,
            fg_color=COLORS["border"], text_color=COLORS["text"],
            hover_color="#cbd5e1", font=ctk.CTkFont(size=font_size),
            command=self._logout,
        ).pack(side="right", padx=self.adaptive.padding(12), pady=self.adaptive.padding(10))

        body = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        body.pack(fill="both", expand=True)

        # Sidebar - адаптивная ширина
        sidebar_width = self.adaptive.sidebar_width()
        sidebar = ctk.CTkFrame(
            body, width=sidebar_width, fg_color=COLORS["panel"],
            border_width=1, border_color=COLORS["border"],
        )
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # Scrollable sidebar content
        sidebar_pad = self.adaptive.padding(5)
        sidebar_scroll = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
        sidebar_scroll.pack(fill="both", expand=True, padx=sidebar_pad, pady=sidebar_pad)

        # Адаптивные размеры шрифтов для sidebar
        header_font_size = self.adaptive.font_size(13)
        small_font_size = self.adaptive.font_size(11)
        btn_icon_size = self.adaptive.font_size(14)

        # Friends section
        friends_header_frame = ctk.CTkFrame(sidebar_scroll, fg_color="transparent")
        friends_header_frame.pack(fill="x", pady=(sidebar_pad, 0))

        self.friends_header = ctk.CTkButton(
            friends_header_frame,
            text="👥 Друзья ▼",
            anchor="w",
            fg_color="transparent",
            text_color=COLORS["accent"],
            font=ctk.CTkFont(size=header_font_size, weight="bold"),
            command=self._toggle_friends_section,
        )
        self.friends_header.pack(side="left", fill="x", expand=True)

        refresh_friends_btn = ctk.CTkButton(
            friends_header_frame,
            text="🔄",
            width=self.adaptive.width(30),
            fg_color="transparent",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=btn_icon_size),
            command=self._load_friends,
        )
        refresh_friends_btn.pack(side="right", padx=(0, sidebar_pad))

        self.friends_frame = ctk.CTkFrame(sidebar_scroll, fg_color="transparent")
        friends_height = self.adaptive.height(150)
        self.friends_box = ctk.CTkScrollableFrame(self.friends_frame, fg_color="transparent", height=friends_height)
        self.friends_box.pack(fill="both", expand=True, padx=sidebar_pad, pady=2)
        self.friends_expanded = False
        self.friends_frame.pack_forget()

        # All users section (expandable) - this is the MAIN users list
        self.users_header = ctk.CTkButton(
            sidebar_scroll,
            text="🌐 Все пользователи ▼",
            anchor="w",
            fg_color="transparent",
            text_color=COLORS["accent"],
            font=ctk.CTkFont(size=header_font_size, weight="bold"),
            command=self._toggle_users_section,
        )
        self.users_header.pack(fill="x", pady=(self.adaptive.padding(10), 0))

        self.users_frame = ctk.CTkFrame(sidebar_scroll, fg_color="transparent")
        users_height = self.adaptive.height(250)
        self.users_box = ctk.CTkScrollableFrame(self.users_frame, fg_color="transparent", height=users_height)
        self.users_box.pack(fill="both", expand=True, padx=sidebar_pad, pady=2)
        self.users_expanded = True
        self.users_frame.pack(fill="both", expand=True, pady=(0, sidebar_pad))

        # Pending requests section
        requests_header_frame = ctk.CTkFrame(sidebar_scroll, fg_color="transparent")
        requests_header_frame.pack(fill="x", pady=(self.adaptive.padding(10), 0))

        self.requests_header = ctk.CTkButton(
            requests_header_frame,
            text="📨 Заявки в друзья ▶",
            anchor="w",
            fg_color="transparent",
            text_color=COLORS["warning"],
            font=ctk.CTkFont(size=small_font_size),
            command=self._toggle_requests_section,
        )
        self.requests_header.pack(side="left", fill="x", expand=True)

        refresh_requests_btn = ctk.CTkButton(
            requests_header_frame,
            text="🔄",
            width=self.adaptive.width(30),
            fg_color="transparent",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=btn_icon_size),
            command=self._load_pending_requests,
        )
        refresh_requests_btn.pack(side="right", padx=(0, sidebar_pad))

        self.requests_frame = ctk.CTkFrame(sidebar_scroll, fg_color="transparent")
        requests_height = self.adaptive.height(120)
        self.requests_box = ctk.CTkScrollableFrame(self.requests_frame, fg_color="transparent", height=requests_height)
        self.requests_box.pack(fill="both", expand=True, padx=sidebar_pad, pady=2)
        self.requests_expanded = False
        self.requests_frame.pack_forget()

        # Hint - адаптивный
        hint = ctk.CTkFrame(sidebar_scroll, fg_color=COLORS["quiz_bg"], corner_radius=self.adaptive.scale_value(10))
        hint.pack(fill="x", padx=sidebar_pad, pady=(self.adaptive.padding(10), sidebar_pad))
        hint_font_size = self.adaptive.font_size(11)
        hint_wraplength = self.adaptive.width(200)
        ctk.CTkLabel(
            hint,
            text="Викторина откроется в отдельном окне.\nНужно ≥2 игрока онлайн.",
            font=ctk.CTkFont(size=hint_font_size), text_color=COLORS["success"],
            wraplength=hint_wraplength, justify="left",
        ).pack(padx=self.adaptive.padding(10), pady=self.adaptive.padding(8))

        # Center area (chat)
        center = ctk.CTkFrame(body, fg_color=COLORS["bg"])
        center.pack(side="left", fill="both", expand=True)

        # Messages box с адаптивным шрифтом
        msg_font_size = self.adaptive.font_size(13)
        msg_pad = self.adaptive.padding(12)
        self.messages_box = ctk.CTkTextbox(
            center, fg_color=COLORS["panel"], text_color=COLORS["text"],
            font=ctk.CTkFont(size=msg_font_size), wrap="word",
            border_width=1, border_color=COLORS["border"],
            activate_scrollbars=True, state="disabled",
        )
        self.messages_box.pack(fill="both", expand=True, padx=msg_pad, pady=msg_pad)
        self.messages_box.tag_config("system", foreground=COLORS["system"])
        self.messages_box.tag_config("own", foreground=COLORS["own"])
        self.messages_box.tag_config("other", foreground=COLORS["other"])
        self.messages_box.tag_config("dm", foreground=COLORS["dm"])
        self.messages_box.tag_config("meta", foreground=COLORS["muted"])

        # Bottom input area
        bottom_height = self.adaptive.height(90)
        bottom = ctk.CTkFrame(
            center, fg_color=COLORS["panel"], height=bottom_height,
            border_width=1, border_color=COLORS["border"],
        )
        bottom.pack(fill="x", padx=msg_pad, pady=(0, msg_pad))
        bottom.pack_propagate(False)

        # Input field
        input_height = self.adaptive.height(54)
        self.input_field = ctk.CTkTextbox(
            bottom, height=input_height, font=ctk.CTkFont(size=msg_font_size),
            fg_color=COLORS["input_bg"],
        )
        self.input_field.pack(side="left", fill="both", expand=True,
                              padx=(msg_pad, self.adaptive.padding(8)), pady=msg_pad)
        self.input_field.bind("<Return>", self._on_enter)

        # Send button
        send_width = self.adaptive.width(110)
        send_height = self.adaptive.height(40)
        ctk.CTkButton(
            bottom, text="Отправить", width=send_width, height=send_height,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(size=font_size), command=self._send_message,
        ).pack(side="right", padx=msg_pad, pady=msg_pad)

    def _toggle_friends_section(self) -> None:
        """Toggle friends section visibility."""
        if self.friends_expanded:
            self.friends_frame.pack_forget()
            self.friends_header.configure(text="👥 Друзья ▶")
            self.friends_expanded = False
        else:
            self.friends_frame.pack(fill="both", expand=True, pady=(0, 5))
            self.friends_header.configure(text="👥 Друзья ▼")
            self.friends_expanded = True
            # Load friends only when expanding
            if self._connected:
                self._conn.send({"type": "get_friends"})

    def _toggle_users_section(self) -> None:
        """Toggle users section visibility."""
        if self.users_expanded:
            self.users_frame.pack_forget()
            self.users_header.configure(text="🌐 Все пользователи ▶")
            self.users_expanded = False
        else:
            self.users_frame.pack(fill="both", expand=True, pady=(0, 5))
            self.users_header.configure(text="🌐 Все пользователи ▼")
            self.users_expanded = True
            self._refresh_users()

    def _toggle_requests_section(self) -> None:
        """Toggle pending requests section visibility."""
        if self.requests_expanded:
            self.requests_frame.pack_forget()
            self.requests_header.configure(text="📨 Заявки в друзья ▶")
            self.requests_expanded = False
        else:
            self.requests_frame.pack(fill="both", expand=True, pady=(0, 5))
            self.requests_header.configure(text="📨 Заявки в друзья ▼")
            self.requests_expanded = True
            self._load_pending_requests()

    def _load_friends(self) -> None:
        """Load friends list from server."""
        if self._connected:
            self._conn.send({"type": "get_friends"})

    def _load_pending_requests(self) -> None:
        """Load pending friend requests."""
        if self._connected:
            self._conn.send({"type": "get_pending_requests"})

    def _refresh_friends_list(self, friends: list[dict]) -> None:
        """Display friends list."""
        for w in self.friends_box.winfo_children():
            w.destroy()

        self.friends_list = friends  # Store friends list

        if not friends:
            ctk.CTkLabel(
                self.friends_box,
                text="Нет друзей",
                font=ctk.CTkFont(size=12),
                text_color=COLORS["muted"],
            ).pack(pady=20)
            return

        for friend in friends:
            name = friend.get('display_name', friend.get('username', '?'))
            username = friend.get('username', '')
            friend_id = friend.get('user_id', '')
            is_online = friend.get('is_online', False)

            print(f"Adding friend: {name} (username: {username}, ID: {friend_id}, online: {is_online})")  # Debug

            # Use online status from server response, fallback to checking users list
            if not is_online:
                is_online = any(u.get('username') == username for u in self.users)
            status_icon = "🟢" if is_online else "⚫"

            # Create frame for each friend
            friend_frame = ctk.CTkFrame(self.friends_box, fg_color="transparent")
            friend_frame.pack(fill="x", pady=2)

            btn = ctk.CTkButton(
                friend_frame,
                text=f"{status_icon} {name}",
                anchor="w",
                height=34,
                fg_color="transparent",
                text_color=COLORS["text"],
                hover_color=COLORS["border"],
            )
            btn.pack(side="left", fill="x", expand=True)
            # Use friend_id for DM (session ID if online, otherwise we need to handle offline)
            def on_friend_right_click(event, fid=friend_id, n=username):
                event.widget.configure(state="disabled")
                self.after(10, lambda: event.widget.configure(state="normal"))
                if fid:
                    self._open_user_profile({"id": fid, "username": n})
            
            btn.configure(command=lambda fid=friend_id, n=username: self._open_dm({"id": fid, "username": n}) if fid else None)
            btn.bind("<Button-3>", on_friend_right_click)

            # Remove friend button
            remove_btn = ctk.CTkButton(
                friend_frame,
                text="✕",
                width=30,
                height=30,
                fg_color="transparent",
                text_color=COLORS["danger"],
                hover_color=COLORS["border"],
                command=lambda fn=username: self._confirm_remove_friend(fn, fn)
            )
            remove_btn.pack(side="right", padx=(0, 5))

    def _confirm_remove_friend(self, friend_id: str, friend_username: str) -> None:
        """Confirm friend removal."""
        if messagebox.askyesno("Удалить друга", f"Вы уверены, что хотите удалить {friend_username} из друзей?"):
            self._conn.send({
                "type": "remove_friend",
                "friend_id": friend_id,
                "friend_username": friend_username,
            })

    def _refresh_pending_requests(self, requests: list[dict]) -> None:
        """Display pending friend requests."""
        for w in self.requests_box.winfo_children():
            w.destroy()

        if not requests:
            ctk.CTkLabel(
                self.requests_box,
                text="Нет заявок",
                font=ctk.CTkFont(size=11),
                text_color=COLORS["muted"],
            ).pack(pady=10)
            return

        for req in requests:
            frame = ctk.CTkFrame(self.requests_box, fg_color=COLORS["input_bg"], corner_radius=8)
            frame.pack(fill="x", pady=3, padx=2)

            name = req.get('display_name', req.get('username', '?'))
            from_user_id = req.get('from_user_id', '')

            ctk.CTkLabel(
                frame,
                text=f"📨 {name}",
                anchor="w",
                font=ctk.CTkFont(size=11),
            ).pack(side="left", padx=8, pady=5)

            ctk.CTkButton(
                frame,
                text="✅",
                width=30,
                fg_color=COLORS["success"],
                command=lambda fid=from_user_id: self._accept_friend(fid),
            ).pack(side="right", padx=2, pady=2)

            ctk.CTkButton(
                frame,
                text="❌",
                width=30,
                fg_color=COLORS["danger"],
                command=lambda fid=from_user_id: self._reject_friend(fid),
            ).pack(side="right", padx=2, pady=2)

    def _accept_friend(self, from_user_id: str) -> None:
        """Accept friend request."""
        if self._connected:
            self._conn.send({"type": "accept_friend", "from_user_id": from_user_id})

    def _reject_friend(self, from_user_id: str) -> None:
        """Reject friend request."""
        if self._connected:
            self._conn.send({"type": "reject_friend", "from_user_id": from_user_id})

    def _show_login(self) -> None:
        self.chat_frame.pack_forget()
        self.login_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.44, relheight=0.78)

    def _show_chat(self) -> None:
        self.login_frame.place_forget()
        self.chat_frame.pack(fill="both", expand=True)

    def _do_login(self) -> None:
        server = self.login_server.get().strip()
        username = self.login_user.get().strip()
        password = self.login_password.get()

        if not server or not username or not password:
            self.login_status.configure(text="Заполните сервер, логин и пароль", text_color=COLORS["danger"])
            return

        try:
            parse_server_address(server, False)
        except ValueError as exc:
            self.login_status.configure(text=str(exc), text_color=COLORS["danger"])
            return

        self.login_btn.configure(state="disabled")
        self.login_status.configure(text="Подключение…", text_color=COLORS["muted"])
        save_settings(server, username, False)

        display_name = ""
        if self._auth_mode == "register":
            display_name = self.login_display.get().strip()

        self._conn.connect(
            server,
            username,
            password,
            False,  # use_ssl
            auth_action=self._auth_mode,
            server_password="",  # server_pwd
            display_name=display_name,
        )

    def _on_ws_state(self, state: str) -> None:
        self.after(0, lambda: self._apply_state(state))

    def _apply_state(self, state: str) -> None:
        if state == "connecting":
            self.login_status.configure(text="Подключение…")
            self.header_status.configure(text="Подключение…")
        elif state == "connected":
            self._connected = True
            self.login_btn.configure(state="normal")
            self._show_chat()
            self.header_status.configure(text="В сети", text_color=COLORS["success"])
        elif state == "auth_failed":
            self._connected = False
            self.login_btn.configure(state="normal")
            self.header_status.configure(text="Ошибка", text_color=COLORS["danger"])
        elif state.startswith("error:"):
            self._connected = False
            self.login_btn.configure(state="normal")
            self.login_status.configure(text=f"Ошибка: {state[6:]}", text_color=COLORS["danger"])
        elif state == "disconnected":
            self._connected = False
            self.header_status.configure(text="Отключено", text_color=COLORS["muted"])
            if self.chat_frame.winfo_ismapped():
                self._append_line("Соединение с сервером потеряно\n", "system")

    def _on_ws_message(self, data: dict[str, Any]) -> None:
        self.after(0, lambda: self._handle_message(data))

    def _handle_message(self, data: dict[str, Any]) -> None:
        msg_type = data.get("type")

        if msg_type == "auth_error":
            self.login_status.configure(text=data.get("text", "Ошибка"), text_color=COLORS["danger"])
            self.login_btn.configure(state="normal")
            messagebox.showerror("Вход", data.get("text", "Ошибка авторизации"))
            return

        if msg_type == "user_profile":
            # Extract the requested user info
            profile = data.get("profile", {})
            requested_user_id = data.get("requested_user_id", "")
            requested_username = data.get("requested_username", "")
            self._show_user_profile(profile, requested_user_id, requested_username)
            return

        if msg_type == "friend_request_received":
            from_user_id = data.get("from_user_id", "")
            from_username = data.get("from_username", "")

            # Show notification
            self._show_system_entry("general", f"📨 Новый запрос в друзья от {from_username}")

            # Update pending requests section
            self._load_pending_requests()

            # Show popup
            if messagebox.askyesno("Запрос в друзья",
                                   f"Пользователь {from_username} хочет добавить вас в друзья. Принять?"):
                self._conn.send({"type": "accept_friend", "from_user_id": from_user_id})
            else:
                self._conn.send({"type": "reject_friend", "from_user_id": from_user_id})
            return

        if msg_type == "friend_request_accepted":
            by_username = data.get("by_username", "")
            self._show_system_entry("general", f"✅ {by_username} принял(а) ваш запрос в друзья!")
            # Refresh both friends and pending requests
            self._load_friends()
            self._load_pending_requests()
            return

        if msg_type == "friend_list_updated":
            # Force refresh friends list and pending requests
            self._load_friends()
            self._load_pending_requests()
            return

        if msg_type == "friend_removed":
            friend_username = data.get("friend_username", "")
            self._show_system_entry("general", f"❌ {friend_username} удален из друзей")
            self._load_friends()  # Reload friends list
            return

        if msg_type == "pending_requests_updated":
            self._load_pending_requests()
            return

        if msg_type == "friend_request_rejected":
            by_username = data.get("by_username", "")
            self._show_system_entry("general", f"❌ {by_username} отклонил(а) вашу заявку в друзья")
            # Refresh pending requests for the sender
            self._load_pending_requests()
            return

        if msg_type == "quiz_invite_received":
            from_user_id = data.get("from_user_id", "")
            from_username = data.get("from_username", "")
            
            # Show notification
            self._show_system_entry("general", f"🎮 {from_username} приглашает вас в викторину!")
            
            # Show dialog with accept/decline
            if messagebox.askyesno("Приглашение в викторину",
                                   f"{from_username} приглашает вас сыграть в викторину. Принять?"):
                self._conn.send({
                    "type": "quiz_invite_accept",
                    "from_user_id": from_user_id
                })
            else:
                self._conn.send({
                    "type": "quiz_invite_decline",
                    "from_user_id": from_user_id
                })
            return

        if msg_type == "quiz_invite_accepted":
            players = data.get("players", [])
            player_names = ", ".join([p.get("username", "?") for p in players])
            self._show_system_entry("general", f"🎮 Викторина начинается! Игроки: {player_names}")
            return

        if msg_type == "quiz_invite_declined":
            by_username = data.get("by_username", "")
            self._show_system_entry("general", f"❌ {by_username} отклонил(а) приглашение в викторину")
            return

        if msg_type == "quiz_player_exited":
            username = data.get("username", "")
            self._show_system_entry("general", f"🚪 {username} вышел(а) из викторины")
            return

        if msg_type == "avatar_result":
            success = data.get("success", False)
            message = data.get("message", "")
            if success:
                # Обновляем профиль
                if self.profile:
                    self.profile["has_avatar"] = True
                messagebox.showinfo("Аватарка", message)
            else:
                messagebox.showerror("Аватарка", message)
            return

        if msg_type == "avatar_data":
            username = data.get("username", "")
            avatar_data = data.get("avatar_data")
            # Сохраняем в кэш для последующего отображения
            if not hasattr(self, 'avatar_cache'):
                self.avatar_cache = {}
            self.avatar_cache[username] = avatar_data
            return

        if msg_type == "friend_status":
            is_friend = data.get("is_friend", False)
            username = data.get("username", "")
            # Store this info for later use
            if not hasattr(self, 'friend_status_cache'):
                self.friend_status_cache = {}
            self.friend_status_cache[username] = is_friend
            return

        def _refresh_friend_status(self, user_id: str) -> None:
            """Refresh friend status for a user."""
            if self._connected:
                self._conn.send({"type": "check_friend_status", "user_id": user_id})

        if msg_type == "friends_list":
            self.friends_list = data.get("friends", [])
            self._refresh_friends_list(self.friends_list)
            return

        if msg_type == "pending_requests":
            self._refresh_pending_requests(data.get("requests", []))
            # Show badge if there are pending requests
            count = len(data.get("requests", []))
            if count > 0:
                self.requests_header.configure(
                    text=f"📨 Заявки в друзья ({count}) ▼" if self.requests_expanded else f"📨 Заявки в друзья ({count}) ▶")
            else:
                self.requests_header.configure(
                    text="📨 Заявки в друзья ▼" if self.requests_expanded else "📨 Заявки в друзья ▶")
            return

        if msg_type == "friend_request_result":
            if not data.get("success", False):
                messagebox.showwarning("Друзья", data.get("message", "Ошибка при отправке заявки"))
            return

        if msg_type == "welcome":
            self.user_id = data.get("userId")
            self.username = data.get("username", "")
            self.account = data.get("account", self.username)
            self.profile = data.get("profile") or {}
            self.users = data.get("users") or []
            self._refresh_users()
            welcome = f"Добро пожаловать, {self.username}!"
            self._histories.setdefault("general", [])
            if not any("Добро" in e.get("text", "") for e in self._histories["general"] if e.get("kind") == "system"):
                self._remember_system("general", welcome)
            if self.chat_mode == "general":
                self._reload_history_view("general")
            #self._check_state()
            return

        if msg_type == "quiz_lobby_opened":
            self._ensure_quiz_window()
            if self.quiz_window and hasattr(self.quiz_window, 'winfo_exists') and self.quiz_window.winfo_exists():
                self.quiz_window.show_lobby(0, len(self.users))
            self._show_system_entry("general", "🎮 Открыто лобби викторины! Нажмите 'Готов' для участия.")
            return

        if msg_type == "quiz_lobby_countdown":
            self._ensure_quiz_window()
            if self.quiz_window and hasattr(self.quiz_window, 'winfo_exists') and self.quiz_window.winfo_exists():
                self.quiz_window.show_lobby(
                    data.get("ready_count", 0),
                    data.get("total_online", len(self.users)),
                    data.get("seconds", 0)
                )
            return

        if msg_type == "quiz_player_ready":
            self._show_system_entry("general", f"✅ {data.get('username')} готов к викторине!")
            return

        if msg_type == "quiz_lobby_cancelled":
            self._show_system_entry("general", f"❌ Лобби викторины закрыто ({data.get('cancelled_by')})")
            return

        if msg_type == "profile_updated":
            self.profile = data.get("profile") or self.profile
            self.username = self.profile.get("displayName", self.username)
            self._refresh_users()
            return

        if msg_type == "history":
            self._apply_server_history(data)
            return

        if msg_type == "quiz_started":
            # Проверяем, не выходил ли пользователь из викторины
            if self.quiz_window and hasattr(self.quiz_window, '_exited') and self.quiz_window._exited:
                return
            
            self._ensure_quiz_window()
            if self.quiz_window and hasattr(self.quiz_window, 'winfo_exists') and self.quiz_window.winfo_exists():
                self.quiz_window.open_waiting("Викторина началась!")
            self._show_system_entry("general", "⚽ Викторина началась!")
            return

        if msg_type == "quiz_player_answered":
            self.quiz_window.set_waiting(data.get("answeredCount", 0), data.get("totalPlayers", 0))
            return

        # В методе _handle_message, замените блоки с quiz_window:
        if msg_type == "quiz_question":
            # Проверяем, не выходил ли пользователь из викторины
            if self.quiz_window and hasattr(self.quiz_window, '_exited') and self.quiz_window._exited:
                return  # Не показываем вопросы если пользователь вышел
            
            if self.quiz_window and hasattr(self.quiz_window, 'winfo_exists') and self.quiz_window.winfo_exists():
                self.quiz_window.show_question(data)
            else:
                # Recreate quiz window if needed
                self._ensure_quiz_window()
                if self.quiz_window:
                    self.quiz_window.show_question(data)
            return

        if msg_type == "quiz_round_result":
            # Проверяем, не выходил ли пользователь из викторины
            if self.quiz_window and hasattr(self.quiz_window, '_exited') and self.quiz_window._exited:
                return
            
            if self.quiz_window and hasattr(self.quiz_window, 'winfo_exists') and self.quiz_window.winfo_exists():
                self.quiz_window.show_round_result(data)
            else:
                self._ensure_quiz_window()
                if self.quiz_window:
                    self.quiz_window.show_round_result(data)
            self._show_system_entry("general", f"Правильно: {data.get('correctText', '')}")
            return

        if msg_type == "quiz_finished":
            # Проверяем, не выходил ли пользователь из викторины
            if self.quiz_window and hasattr(self.quiz_window, '_exited') and self.quiz_window._exited:
                return
            
            if self.quiz_window and hasattr(self.quiz_window, 'winfo_exists') and self.quiz_window.winfo_exists():
                self.quiz_window.show_finished(data)
            else:
                self._ensure_quiz_window()
                if self.quiz_window:
                    self.quiz_window.show_finished(data)
            w = data.get("winner") or {}
            self._show_system_entry("general", f"🏆 Победитель: {w.get('username')} ({w.get('score')} б.)")
            if w.get("username") == self.account or w.get("username") == self.username:
                self.profile["quizWins"] = self.profile.get("quizWins", 0) + 1
            return

        if msg_type == "quiz_state":
            # Проверяем, не выходил ли пользователь из викторины
            if self.quiz_window and hasattr(self.quiz_window, '_exited') and self.quiz_window._exited:
                return
            
            if data.get("active"):
                if self.quiz_window and hasattr(self.quiz_window, 'winfo_exists') and self.quiz_window.winfo_exists():
                    self.quiz_window.apply_state(data, self.user_id)
                else:
                    self._ensure_quiz_window()
                    if self.quiz_window:
                        self.quiz_window.apply_state(data, self.user_id)
            return

        if msg_type == "quiz_error":
            text = data.get("text", "Ошибка")
            if self.quiz_window and hasattr(self.quiz_window, 'winfo_exists') and self.quiz_window.winfo_exists():
                self.quiz_window.show_error(text)
            messagebox.showwarning("Викторина", text)
            return

        if msg_type == "quiz_lobby_countdown":
            self._ensure_quiz_window()
            self.quiz_window.show_lobby(
                data.get("ready_count", 0),
                data.get("total_online", len(self.users)),
                data.get("seconds", 0)
            )
            return

        if msg_type == "quiz_player_ready":
            self._show_system_entry("general", f"✅ {data.get('username')} готов к викторине!")
            return

        if msg_type == "quiz_lobby_cancelled":
            self._show_system_entry("general", f"❌ Лобби викторины закрыто ({data.get('cancelled_by')})")
            return

        if msg_type in ("user_joined", "user_left", "user_renamed"):
            self.users = data.get("users") or self.users
            self._refresh_users()
            return

        if msg_type == "system":
            if self.chat_mode == "general":
                self._show_system_entry("general", data.get("text", ""))
            return

        if msg_type == "message":
            is_own = data.get("isEcho") or data.get("userId") == self.user_id
            author = "Вы" if is_own else data.get("username", "?")
            text = data.get("text", "")
            timestamp = data.get("timestamp")

            # Show in general chat
            self._show_chat_entry("general", author, text, timestamp, "own" if is_own else "other")

            # Also show in quiz window if it's open
            if self.quiz_window and hasattr(self.quiz_window, 'add_chat_message'):
                self.quiz_window.add_chat_message(author, text, is_own=is_own)

            return

        if msg_type == "dm":
            print("=== DM RECEIVED IN CLIENT ===")
            print(f"Full data: {data}")

            is_echo = bool(data.get("isEcho"))
            print(f"Is echo: {is_echo}")

            # Determine peer ID
            if is_echo:
                peer_id = data.get("toUserId")
            else:
                peer_id = data.get("userId")

            print(f"Peer ID: {peer_id}")
            print(f"My user_id: {self.user_id}")

            if not peer_id:
                print("No peer_id, skipping")
                return

            # For echo messages from ourselves, skip if we already added locally
            is_own = is_echo or data.get("userId") == self.user_id

            # For non-echo messages from others, always show
            if not is_own:
                print(f"Received DM from {data.get('username')}")
                # Show notification in general chat
                self._show_system_entry("general",
                                        f"💬 Новое личное сообщение от {data.get('username')} (откройте личный чат)")

                # Store in history
                key = self._dm_history_key(peer_id)
                author = data.get("username", "?")
                text = data.get("text", "")
                timestamp = data.get("timestamp")

                self._remember_chat(key, author, text, timestamp, "dm")

                # If this DM conversation is currently open, display it
                if self.chat_mode == "dm" and self.dm_target and self.dm_target.get("id") == peer_id:
                    print(f"Displaying in current DM view")
                    self._append_chat_line(author, text, timestamp, "dm")

            return

    def _active_history_key(self) -> str:
        if self.chat_mode == "dm" and self.dm_target:
            return f"dm:{self.dm_target['id']}"
        return "general"

    @staticmethod
    def _dm_history_key(peer_id: str) -> str:
        return f"dm:{peer_id}"

    def _remember_chat(self, key: str, author: str, text: str, timestamp: str | None, tag: str) -> None:
        self._histories.setdefault(key, []).append({
            "kind": "chat", "author": author, "text": text, "timestamp": timestamp, "tag": tag,
        })

    def _remember_system(self, key: str, text: str) -> None:
        self._histories.setdefault(key, []).append({"kind": "system", "text": text})

    def _show_chat_entry(self, key: str, author: str, text: str, timestamp: str | None, tag: str) -> None:
        self._remember_chat(key, author, text, timestamp, tag)
        if self._active_history_key() == key:
            self._append_chat_line(author, text, timestamp, tag)

    def _show_system_entry(self, key: str, text: str) -> None:
        self._remember_system(key, text)
        if self._active_history_key() == key:
            self._append_line(text + "\n", "system")

    def _reload_history_view(self, key: str, *, empty_dm_hint: str = "") -> None:
        self.messages_box.configure(state="normal")
        self.messages_box.delete("1.0", "end")
        for entry in self._histories.get(key, []):
            if entry["kind"] == "system":
                self.messages_box.insert("end", entry["text"] + "\n", "system")
            else:
                t = self._format_time(entry.get("timestamp"))
                self.messages_box.insert("end", f"[{t}] ", "meta")
                self.messages_box.insert("end", f"{entry['author']}: ", entry.get("tag", "other"))
                self.messages_box.insert("end", entry["text"] + "\n", entry.get("tag", "other"))
        if not self._histories.get(key):
            if key == "general":
                self._append_line("Общий чат — пишите и общайтесь во время викторины.\n", "system")
            elif empty_dm_hint:
                self._append_line(empty_dm_hint + "\n", "system")
        self.messages_box.see("end")
        self.messages_box.configure(state="disabled")

    def _format_time(self, ts: str | None) -> str:
        if not ts:
            return datetime.now().strftime("%H:%M")
        try:
            return datetime.fromisoformat(ts).strftime("%H:%M")
        except ValueError:
            return ""

    def _append_line(self, text: str, tag: str) -> None:
        self.messages_box.configure(state="normal")
        self.messages_box.insert("end", text, tag)
        self.messages_box.see("end")
        self.messages_box.configure(state="disabled")

    def _append_chat_line(self, author: str, text: str, timestamp: str | None, tag: str) -> None:
        t = self._format_time(timestamp)
        self.messages_box.configure(state="normal")
        self.messages_box.insert("end", f"[{t}] ", "meta")
        self.messages_box.insert("end", f"{author}: ", tag)
        self.messages_box.insert("end", f"{text}\n", tag)
        self.messages_box.see("end")
        self.messages_box.configure(state="disabled")

    def _refresh_users(self) -> None:
        """Refresh the users list (online users only)."""
        # Clear existing widgets
        for w in self.users_box.winfo_children():
            w.destroy()

        if not self.users:
            ctk.CTkLabel(
                self.users_box,
                text="Нет пользователей онлайн",
                font=ctk.CTkFont(size=12),
                text_color=COLORS["muted"],
            ).pack(pady=20)
            return

        for u in self.users:
            uid = u.get("id", "")
            name = u.get("username", "?")

            if not uid:
                continue

            label = f"🟢 {name}" + (" (вы)" if uid == self.user_id else "")

            btn = ctk.CTkButton(
                self.users_box,
                text=label,
                anchor="w",
                height=35,
                fg_color=COLORS["accent_soft"] if uid == self.user_id else "transparent",
                text_color=COLORS["accent"] if uid == self.user_id else COLORS["text"],
                hover_color=COLORS["border"],
            )
            def on_right_click(event, uid=uid, name=name):
                event.widget.configure(state="disabled")
                self.after(10, lambda: event.widget.configure(state="normal"))
                self._open_user_profile({"id": uid, "username": name})
            
            btn.configure(command=lambda uid=uid, name=name: self._open_dm({"id": uid, "username": name}))
            btn.bind("<Button-3>", on_right_click)
            btn.pack(fill="x", pady=2)

    def _open_general(self) -> None:
        self.chat_mode = "general"
        self.dm_target = None
        self.header_title.configure(text="📢 Общий чат")
        self.general_chat_btn.pack_forget()  # Hide button when in general chat
        self._reload_history_view("general")

    def _open_dm(self, user: dict[str, str]) -> None:
        print(f"Opening DM with user: {user}")
        print(f"Current user_id: {self.user_id}")

        if user.get("id") == self.user_id:
            print("Cannot open DM with self")
            return

        self.chat_mode = "dm"
        self.dm_target = user
        self.header_title.configure(text=f"💬 Личный чат: {user.get('username')}")
        self.general_chat_btn.pack(side="right", padx=(0, 6), pady=10)  # Show button when in DM

        print(f"Chat mode set to: {self.chat_mode}")
        print(f"DM target: {self.dm_target}")

        key = self._dm_history_key(user["id"])
        self._reload_history_view(
            key,
            empty_dm_hint=f"Личные сообщения с {user.get('username')}. Новые сообщения появятся здесь.",
        )
        if self._connected:
            self._conn.send({"type": "load_dm", "toUserId": user["id"]})

    def _apply_server_history(self, data: dict[str, Any]) -> None:
        channel = data.get("channel", "general")
        key = channel if channel == "general" else channel
        entries = []
        for m in data.get("messages") or []:
            is_own = m.get("userId") == self.user_id
            entries.append({
                "kind": "chat",
                "author": "Вы" if is_own else m.get("username", "?"),
                "text": m.get("text", ""),
                "timestamp": m.get("timestamp"),
                "tag": "own" if is_own else ("other" if key == "general" else "dm"),
            })
        if entries:
            self._histories[key] = entries
        if self._active_history_key() == key:
            self._reload_history_view(key)

    def _quiz_start(self) -> None:
        if not self._connected:
            messagebox.showwarning("Викторина", "Сначала войдите в чат")
            return

        # Get online users excluding self
        others = [u for u in self.users if u.get("id") != self.user_id]
        online_count = len(self.users)  # total including self

        if online_count < 2:
            messagebox.showinfo(
                "Викторина",
                f"Нужно минимум 2 игрока онлайн.\nСейчас онлайн: {online_count}\n\n"
                "Откройте второй клиент (python main.py) с другим логином.",
            )
            return

        # Destroy old quiz window if it exists
        if self.quiz_window is not None:
            try:
                if self.quiz_window.winfo_exists():
                    self.quiz_window.destroy()
            except (tk.TclError, AttributeError):
                pass
            self.quiz_window = None

        # Create new quiz window
        self.quiz_window = QuizWindow(
            self,
            on_answer=self._quiz_answer,
            on_send_message=self._send_from_quiz
        )

        self.quiz_window.open_waiting(f"Запрос на сервер… (онлайн: {online_count})")
        self._conn.send({"type": "quiz_start"})

    def _quiz_answer(self, index: int) -> None:
        if not self._connected:
            return
        
        if index == -3:
            # Выход из викторины - обнуление баллов
            self._conn.send({"type": "quiz_exit"})
        else:
            self._conn.send({"type": "quiz_answer", "answerIndex": index})

    def _open_profile(self) -> None:
        # Use `user_id` to determine whether the user is logged in.
        # `self.profile` may be empty in some edge cases, so provide
        # a sensible fallback for display.
        if not self.user_id:
            messagebox.showinfo("Профиль", "Войдите в аккаунт")
            return
        profile = self.profile or {
            "username": self.account or self.username or "?",
            "displayName": self.username or self.account or "?",
            "bio": "",
            "quizGames": 0,
            "quizWins": 0,
            "quizPoints": 0,
        }
        ProfileDialog(self, profile, on_save=self._save_profile)

    def _save_profile(self, display_name: str, bio: str) -> None:
        if self._connected:
            self._conn.send({"type": "profile_update", "displayName": display_name, "bio": bio})

    def _on_enter(self, event: tk.Event) -> str | None:
        if event.state & 0x1:
            return None
        self._send_message()
        return "break"

    def _send_message(self) -> None:
        if not self._connected:
            messagebox.showwarning("Чат", "Нет подключения")
            return

        text = self.input_field.get("1.0", "end").strip()
        if not text:
            return

        print(f"=== SENDING MESSAGE ===")
        print(f"Chat mode: {self.chat_mode}")
        print(f"DM target: {self.dm_target}")

        if self.chat_mode == "dm":
            if not self.dm_target:
                messagebox.showwarning("Чат", "Ошибка: получатель не выбран. Нажмите на пользователя в списке.")
                return

            print(f"Sending DM to {self.dm_target['id']}: {text}")

            # Add to local history immediately (optimistic)
            key = self._dm_history_key(self.dm_target["id"])
            self._show_chat_entry(key, "Вы", text, None, "own")

            # Send to server
            self._conn.send({"type": "dm", "toUserId": self.dm_target["id"], "text": text})
        else:
            print(f"Sending general message: {text}")

            # Add to local history
            self._show_chat_entry("general", "Вы", text, None, "own")

            # Send to server
            self._conn.send({"type": "message", "text": text})

        self.input_field.delete("1.0", "end")
        print(f"=== MESSAGE SENT ===")

    def _send_from_quiz(self, text: str) -> None:
        """Send message from quiz window to general chat."""
        if not self._connected:
            return

        # Add to local history
        self._show_chat_entry("general", "Вы", text, None, "own")

        # Send to server
        self._conn.send({"type": "message", "text": text})

        # Also add to quiz window if it exists
        if self.quiz_window and hasattr(self.quiz_window, 'add_chat_message'):
            self.quiz_window.add_chat_message(self.username, text, is_own=True)

    def _open_user_profile(self, user: dict[str, str]) -> None:
        """Open profile of another user."""
        if user.get("id") == self.user_id:
            self._open_profile()
            return

        print(f"Opening user profile for: {user}")  # Debug
        # Request user profile from server with both id and username
        self._conn.send({
            "type": "get_user_profile",
            "user_id": user["id"],
            "username": user["username"],
            "requested_by": self.user_id
        })

    def _show_user_profile(self, profile: dict[str, Any], requested_user_id: str = None,
                           requested_username: str = None) -> None:
        """Show profile of another user with add friend button."""
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Профиль: {profile.get('displayName', '?')}")
        dialog.geometry("450x650")
        dialog.configure(fg_color=COLORS["bg"])
        dialog.transient(self)

        # Main container with scroll
        main_container = ctk.CTkScrollableFrame(dialog, fg_color=COLORS["bg"])
        main_container.pack(fill="both", expand=True, padx=20, pady=20)

        card = ctk.CTkFrame(main_container, fg_color=COLORS["panel"], corner_radius=16)
        card.pack(fill="both", expand=True, padx=10, pady=10)

        # Avatar
        uname = profile.get("username", "?")
        display_name = profile.get("displayName", uname)
        initials = (display_name[:2] or "?").upper()

        av = ctk.CTkLabel(
            card,
            text=initials,
            width=80,
            height=80,
            fg_color=COLORS["accent"],
            text_color="white",
            corner_radius=40,
            font=ctk.CTkFont(size=28, weight="bold"),
        )
        av.pack(pady=(25, 10))
        
        # Загружаем аватарку если есть
        if profile.get("has_avatar"):
            # Отправляем запрос на сервер для получения аватарки
            if self._connected:
                self._conn.send({
                    "type": "get_avatar",
                    "username": uname
                })

        ctk.CTkLabel(
            card,
            text=display_name,
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["text"],
        ).pack()

        ctk.CTkLabel(
            card,
            text=f"@{uname}",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["muted"],
        ).pack(pady=(2, 10))

        # Separator
        ctk.CTkFrame(card, height=1, fg_color=COLORS["border"]).pack(fill="x", padx=20, pady=10)

        # Bio
        bio = profile.get("bio", "")
        if bio:
            ctk.CTkLabel(
                card,
                text="📝 О себе",
                anchor="w",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=COLORS["accent"],
            ).pack(anchor="w", padx=25, pady=(10, 5))

            ctk.CTkLabel(
                card,
                text=bio,
                wraplength=350,
                justify="left",
                font=ctk.CTkFont(size=12),
                text_color=COLORS["text"],
            ).pack(anchor="w", padx=25, pady=(0, 10))

        # Statistics section
        stats_frame = ctk.CTkFrame(card, fg_color=COLORS["quiz_bg"], corner_radius=12)
        stats_frame.pack(fill="x", padx=25, pady=15)

        ctk.CTkLabel(
            stats_frame,
            text="📊 Статистика викторины",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["success"],
        ).pack(anchor="w", padx=15, pady=(12, 8))

        stats_grid = ctk.CTkFrame(stats_frame, fg_color="transparent")
        stats_grid.pack(fill="x", padx=15, pady=(0, 12))

        games = profile.get('quizGames', 0)
        wins = profile.get('quizWins', 0)
        points = profile.get('quizPoints', 0)
        avg = round(points / games, 1) if games > 0 else 0

        stats = [
            ("🏆 Игр сыграно:", games, COLORS["accent"]),
            ("🥇 Побед:", wins, COLORS["success"]),
            ("⭐ Всего баллов:", points, COLORS["warning"]),
            ("📈 Средний балл:", avg, COLORS["accent"]),
        ]

        for label, value, color in stats:
            row = ctk.CTkFrame(stats_grid, fg_color="transparent")
            row.pack(fill="x", pady=5)
            ctk.CTkLabel(row, text=label, width=120, anchor="w", font=ctk.CTkFont(size=12)).pack(side="left")
            ctk.CTkLabel(row, text=str(value), font=ctk.CTkFont(size=12, weight="bold"), text_color=color).pack(
                side="left")

        button_frame = ctk.CTkFrame(card, fg_color="transparent")
        button_frame.pack(pady=15)

        # Check if this is another user
        if requested_username and requested_username != self.account:
            # Check if already friends by username
            is_friend = False
            # Check in local friends list by username
            if hasattr(self, 'friends_list'):
                for f in self.friends_list:
                    if f.get('username') == requested_username:
                        is_friend = True
                        break

            print(f"Friend check for {requested_username}: is_friend={is_friend}")  # Debug

            if is_friend:
                # Show "Friends" button with remove option and quiz invite
                friend_btn = ctk.CTkButton(
                    button_frame,
                    text="👥 Ваш друг ",
                    width=180,
                    height=40,
                    fg_color=COLORS["success"],
                    hover_color="#047857",
                    font=ctk.CTkFont(size=13, weight="bold"),
                )
                friend_btn.pack(pady=(0, 5))

                def show_remove_menu():
                    menu = tk.Menu(dialog, tearoff=0)
                    menu.add_command(
                        label="❌ Удалить из друзей",
                        command=lambda fn=requested_username: self._confirm_remove_friend(fn, fn)
                    )
                    menu.post(dialog.winfo_pointerx(), dialog.winfo_pointery())

                friend_btn.configure(command=show_remove_menu)
                
                # Quiz invite button for friends
                quiz_invite_btn = ctk.CTkButton(
                    button_frame,
                    text="🎮 Пригласить в квиз",
                    width=180,
                    height=36,
                    fg_color=COLORS["accent"],
                    hover_color=COLORS["accent_hover"],
                    font=ctk.CTkFont(size=12),
                    command=lambda uid=requested_user_id, un=requested_username: self._send_quiz_invite(uid, un),
                )
                quiz_invite_btn.pack()
            else:
                # Show add friend button
                add_btn = ctk.CTkButton(
                    button_frame,
                    text="➕ Добавить в друзья",
                    width=180,
                    height=40,
                    fg_color=COLORS["success"],
                    hover_color="#047857",
                    font=ctk.CTkFont(size=13, weight="bold"),
                    command=lambda uid=requested_user_id, un=requested_username: self._send_friend_request(uid, un),
                )
                add_btn.pack()
        else:
            print(f"Skipping friend button: requested_user_id={requested_user_id}, self.user_id={self.user_id}")

        # Close button
        ctk.CTkButton(
            card,
            text="Закрыть",
            width=120,
            height=35,
            command=dialog.destroy,
        ).pack(pady=(0, 20))

    def _force_refresh_friends(self) -> None:
        """Force refresh friends list."""
        if self._connected:
            self._conn.send({"type": "get_friends"})

    def _send_friend_request(self, to_user_id: str, to_username: str) -> None:
        """Send friend request to user."""
        if self._connected:
            self._conn.send({
                "type": "friend_request",
                "to_user_id": to_user_id,
                "to_username": to_username,
            })
            messagebox.showinfo("Друзья", f"Заявка в друзья отправлена пользователю {to_username}")

    def _send_quiz_invite(self, target_id: str, target_username: str) -> None:
        """Пригласить друга в викторину."""
        if not self._connected:
            messagebox.showwarning("Викторина", "Нет подключения к серверу")
            return
        
        # Проверяем, не идет ли уже викторина
        if hasattr(self, 'quiz_window') and self.quiz_window and hasattr(self.quiz_window, 'winfo_exists') and self.quiz_window.winfo_exists():
            messagebox.showwarning("Викторина", "Викторина уже идет")
            return
        
        self._conn.send({
            "type": "quiz_invite",
            "target_id": target_id,
            "target_username": target_username,
        })
        messagebox.showinfo("Викторина", f"Приглашение отправлено пользователю {target_username}")

    def _logout(self) -> None:
        self._conn.disconnect(wait=True)
        self._connected = False
        self.user_id = None
        self.profile = {}
        self._histories.clear()

        # Destroy quiz window if it exists
        if self.quiz_window is not None:
            try:
                if self.quiz_window.winfo_exists():
                    self.quiz_window.destroy()
            except (tk.TclError, AttributeError):
                pass
            self.quiz_window = None

        self.messages_box.configure(state="normal")
        self.messages_box.delete("1.0", "end")
        self.messages_box.configure(state="disabled")
        self._show_login()
        self.login_status.configure(text="")

    def _on_close(self) -> None:
        self._conn.disconnect(wait=True)
        self.destroy()


def run() -> None:
    ChatApp().mainloop()
