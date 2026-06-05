"""Синхронная викторина: все участники отвечают → следующий вопрос."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, TYPE_CHECKING

from db.database import get_db

if TYPE_CHECKING:
    from server import ChatRoom, Client

log = logging.getLogger("quiz")


class QuizManager:
    def __init__(self, room: ChatRoom) -> None:
        self.room = room
        self.db = get_db()
        self.active = False
        self.waiting_lobby = False
        self.session_id: int | None = None
        self.questions: list[dict[str, Any]] = []
        self.index = 0
        self.player_ids: list[str] = []
        self.answered: set[str] = set()
        self._advance_lock = asyncio.Lock()
        self._ready_players: set[str] = set()
        self._lobby_task: asyncio.Task | None = None

    def state_payload(self) -> dict[str, Any]:
        if not self.active or not self.questions:
            return {"type": "quiz_state", "active": False}
        q = self.questions[self.index]
        players = self.db.get_session_players(self.session_id)  # type: ignore[arg-type]
        return {
            "type": "quiz_state",
            "active": True,
            "sessionId": self.session_id,
            "questionIndex": self.index,
            "totalQuestions": len(self.questions),
            "question": _public_question(q),
            "answeredUserIds": list(self.answered),
            "playerIds": self.player_ids,
            "scores": players,
        }

    async def start_lobby(self, requester_id: str) -> dict[str, Any] | None:
        """Start the waiting lobby for quiz."""
        if self.active:
            return {"type": "quiz_error", "text": "Викторина уже идёт"}

        if self.waiting_lobby:
            return {"type": "quiz_error", "text": "Лобби уже открыто. Дождитесь начала или отмените."}

        online_clients = list(self.room.clients.values())
        if len(online_clients) < 2:
            return {"type": "quiz_error", "text": f"Нужно минимум 2 участника онлайн. Сейчас: {len(online_clients)}"}

        self.waiting_lobby = True
        self._ready_players = set()

        # Broadcast lobby opened
        await self.room.broadcast({
            "type": "quiz_lobby_opened",
            "opened_by": requester_id,
        })

        # Start 10-second countdown
        self._lobby_task = asyncio.create_task(self._lobby_countdown())
        return None

    async def _lobby_countdown(self) -> None:
        """Countdown for lobby before quiz starts."""
        for i in range(10, 0, -1):
            if not self.waiting_lobby:
                return
            await self.room.broadcast({
                "type": "quiz_lobby_countdown",
                "seconds": i,
                "ready_count": len(self._ready_players),
                "total_online": len(self.room.clients),
            })
            await asyncio.sleep(1)

        # Start the quiz after countdown
        if self.waiting_lobby:
            await self._start_quiz()

    async def ready_for_quiz(self, client: Client) -> dict[str, Any] | None:
        """Mark a player as ready for the quiz."""
        if not self.waiting_lobby:
            return {"type": "quiz_error", "text": "Нет активного лобби. Нажмите 'Викторина' для создания."}

        self._ready_players.add(client.user_id)

        await self.room.broadcast({
            "type": "quiz_player_ready",
            "user_id": client.user_id,
            "username": client.username,
            "ready_count": len(self._ready_players),
            "total_online": len(self.room.clients),
        })
        return None

    async def cancel_lobby(self, client: Client) -> dict[str, Any] | None:
        """Cancel the waiting lobby."""
        if not self.waiting_lobby:
            return {"type": "quiz_error", "text": "Нет активного лобби"}

        self.waiting_lobby = False
        if self._lobby_task:
            self._lobby_task.cancel()

        await self.room.broadcast({
            "type": "quiz_lobby_cancelled",
            "cancelled_by": client.username,
        })
        return None

    async def _start_quiz(self) -> None:
        """Actually start the quiz after lobby."""
        if not self.waiting_lobby:
            return

        self.waiting_lobby = False

        # Get all online players (not just ready ones)
        online_clients = list(self.room.clients.values())

        if len(online_clients) < 2:
            await self.room.broadcast({
                "type": "quiz_error",
                "text": "Недостаточно игроков для старта викторины",
            })
            return

        # Получаем случайные вопросы (10 штук)
        total_questions = self.db.get_question_count()
        questions_to_use = min(10, total_questions)
        self.questions = self.db.get_random_questions(questions_to_use)
        
        if not self.questions:
            await self.room.broadcast({
                "type": "quiz_error",
                "text": "В базе нет вопросов",
            })
            return

        players = [(c.user_id, c.username) for c in online_clients]

        log.info(f"Starting quiz with {len(players)} players: {players}")

        self.session_id = self.db.create_quiz_session(players)
        self.player_ids = [p[0] for p in players]
        self.index = 0
        self.answered = set()
        self.active = True

        await self.room.broadcast({
            "type": "quiz_started",
            "sessionId": self.session_id,
            "totalQuestions": len(self.questions),
            "players": self.db.get_session_players(self.session_id),
        })

        await asyncio.sleep(0.5)

        try:
            await self._send_question()
        except Exception as e:
            self.active = False
            await self.room.broadcast({
                "type": "quiz_error",
                "text": f"Ошибка при отправке вопроса: {str(e)}",
            })

    async def start(self) -> dict[str, Any] | None:
        """Legacy start method - now use start_lobby."""
        return await self.start_lobby("")

    async def submit_answer(self, client: Client, answer_index: int) -> None:
        if not self.active or self.session_id is None:
            await client.websocket.send_json({
                "type": "quiz_error",
                "text": "Викторина не запущена",
            })
            return

        if client.user_id not in self.player_ids:
            await client.websocket.send_json({
                "type": "quiz_error",
                "text": "Вы не участвуете в текущей викторине",
            })
            return

        if client.user_id in self.answered:
            return

        if answer_index not in (-1, 0, 1, 2, 3):
            return

        q = self.questions[self.index]
        correct = answer_index == q["correctIndex"] if answer_index != -1 else False

        self.db.save_quiz_answer(
            self.session_id,
            q["id"],
            client.user_id,
            client.username,
            answer_index if answer_index != -1 else 0,
            correct,
        )
        self.answered.add(client.user_id)

        await self.room.broadcast({
            "type": "quiz_player_answered",
            "userId": client.user_id,
            "username": client.username,
            "answeredCount": len(self.answered),
            "totalPlayers": len(self.player_ids),
        })

        # Don't advance automatically - wait for timer
        # The timer in _question_timeout will advance the round

    async def _send_question(self) -> None:
        """Send question and start timeout timer."""
        q = self.questions[self.index]
        self.answered = set()
        await self.room.broadcast({
            "type": "quiz_question",
            "sessionId": self.session_id,
            "questionIndex": self.index,
            "totalQuestions": len(self.questions),
            "question": _public_question(q),
        })

        # Start timeout task for this question (20 seconds)
        asyncio.create_task(self._question_timeout())

    async def _question_timeout(self) -> None:
        """Auto-advance after 20 seconds regardless of answers."""
        await asyncio.sleep(20)  # 20 seconds for each question

        async with self._advance_lock:
            if self.active and self.index < len(self.questions):
                # Mark non-answered players as wrong
                for uid in self.player_ids:
                    if uid not in self.answered:
                        q = self.questions[self.index]
                        self.db.save_quiz_answer(
                            self.session_id,
                            q["id"],
                            uid,
                            self.room.username_for(uid) or "?",
                            -1,  # No answer
                            False,
                        )
                        self.answered.add(uid)

                # Broadcast timeout message
                await self.room.broadcast({
                    "type": "quiz_timeout",
                    "notAnswered": [uid for uid in self.player_ids if uid not in self.answered],
                })

                await self._finish_round()

    async def _finish_round(self) -> None:
        q = self.questions[self.index]
        players = self.db.get_session_players(self.session_id)  # type: ignore[arg-type]

        await self.room.broadcast({
            "type": "quiz_round_result",
            "questionIndex": self.index,
            "correctIndex": q["correctIndex"],
            "correctText": q["options"][q["correctIndex"]],
            "scores": players,
        })

        await asyncio.sleep(3)
        self.index += 1

        if self.index >= len(self.questions):
            await self._finish_quiz()
        else:
            await self._send_question()

    async def _finish_quiz(self) -> None:
        self.db.finish_session(self.session_id)  # type: ignore[arg-type]
        players = self.db.get_session_players(self.session_id)  # type: ignore[arg-type]
        winner = players[0] if players else None
        try:
            self.db.record_quiz_results(players)
        except Exception:
            pass

        await self.room.broadcast({
            "type": "quiz_finished",
            "scores": players,
            "winner": winner,
        })

        self.active = False
        self.session_id = None
        self.questions = []
        self.player_ids = []
        self.answered = set()
        self.waiting_lobby = False

    def player_left(self, user_id: str) -> None:
        """Handle a player leaving during an active quiz."""
        if not self.active:
            if self.waiting_lobby and user_id in self._ready_players:
                self._ready_players.remove(user_id)
            return

        if user_id in self.player_ids:
            try:
                self.player_ids.remove(user_id)
            except ValueError:
                pass


def _public_question(q: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": q["id"],
        "text": q["question"],
        "options": q["options"],
        "correctIndex": q.get("correctIndex"),
    }