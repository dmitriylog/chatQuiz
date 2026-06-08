"""SQLite: сообщения и вопросы викторины."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from db.auth import hash_password, verify_password

# Пытаемся импортировать шифрование, но делаем его опциональным
try:
    from db.encryption import encrypt_message, decrypt_message
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False
    def encrypt_message(msg): return msg
    def decrypt_message(msg): return msg

DB_PATH = Path(os.environ.get("CHAT_DB", Path(__file__).parent.parent / "data" / "chat.db"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def dm_channel(username_a: str, username_b: str) -> str:
    a, b = sorted([username_a.strip().lower(), username_b.strip().lower()])
    return f"dm:{a}|{b}"


FOOTBALL_QUESTIONS: list[dict[str, Any]] = [
    {
        "question": "Сколько игроков одной команды на поле в классическом футболе?",
        "options": ["9", "10", "11", "12"],
        "correct_index": 2,
    },
    {
        "question": "Какая страна выиграла чемпионат мира FIFA 2018?",
        "options": ["Бразилия", "Хорватия", "Франция", "Германия"],
        "correct_index": 2,
    },
    {
        "question": "Как называется главный международный турнир сборных в Европе?",
        "options": ["Лига чемпионов", "Чемпионат Европы", "Кубок Америки", "Суперкубок UEFA"],
        "correct_index": 1,
    },
    {
        "question": "Сколько минут длится основное время матча (без добавленного)?",
        "options": ["80", "90", "100", "120"],
        "correct_index": 1,
    },
    {
        "question": "Какой игрок чаще всего называют «CR7»?",
        "options": ["Кака", "Криштиану Роналду", "Касильяс", "Коэнтрао"],
        "correct_index": 1,
    },
    {
        "question": "Какой клуб играет дома на «Камп Ноу»?",
        "options": ["Реал Мадрид", "Барселона", "Атлетико", "Севилья"],
        "correct_index": 1,
    },
    {
        "question": "Как называется судья, который следит за игрой на поле?",
        "options": ["Линейный", "Главный арбитр", "Делегат", "Инспектор"],
        "correct_index": 1,
    },
    {
        "question": "За что назначается одиннадцатиметровый удар?",
        "options": ["Удар с угла", "Грубый фол в штрафной", "Офсайд", "Аут"],
        "correct_index": 1,
    },
    {
        "question": "Какой трофей вручают победителю Лиги чемпионов UEFA?",
        "options": ["Кубок мира", "Большой кубок", "Золотая бутса", "Серебряный мяч"],
        "correct_index": 1,
    },
    {
        "question": "Сколько замен разрешено в официальном матче FIFA (стандарт)?",
        "options": ["3", "5", "7", "Неограниченно"],
        "correct_index": 1,
    },
]


class Database:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT NOT NULL,
                    sender_user_id TEXT NOT NULL,
                    sender_username TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel, id);

                CREATE TABLE IF NOT EXISTS quiz_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    option_a TEXT NOT NULL,
                    option_b TEXT NOT NULL,
                    option_c TEXT NOT NULL,
                    option_d TEXT NOT NULL,
                    correct_index INTEGER NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS quiz_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    status TEXT NOT NULL,
                    current_index INTEGER NOT NULL DEFAULT 0,
                    started_at TEXT NOT NULL,
                    finished_at TEXT
                );

                CREATE TABLE IF NOT EXISTS quiz_players (
                    session_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    score INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (session_id, user_id)
                );

                CREATE TABLE IF NOT EXISTS quiz_answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    question_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    answer_index INTEGER NOT NULL,
                    is_correct INTEGER NOT NULL,
                    answered_at TEXT NOT NULL,
                    UNIQUE(session_id, question_id, user_id)
                );
                
                CREATE TABLE IF NOT EXISTS friends (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,          -- Имя пользователя (отправитель)
                    friend_id TEXT NOT NULL,        -- Имя пользователя (получатель)
                    friend_username TEXT,           -- Поле обратной совместимости
                    status TEXT NOT NULL,           -- 'pending', 'accepted', 'rejected'
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    UNIQUE(user_id, friend_id)
                );
                CREATE INDEX IF NOT EXISTS idx_friends_user ON friends(user_id);
                CREATE INDEX IF NOT EXISTS idx_friends_friend ON friends(friend_id);

                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    bio TEXT NOT NULL DEFAULT '',
                    quiz_wins INTEGER NOT NULL DEFAULT 0,
                    quiz_games INTEGER NOT NULL DEFAULT 0,
                    quiz_points INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    avatar_data BLOB
                );
                """
            )
            # На всякий случай обрабатываем миграцию для старых БД
            try:
                conn.execute("ALTER TABLE friends ADD COLUMN friend_username TEXT")
            except sqlite3.OperationalError:
                pass

            # Добавляем поле avatar_data если его нет
            try:
                conn.execute("ALTER TABLE users ADD COLUMN avatar_data BLOB")
            except sqlite3.OperationalError:
                pass

            count = conn.execute("SELECT COUNT(*) FROM quiz_questions").fetchone()[0]
            if count == 0:
                for i, q in enumerate(FOOTBALL_QUESTIONS):
                    opts = q["options"]
                    conn.execute(
                        """
                        INSERT INTO quiz_questions
                        (question, option_a, option_b, option_c, option_d, correct_index, sort_order)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (q["question"], opts[0], opts[1], opts[2], opts[3], q["correct_index"], i),
                    )
            conn.commit()

    def save_message(
        self,
        channel: str,
        sender_user_id: str,
        sender_username: str,
        body: str,
        encrypt: bool = False,
    ) -> int:
        """Сохранить сообщение. Если encrypt=True - зашифровать тело сообщения."""
        message_body = encrypt_message(body) if encrypt else body
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO messages (channel, sender_user_id, sender_username, body, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (channel, sender_user_id, sender_username, message_body, _now()),
            )
            conn.commit()
            return int(cur.lastrowid)

    def get_channel_history(self, channel: str, limit: int = 200, decrypt: bool = False) -> list[dict[str, Any]]:
        """Получить историю канала. Если decrypt=True - расшифровать сообщения."""
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT sender_user_id, sender_username, body, created_at
                FROM messages WHERE channel = ? ORDER BY id DESC LIMIT ?
                """,
                (channel, limit),
            ).fetchall()
        rows = list(reversed(rows))
        result = []
        for r in rows:
            text = r["body"]
            if decrypt:
                try:
                    text = decrypt_message(text)
                except Exception:
                    # Если расшифровка не удалась, оставляем как есть
                    pass
            result.append({
                "userId": r["sender_user_id"],
                "username": r["sender_username"],
                "text": text,
                "timestamp": r["created_at"],
            })
        return result

    def list_questions(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, question, option_a, option_b, option_c, option_d, correct_index
                FROM quiz_questions ORDER BY sort_order, id
                """
            ).fetchall()
        return [_question_row(r) for r in rows]

    def get_random_questions(self, count: int = 10) -> list[dict[str, Any]]:
        """Получить случайные вопросы из базы данных (без повторений)."""
        import random
        
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, question, option_a, option_b, option_c, option_d, correct_index
                FROM quiz_questions ORDER BY RANDOM() LIMIT ?
                """,
                (count,)
            ).fetchall()
        
        questions = [_question_row(r) for r in rows]
        # Перемешиваем еще раз для большей случайности
        random.shuffle(questions)
        return questions

    def get_question(self, question_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM quiz_questions WHERE id = ?", (question_id,)
            ).fetchone()
        return _question_row(row) if row else None

    def add_question(self, question: str, options: list[str], correct_index: int) -> int:
        """Добавить новый вопрос в базу данных."""
        if len(options) != 4:
            raise ValueError("Должно быть ровно 4 варианта ответа")
        if not (0 <= correct_index <= 3):
            raise ValueError("Индекс правильного ответа должен быть от 0 до 3")
        
        with self.connect() as conn:
            # Получаем максимальный sort_order
            max_order = conn.execute(
                "SELECT MAX(sort_order) FROM quiz_questions"
            ).fetchone()[0] or 0
            
            cur = conn.execute(
                """
                INSERT INTO quiz_questions 
                (question, option_a, option_b, option_c, option_d, correct_index, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (question, options[0], options[1], options[2], options[3], correct_index, max_order + 1)
            )
            conn.commit()
            return int(cur.lastrowid)

    def delete_question(self, question_id: int) -> bool:
        """Удалить вопрос из базы данных."""
        with self.connect() as conn:
            conn.execute("DELETE FROM quiz_questions WHERE id = ?", (question_id,))
            conn.commit()
            return conn.total_changes > 0

    def get_question_count(self) -> int:
        """Получить общее количество вопросов в базе."""
        with self.connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM quiz_questions").fetchone()[0]

    def create_quiz_session(self, players: list[tuple[str, str]]) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO quiz_sessions (status, current_index, started_at)
                VALUES ('active', 0, ?)
                """,
                (_now(),),
            )
            session_id = int(cur.lastrowid)
            for uid, uname in players:
                conn.execute(
                    """
                    INSERT INTO quiz_players (session_id, user_id, username, score)
                    VALUES (?, ?, ?, 0)
                    """,
                    (session_id, uid, uname),
                )
            conn.commit()
        return session_id

    def finish_session(self, session_id: int) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE quiz_sessions SET status = 'finished', finished_at = ? WHERE id = ?
                """,
                (_now(), session_id),
            )
            conn.commit()

    def get_session_players(self, session_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT user_id, username, score FROM quiz_players
                WHERE session_id = ? ORDER BY score DESC, username
                """,
                (session_id,),
            ).fetchall()
        return [
            {"userId": r["user_id"], "username": r["username"], "score": r["score"]}
            for r in rows
        ]

    def save_quiz_answer(
        self,
        session_id: int,
        question_id: int,
        user_id: str,
        username: str,
        answer_index: int,
        is_correct: bool,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO quiz_answers
                (session_id, question_id, user_id, username, answer_index, is_correct, answered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, question_id, user_id, username, answer_index, int(is_correct), _now()),
            )
            if is_correct:
                conn.execute(
                    """
                    UPDATE quiz_players SET score = score + 1
                    WHERE session_id = ? AND user_id = ?
                    """,
                    (session_id, user_id),
                )
            conn.commit()

    def has_answered(self, session_id: int, question_id: int, user_id: str) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM quiz_answers
                WHERE session_id = ? AND question_id = ? AND user_id = ?
                """,
                (session_id, question_id, user_id),
            ).fetchone()
        return row is not None

    def send_friend_request(self, from_user_id: str, from_username: str, to_user_id: str, to_username: str) -> tuple[bool, str]:
        """Отправка запроса в друзья на основе username."""
        f_user = from_username.strip().lower()
        t_user = to_username.strip().lower()
        if f_user == t_user:
            return False, "Нельзя добавить самого себя"

        try:
            with self.connect() as conn:
                existing = conn.execute(
                    """
                    SELECT status FROM friends 
                    WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)
                    """,
                    (from_username, to_username, to_username, from_username)
                ).fetchone()

                if existing:
                    if existing['status'] == 'pending':
                        return False, "Заявка уже отправлена"
                    elif existing['status'] == 'accepted':
                        return False, "Вы уже друзья"

                conn.execute(
                    """
                    INSERT INTO friends (user_id, friend_id, friend_username, status, created_at)
                    VALUES (?, ?, ?, 'pending', ?)
                    """,
                    (from_username, to_username, to_username, _now())
                )
                conn.commit()
            return True, "Заявка отправлена"
        except sqlite3.IntegrityError:
            return False, "Заявка уже была отправлена"

    def accept_friend_request(self, current_username: str, from_username: str) -> bool:
        """Принять запрос (создает двустороннюю подтвержденную связь)."""
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE friends SET status = 'accepted', updated_at = ?
                WHERE user_id = ? AND friend_id = ? AND status = 'pending'
                """,
                (_now(), from_username, current_username)
            )

            # Проверяем и создаем зеркальную запись для взаимности
            reverse = conn.execute(
                """
                SELECT 1 FROM friends WHERE user_id = ? AND friend_id = ?
                """,
                (current_username, from_username)
            ).fetchone()

            if not reverse:
                conn.execute(
                    """
                    INSERT INTO friends (user_id, friend_id, friend_username, status, created_at)
                    VALUES (?, ?, ?, 'accepted', ?)
                    """,
                    (current_username, from_username, from_username, _now())
                )
            conn.commit()
        return True

    def reject_friend_request(self, current_username: str, from_username: str) -> bool:
        """Отклонить входящий запрос."""
        with self.connect() as conn:
            conn.execute(
                """
                DELETE FROM friends
                WHERE user_id = ? AND friend_id = ? AND status = 'pending'
                """,
                (from_username, current_username)
            )
            conn.commit()
        return True

    def get_friends(self, username: str) -> list[dict[str, Any]]:
        """Получить список друзей (исправлен JOIN по u.username вместо несуществующего u.user_id)."""
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT f.friend_id AS user_id, u.username, u.display_name, u.bio, 
                       u.quiz_wins, u.quiz_games, u.quiz_points
                FROM friends f
                JOIN users u ON u.username = f.friend_id
                WHERE f.user_id = ? AND f.status = 'accepted'
                """,
                (username,)
            ).fetchall()
            return [dict(row) for row in rows]

    def get_pending_requests(self, username: str) -> list[dict[str, Any]]:
        """Получить входящие запросы в друзья."""
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT f.user_id AS from_user_id, u.username, u.display_name, u.bio, f.created_at
                FROM friends f
                JOIN users u ON u.username = f.user_id
                WHERE f.friend_id = ? AND f.status = 'pending'
                """,
                (username,)
            ).fetchall()
            return [dict(row) for row in rows]

    def is_friend(self, username_a: str, username_b: str) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM friends 
                WHERE ((user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?))
                AND status = 'accepted'
                """,
                (username_a, username_b, username_b, username_a)
            ).fetchone()
        return row is not None

    def remove_friend(self, username_a: str, username_b: str) -> bool:
        with self.connect() as conn:
            conn.execute(
                """
                DELETE FROM friends 
                WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)
                """,
                (username_a, username_b, username_b, username_a)
            )
            conn.commit()
        return True

    def register_user(
        self, username: str, password: str, display_name: str | None = None
    ) -> tuple[dict[str, Any] | None, str | None]:
        username = username.strip()[:32]
        if len(username) < 2:
            return None, "Имя пользователя слишком короткое"
        if len(password) < 4:
            return None, "Пароль минимум 4 символа"
        display = (display_name or username).strip()[:48] or username
        try:
            with self.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO users (username, password_hash, display_name, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (username, hash_password(password), display, _now()),
                )
                conn.commit()
        except sqlite3.IntegrityError:
            return None, "Пользователь уже существует"
        return self.get_profile(username), None

    def authenticate(self, username: str, password: str) -> tuple[dict[str, Any] | None, str | None]:
        username = username.strip()[:32]
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
        if not row:
            return None, "Неверный логин или пароль"
        if not verify_password(password, row["password_hash"]):
            return None, "Неверный логин или пароль"
        return self._profile_from_row(row), None

    def get_profile(self, username: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username.strip(),)
            ).fetchone()
        return self._profile_from_row(row) if row else None

    def update_profile(
        self, username: str, display_name: str | None = None, bio: str | None = None
    ) -> dict[str, Any] | None:
        with self.connect() as conn:
            if display_name is not None:
                conn.execute(
                    "UPDATE users SET display_name = ? WHERE username = ?",
                    (display_name.strip()[:48], username),
                )
            if bio is not None:
                conn.execute(
                    "UPDATE users SET bio = ? WHERE username = ?",
                    (bio.strip()[:280], username),
                )
            conn.commit()
        return self.get_profile(username)

    def save_avatar(self, username: str, avatar_data: bytes | None) -> bool:
        """Сохранить аватарку пользователя (BLOB до 1MB)."""
        if avatar_data and len(avatar_data) > 1024 * 1024:  # 1MB limit
            return False
        with self.connect() as conn:
            conn.execute(
                "UPDATE users SET avatar_data = ? WHERE username = ?",
                (avatar_data, username)
            )
            conn.commit()
        return True

    def get_avatar(self, username: str) -> bytes | None:
        """Получить аватарку пользователя."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT avatar_data FROM users WHERE username = ?",
                (username.strip(),)
            ).fetchone()
        return row["avatar_data"] if row else None

    def has_avatar(self, username: str) -> bool:
        """Проверить, есть ли у пользователя аватарка."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT avatar_data FROM users WHERE username = ?",
                (username.strip(),)
            ).fetchone()
        return row is not None and row["avatar_data"] is not None

    def record_quiz_results(self, players: list[dict[str, Any]]) -> None:
        if not players:
            return
        winner = players[0]
        with self.connect() as conn:
            for p in players:
                conn.execute(
                    """
                    UPDATE users SET quiz_games = quiz_games + 1,
                    quiz_points = quiz_points + ?
                    WHERE username = ?
                    """,
                    (p.get("score", 0), p.get("username")),
                )
            conn.execute(
                """
                UPDATE users SET quiz_wins = quiz_wins + 1
                WHERE username = ?
                """,
                (winner.get("username"),),
            )
            conn.commit()

    @staticmethod
    def _profile_from_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "username": row["username"],
            "displayName": row["display_name"],
            "bio": row["bio"],
            "quizWins": row["quiz_wins"],
            "quizGames": row["quiz_games"],
            "quizPoints": row["quiz_points"],
            "createdAt": row["created_at"],
            "has_avatar": row["avatar_data"] is not None,
        }


def _question_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "question": row["question"],
        "options": [row["option_a"], row["option_b"], row["option_c"], row["option_d"]],
        "correctIndex": row["correct_index"],
    }


_db: Database | None = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
        _db.init_schema()
    return _db