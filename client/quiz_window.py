"""Отдельное окно викторины с встроенным чатом."""

from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from client.theme import COLORS


class QuizWindow(ctk.CTkToplevel):
    def __init__(self, master: Any, on_answer: Callable[[int], None], on_send_message: Callable[[str], None] = None) -> None:
        super().__init__(master)
        self.title("⚽ Викторина — футбол")
        self.geometry("1400x900")
        self.minsize(1200, 800)
        self.configure(fg_color=COLORS["bg"])
        self._on_answer = on_answer
        self._on_send_message = on_send_message
        self._answered = False
        self._buttons: list[ctk.CTkButton] = []
        self._timer_id = None
        self._time_left = 20
        self._quiz_active = True
        self._exited = False  # Флаг выхода из викторины

        self.transient(master)
        self.lift()
        self.focus_force()

        # Header
        header = ctk.CTkFrame(self, fg_color=COLORS["accent"], corner_radius=0, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="⚽ Футбольная викторина",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="white",
        ).pack(side="left", padx=25, pady=15)

        # Close button
        self.exit_btn = ctk.CTkButton(
            header,
            text="✕ Выйти",
            width=100,
            height=35,
            fg_color="#dc2626",
            hover_color="#b91c1c",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._close_window,
        )
        self.exit_btn.pack(side="right", padx=20, pady=15)

        # Main content area (left: quiz, right: chat)
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=15, pady=15)

        # Left side - Quiz area (65%)
        quiz_frame = ctk.CTkFrame(main_container, fg_color=COLORS["panel"], corner_radius=16)
        quiz_frame.pack(side="left", fill="both", expand=True, padx=(0, 8))

        # Timer display
        timer_frame = ctk.CTkFrame(quiz_frame, fg_color="transparent")
        timer_frame.pack(pady=(20, 5))

        self.timer_label = ctk.CTkLabel(
            timer_frame,
            text="⏱️ 20",
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color=COLORS["accent"],
        )
        self.timer_label.pack()

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            quiz_frame,
            width=400,
            height=10,
            corner_radius=5,
            fg_color=COLORS["border"],
            progress_color=COLORS["accent"],
        )
        self.progress_bar.pack(pady=(5, 15))
        self.progress_bar.set(1.0)

        # Question area
        self.status = ctk.CTkLabel(
            quiz_frame,
            text="",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["muted"],
        )
        self.status.pack(anchor="w", padx=25, pady=(10, 5))

        self.question = ctk.CTkLabel(
            quiz_frame,
            text="",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["text"],
            wraplength=550,
            justify="left",
        )
        self.question.pack(anchor="w", padx=25, pady=(0, 20))

        # Options area
        options_container = ctk.CTkScrollableFrame(quiz_frame, fg_color="transparent", height=300)
        options_container.pack(fill="both", expand=True, padx=15, pady=5)
        self.options = options_container

        # Right side - Chat area (35%)
        chat_frame = ctk.CTkFrame(main_container, fg_color=COLORS["panel"], corner_radius=16)
        chat_frame.pack(side="right", fill="both", expand=True, padx=(8, 0))

        ctk.CTkLabel(
            chat_frame,
            text="💬 Общий чат",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["accent"],
        ).pack(anchor="w", padx=15, pady=(15, 8))

        # Chat messages display
        self.chat_messages = ctk.CTkTextbox(
            chat_frame,
            fg_color=COLORS["input_bg"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=12),
            wrap="word",
        )
        self.chat_messages.pack(fill="both", expand=True, padx=12, pady=(5, 10))
        self.chat_messages.configure(state="disabled")

        # Chat input
        chat_input_frame = ctk.CTkFrame(chat_frame, fg_color="transparent")
        chat_input_frame.pack(fill="x", padx=12, pady=(0, 15))

        self.chat_entry = ctk.CTkEntry(
            chat_input_frame,
            placeholder_text="Напишите сообщение...",
            fg_color=COLORS["input_bg"],
            height=35,
        )
        self.chat_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.chat_entry.bind("<Return>", self._send_chat_message)

        self.send_btn = ctk.CTkButton(
            chat_input_frame,
            text="Отправить",
            width=90,
            height=35,
            fg_color=COLORS["accent"],
            command=self._send_chat_message,
        )
        self.send_btn.pack(side="right")

        # Bottom - Scores area
        scores_frame = ctk.CTkFrame(quiz_frame, fg_color="transparent")
        scores_frame.pack(fill="x", padx=20, pady=(15, 20))

        self.scores_label = ctk.CTkLabel(
            scores_frame,
            text="🏆 Текущий счёт",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["success"],
        )
        self.scores_label.pack(anchor="w")

        self.scores = ctk.CTkLabel(
            scores_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["muted"],
            justify="left",
        )
        self.scores.pack(anchor="w", pady=(8, 0))

    def _close_window(self) -> None:
        """Close the quiz window and notify server."""
        self._quiz_active = False
        self._exited = True
        self._stop_timer()
        # Отправляем на сервер что пользователь вышел из викторины (баллы = 0)
        self._on_answer(-3)  # Special code for exit
        self.destroy()

    def _send_chat_message(self, event=None) -> None:
        """Send chat message from quiz window."""
        text = self.chat_entry.get().strip()
        if text and self._on_send_message:
            self._on_send_message(text)
            self.chat_entry.delete(0, "end")

    def add_chat_message(self, username: str, text: str, is_own: bool = False) -> None:
        """Add a message to the chat display."""
        self.chat_messages.configure(state="normal")

        prefix = "Вы" if is_own else username

        self.chat_messages.insert("end", f"{prefix}: ")
        self.chat_messages.insert("end", f"{text}\n")

        self.chat_messages.see("end")
        self.chat_messages.configure(state="disabled")

    def _start_timer(self) -> None:
        """Start the 20-second timer for current question."""
        self._time_left = 20
        self._update_timer()

    def _update_timer(self) -> None:
        """Update timer display and handle timeout."""
        if self._time_left <= 0:
            if not self._answered and self._quiz_active:
                self._auto_timeout()
            return

        self.timer_label.configure(text=f"⏱️ {self._time_left}")

        # Update progress bar
        progress = self._time_left / 20
        self.progress_bar.set(progress)

        # Change color when time is low
        if self._time_left <= 5:
            self.timer_label.configure(text_color=COLORS["danger"])
            self.progress_bar.configure(progress_color=COLORS["danger"])
        elif self._time_left <= 10:
            self.timer_label.configure(text_color=COLORS["warning"])
            self.progress_bar.configure(progress_color=COLORS["warning"])
        else:
            self.timer_label.configure(text_color=COLORS["accent"])
            self.progress_bar.configure(progress_color=COLORS["accent"])

        self._time_left -= 1
        self._timer_id = self.after(1000, self._update_timer)

    def _auto_timeout(self) -> None:
        """Handle timeout when user doesn't answer."""
        self._answered = True
        if self._timer_id:
            self.after_cancel(self._timer_id)
            self._timer_id = None

        for btn in self._buttons:
            btn.configure(state="disabled")

        self.status.configure(
            text="⏰ Время вышло! Вы не успели ответить.",
            text_color=COLORS["danger"],
        )
        self._on_answer(-1)

    def _stop_timer(self) -> None:
        """Stop the current timer."""
        if self._timer_id:
            self.after_cancel(self._timer_id)
            self._timer_id = None

    def _clear_options(self) -> None:
        """Clear all option buttons."""
        for b in self._buttons:
            b.destroy()
        self._buttons.clear()

    def open_waiting(self, text: str = "Запуск викторины…") -> None:
        """Show waiting screen."""
        self._quiz_active = True
        self._answered = False
        self._stop_timer()
        self.deiconify()
        self.lift()
        self.focus_force()
        self.status.configure(text=text, text_color=COLORS["accent"])
        self.question.configure(text="Подождите, сервер готовит вопросы…")
        self._clear_options()
        self.scores.configure(text="")
        self.timer_label.configure(text="⏱️ --")
        self.progress_bar.set(0)
        self.exit_btn.configure(text="✕ Выйти", fg_color="#dc2626", command=self._close_window)

    def show_error(self, text: str) -> None:
        """Show error message."""
        self._stop_timer()
        self.deiconify()
        self.lift()
        self.status.configure(text=text, text_color=COLORS["danger"])
        self.question.configure(text="Викторина не запущена")
        self._clear_options()

    def show_question(self, data: dict[str, Any]) -> None:
        """Display a new question."""
        if not self._quiz_active:
            return

        self.deiconify()
        self.lift()
        self.focus_force()
        self._answered = False
        self._stop_timer()

        q = data.get("question") or {}
        idx = int(data.get("questionIndex", 0)) + 1
        total = data.get("totalQuestions", 10)

        self.status.configure(
            text=f"📋 Вопрос {idx} из {total}",
            text_color=COLORS["accent"],
        )
        self.question.configure(text=q.get("text", ""))
        self._clear_options()

        labels = ["A", "B", "C", "D"]
        for i, opt in enumerate(q.get("options") or []):
            btn = ctk.CTkButton(
                self.options,
                text=f"  {labels[i]}.  {opt}",
                height=50,
                anchor="w",
                fg_color=COLORS["input_bg"],
                hover_color=COLORS["accent_soft"],
                text_color=COLORS["text"],
                border_width=1,
                border_color=COLORS["border"],
                font=ctk.CTkFont(size=14),
                command=lambda ix=i: self._pick(ix),
            )
            btn.pack(fill="x", pady=6, padx=6)
            self._buttons.append(btn)

        # Start timer
        self._start_timer()

    def _pick(self, index: int) -> None:
        """Handle answer selection."""
        if self._answered or not self._quiz_active:
            return

        self._answered = True
        # Не останавливаем таймер - пусть продолжает идти до конца
        # self._stop_timer()

        for btn in self._buttons:
            btn.configure(state="disabled")

        self.status.configure(text="✓ Ответ отправлен. Ждём остальных…", text_color=COLORS["success"])
        self._on_answer(index)

    def set_waiting(self, answered: int, total: int) -> None:
        """Update waiting status."""
        if not self._answered and self._quiz_active:
            self.status.configure(
                text=f"⏳ Ответили {answered} из {total} участников",
                text_color=COLORS["warning"],
            )

    def show_round_result(self, data: dict[str, Any]) -> None:
        """Show round result."""
        if not self._quiz_active:
            return
        self._stop_timer()
        self._clear_options()
        self.status.configure(
            text=f"✅ Правильно: {data.get('correctText', '')}",
            text_color=COLORS["success"],
        )
        self.timer_label.configure(text="⏱️ --")
        self.progress_bar.set(0)
        self._show_scores(data.get("scores") or [])

    def show_finished(self, data: dict[str, Any]) -> None:
        """Show final results with nice formatting."""
        self._stop_timer()
        self._clear_options()

        scores = data.get("scores") or []
        winner = data.get("winner") or {}

        # Check for tie
        is_tie = False
        if len(scores) >= 2 and scores[0].get("score") == scores[1].get("score"):
            is_tie = True

        if is_tie:
            self.status.configure(
                text="🤝 НИЧЬЯ! 🤝",
                text_color=COLORS["warning"],
                font=ctk.CTkFont(size=20, weight="bold"),
            )
        elif winner:
            self.status.configure(
                text=f"🏆 ПОБЕДИТЕЛЬ: {winner.get('username')} — {winner.get('score')} очков 🏆",
                text_color=COLORS["success"],
                font=ctk.CTkFont(size=20, weight="bold"),
            )
        else:
            self.status.configure(text="✨ Викторина завершена ✨", text_color=COLORS["success"])

        self.question.configure(text="")
        self.timer_label.configure(text="🏁")
        self.progress_bar.set(1.0)
        self.progress_bar.configure(progress_color=COLORS["success"])

        # Change exit button to close window
        self.exit_btn.configure(text="✕ Закрыть", fg_color=COLORS["accent"], command=self._close_window)

        # Show final scores in a nice table
        self._show_final_results_table(scores)

    def _show_final_results_table(self, scores: list[dict[str, Any]]) -> None:
        """Display final results in a beautiful table."""
        if not scores:
            return

        # Create a frame for the results table
        results_frame = ctk.CTkFrame(self.options, fg_color=COLORS["panel_alt"], corner_radius=12)
        results_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Header
        header_frame = ctk.CTkFrame(results_frame, fg_color=COLORS["accent"], corner_radius=8)
        header_frame.pack(fill="x", padx=5, pady=(5, 2))

        ctk.CTkLabel(
            header_frame,
            text="Место",
            width=80,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="white",
        ).pack(side="left", padx=10, pady=8)

        ctk.CTkLabel(
            header_frame,
            text="Игрок",
            width=200,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="white",
        ).pack(side="left", padx=10, pady=8)

        ctk.CTkLabel(
            header_frame,
            text="Очки",
            width=100,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="white",
        ).pack(side="left", padx=10, pady=8)

        # Rows
        medals = ["🥇", "🥈", "🥉"]
        for i, s in enumerate(scores):
            row_frame = ctk.CTkFrame(results_frame, fg_color="transparent", corner_radius=6)
            row_frame.pack(fill="x", padx=5, pady=2)

            # Alternate row colors
            if i % 2 == 0:
                row_frame.configure(fg_color=COLORS["input_bg"])

            medal_text = medals[i] if i < 3 else f"{i+1}."
            ctk.CTkLabel(
                row_frame,
                text=medal_text,
                width=80,
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=COLORS["accent"] if i < 3 else COLORS["muted"],
            ).pack(side="left", padx=10, pady=8)

            ctk.CTkLabel(
                row_frame,
                text=s.get('username', '?'),
                width=200,
                font=ctk.CTkFont(size=13),
                text_color=COLORS["text"],
                anchor="w",
            ).pack(side="left", padx=10, pady=8)

            score_color = COLORS["success"] if i == 0 else COLORS["text"]
            ctk.CTkLabel(
                row_frame,
                text=str(s.get('score', 0)),
                width=100,
                font=ctk.CTkFont(size=13, weight="bold" if i == 0 else "normal"),
                text_color=score_color,
            ).pack(side="left", padx=10, pady=8)

    def apply_state(self, data: dict[str, Any], user_id: str | None) -> None:
        """Apply quiz state when reconnecting."""
        self.show_question(data)
        answered = set(data.get("answeredUserIds") or [])
        if user_id and user_id in answered:
            self._answered = True
            self._stop_timer()
            for btn in self._buttons:
                btn.configure(state="disabled")
            self.status.configure(text="Вы уже ответили на этот вопрос", text_color=COLORS["success"])
        else:
            self._start_timer()

        self.set_waiting(len(answered), len(data.get("playerIds") or []))
        self._show_scores(data.get("scores") or [])

    def _show_scores(self, scores: list[dict[str, Any]], final: bool = False) -> None:
        """Display scores with nice formatting."""
        if not scores:
            self.scores.configure(text="")
            return

        lines = [f"{i+1}. {s.get('username')}: {s.get('score', 0)}" for i, s in enumerate(scores[:5])]
        self.scores.configure(text="\n".join(lines))

    def show_lobby(self, ready_count: int, total_online: int, countdown: int = None) -> None:
        """Show waiting lobby."""
        self.deiconify()
        self.lift()
        self.focus_force()

        if countdown and countdown > 0:
            self.status.configure(
                text=f"⏰ Старт через {countdown} секунд...",
                text_color=COLORS["warning"],
            )
        else:
            self.status.configure(
                text=f"🎮 Лобби викторины\nГотовы: {ready_count} из {total_online} игроков\n\nНажмите «Готов» для участия",
                text_color=COLORS["accent"],
            )

        self.question.configure(text="Ожидание игроков...")
        self._clear_options()

        # Show ready button
        if not hasattr(self, 'ready_btn'):
            self.ready_btn = ctk.CTkButton(
                self.options,
                text="✅ Я готов!",
                height=50,
                font=ctk.CTkFont(size=16, weight="bold"),
                fg_color=COLORS["success"],
                hover_color="#047857",
                command=self._send_ready,
            )
            self.ready_btn.pack(pady=20)

        self.timer_label.configure(text="🎮")
        self.progress_bar.set(0)

    def _send_ready(self) -> None:
        """Send ready signal to server."""
        if hasattr(self, 'ready_btn'):
            self.ready_btn.configure(text="✓ Готов!", state="disabled", fg_color=COLORS["muted"])
        self._on_answer(-2)  # Special code for ready

    def hide_lobby(self) -> None:
        """Hide lobby UI."""
        if hasattr(self, 'ready_btn'):
            self.ready_btn.destroy()
            delattr(self, 'ready_btn')