"""Панель викторины в десктопном клиенте."""

from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

COLORS = {
    "panel": "#18181f",
    "accent": "#6366f1",
    "success": "#22c55e",
    "warning": "#eab308",
    "muted": "#a1a1aa",
    "quiz_bg": "#1a2e1a",
}


class QuizPanel(ctk.CTkFrame):
    def __init__(
        self,
        master: Any,
        on_start: Callable[[], None],
        on_answer: Callable[[int], None],
    ) -> None:
        super().__init__(master, fg_color=COLORS["quiz_bg"], corner_radius=8)
        self._on_start = on_start
        self._on_answer = on_answer
        self._answered = False
        self._option_buttons: list[ctk.CTkButton] = []

        ctk.CTkLabel(
            self, text="⚽ Викторина: футбол", font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 4))

        self.status_label = ctk.CTkLabel(
            self, text="Нажмите «Старт» (мин. 2 игрока)", font=ctk.CTkFont(size=11),
            text_color=COLORS["muted"], wraplength=170, justify="left",
        )
        self.status_label.pack(anchor="w", padx=10, pady=4)

        self.start_btn = ctk.CTkButton(
            self, text="Старт викторины", height=30, command=self._on_start,
            fg_color=COLORS["accent"],
        )
        self.start_btn.pack(fill="x", padx=10, pady=6)

        self.question_label = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=12), wraplength=170, justify="left",
        )
        self.question_label.pack(anchor="w", padx=10, pady=(8, 4))

        self.options_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.options_frame.pack(fill="x", padx=8, pady=4)

        self.score_label = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=11), text_color=COLORS["muted"],
            wraplength=170, justify="left",
        )
        self.score_label.pack(anchor="w", padx=10, pady=(4, 10))

        self._clear_options()

    def _clear_options(self) -> None:
        for b in self._option_buttons:
            b.destroy()
        self._option_buttons.clear()

    def set_idle(self) -> None:
        self._answered = False
        self.start_btn.configure(state="normal")
        self.status_label.configure(text="Нажмите «Старт» (мин. 2 игрока)")
        self.question_label.configure(text="")
        self.score_label.configure(text="")
        self._clear_options()

    def set_waiting_players(self, answered: int, total: int) -> None:
        self.status_label.configure(
            text=f"Ответили: {answered} / {total}",
            text_color=COLORS["warning"],
        )

    def show_question(self, data: dict[str, Any]) -> None:
        self._answered = False
        self.start_btn.configure(state="disabled")
        q = data.get("question") or {}
        idx = data.get("questionIndex", 0) + 1
        total = data.get("totalQuestions", "?")
        self.status_label.configure(
            text=f"Вопрос {idx} / {total}",
            text_color=COLORS["accent"],
        )
        self.question_label.configure(text=q.get("text", ""))
        self._clear_options()
        labels = ["A", "B", "C", "D"]
        for i, opt in enumerate(q.get("options") or []):
            btn = ctk.CTkButton(
                self.options_frame,
                text=f"{labels[i]}) {opt}",
                height=28,
                anchor="w",
                fg_color="#27272f",
                command=lambda ix=i: self._pick(ix),
            )
            btn.pack(fill="x", pady=2)
            self._option_buttons.append(btn)

    def _pick(self, index: int) -> None:
        if self._answered:
            return
        self._answered = True
        for b in self._option_buttons:
            b.configure(state="disabled")
        self.status_label.configure(text="Ответ отправлен, ждём других…")
        self._on_answer(index)

    def show_round_result(self, data: dict[str, Any]) -> None:
        correct = data.get("correctText", "")
        self.status_label.configure(text=f"Верно: {correct}", text_color=COLORS["success"])
        self._clear_options()
        self._show_scores(data.get("scores") or [])

    def show_finished(self, data: dict[str, Any]) -> None:
        scores = data.get("scores") or []
        winner = data.get("winner")
        if winner:
            self.status_label.configure(
                text=f"🏆 Победитель: {winner.get('username')} ({winner.get('score')} б.)",
                text_color=COLORS["success"],
            )
        else:
            self.status_label.configure(text="Викторина завершена")
        self.question_label.configure(text="")
        self._clear_options()
        self.start_btn.configure(state="normal")
        self._show_scores(scores)

    def show_error(self, text: str) -> None:
        self.status_label.configure(text=text, text_color="#f87171")

    def apply_state(self, data: dict[str, Any], user_id: str | None) -> None:
        if not data.get("active"):
            return
        self.show_question(data)
        answered = set(data.get("answeredUserIds") or [])
        if user_id and user_id in answered:
            self._answered = True
            for b in self._option_buttons:
                b.configure(state="disabled")
        self.set_waiting_players(len(answered), len(data.get("playerIds") or []))
        self._show_scores(data.get("scores") or [])

    def _show_scores(self, scores: list[dict[str, Any]]) -> None:
        if not scores:
            self.score_label.configure(text="")
            return
        lines = [f"{s.get('username')}: {s.get('score', 0)}" for s in scores[:6]]
        self.score_label.configure(text="Счёт:\n" + "\n".join(lines))

    def set_user_id(self, user_id: str | None) -> None:
        self._user_id = user_id
