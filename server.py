"""WebSocket chat server + football quiz."""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from db.database import dm_channel, get_db
from quiz_manager import QuizManager

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger("chat")
log.setLevel(logging.DEBUG)

STATIC_DIR = Path(__file__).parent / "static"
CHAT_PASSWORD = os.environ.get("CHAT_PASSWORD", "").strip()

@dataclass
class Client:
    websocket: WebSocket
    user_id: str
    username: str
    joined_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ChatRoom:
    def __init__(self) -> None:
        self.clients: dict[str, Client] = {}
        self.quiz = QuizManager(self)

    @property
    def online_count(self) -> int:
        return len(self.clients)

    def connect(self, websocket: WebSocket, user_id: str, username: str) -> Client:
        client = Client(websocket=websocket, user_id=user_id, username=username)
        self.clients[user_id] = client
        return client

    def disconnect(self, user_id: str) -> Client | None:
        c = self.clients.pop(user_id, None)
        # Notify quiz manager that a player left so active quizzes don't stall.
        if c and self.quiz and getattr(self.quiz, "active", False):
            try:
                import asyncio
                # Run asynchronously-safe removal
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.call_soon_threadsafe(self.quiz.player_left, user_id)
                else:
                    asyncio.create_task(self._async_notify_quiz_left(user_id))
            except Exception as e:
                log.error(f"Error notifying quiz manager: {e}")
                # Fallback: call synchronously
                self.quiz.player_left(user_id)
        return c

    async def _async_notify_quiz_left(self, user_id: str) -> None:
        """Helper to notify quiz manager asynchronously."""
        if self.quiz:
            self.quiz.player_left(user_id)

    def get_client(self, user_id: str) -> Client | None:
        return self.clients.get(user_id)

    def username_for(self, user_id: str) -> str | None:
        c = self.clients.get(user_id)
        return c.username if c else None

    async def broadcast(self, payload: dict[str, Any], exclude: str | None = None) -> None:
        dead: list[str] = []
        for uid, client in self.clients.items():
            if exclude and uid == exclude:
                continue
            try:
                await client.websocket.send_json(payload)
            except Exception:
                dead.append(uid)
        for uid in dead:
            self.clients.pop(uid, None)

    def user_list(self) -> list[dict[str, str]]:
        return [
            {"id": c.user_id, "username": c.username}
            for c in sorted(self.clients.values(), key=lambda x: x.username.lower())
        ]


room = ChatRoom()
db = get_db()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_schema()
    log.info("Database ready: %s", db.path)
    yield


app = FastAPI(title="Chat Quiz", version="3.0", lifespan=lifespan)

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


async def _send_general_history(client: Client) -> None:
    history = db.get_channel_history("general", limit=150)
    if history:
        await client.websocket.send_json({"type": "history", "channel": "general", "messages": history})


async def _handle_chat_message(client: Client, text: str) -> None:
    db.save_message("general", client.user_id, client.username, text)
    ts = _now_iso()
    payload = {
        "type": "message",
        "userId": client.user_id,
        "username": client.username,
        "text": text,
        "timestamp": ts,
    }
    await room.broadcast(payload, exclude=client.user_id)
    await client.websocket.send_json({**payload, "isEcho": True})


async def _handle_dm(client: Client, to_id: str, text: str) -> None:
    log.info(f"=== DM DEBUG ===")
    log.info(f"From: {client.user_id} ({client.username}) to: {to_id}")
    log.info(f"Text: {text[:50]}")

    target = room.get_client(to_id)
    log.info(f"Target found: {target is not None}")

    if not target or to_id == client.user_id:
        log.warning(f"Target not found or self: {to_id}")
        await client.websocket.send_json({
            "type": "system",
            "text": "Пользователь недоступен",
            "timestamp": _now_iso(),
        })
        return

    channel_id = f"dm_{min(client.user_id, to_id)}_{max(client.user_id, to_id)}"
    log.info(f"Channel: {channel_id}")

    db.save_message(channel_id, client.user_id, client.username, text)
    log.info("Message saved to DB")

    ts = _now_iso()
    payload = {
        "type": "dm",
        "userId": client.user_id,
        "username": client.username,
        "toUserId": to_id,
        "text": text,
        "timestamp": ts,
    }

    # Send to target
    try:
        await target.websocket.send_json(payload)
        log.info(f"✓ DM sent to {target.username}")
    except Exception as e:
        log.error(f"✗ Failed to send to target: {e}")

    # Send echo
    try:
        await client.websocket.send_json({**payload, "isEcho": True})
        log.info(f"✓ Echo sent to {client.username}")
    except Exception as e:
        log.error(f"✗ Failed to send echo: {e}")

    log.info("=== DM DEBUG END ===")


async def _handle_load_dm(client: Client, to_id: str) -> None:
    log.info(f"Loading DM history for {client.username} with {to_id}")
    channel_id = f"dm_{min(client.user_id, to_id)}_{max(client.user_id, to_id)}"
    messages = db.get_channel_history(channel_id, limit=150)
    log.info(f"Found {len(messages)} messages")

    await client.websocket.send_json({
        "type": "history",
        "channel": f"dm:{to_id}",
        "messages": messages,
    })

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    client: Client | None = None
    try:
        await websocket.accept()
        log.info("WebSocket connection accepted")

        raw = await websocket.receive_text()
        hello = json.loads(raw)
        log.info(f"Received hello: {hello.get('username')} - {hello.get('authAction')}")
        if hello.get("type") != "hello":
            await websocket.send_json({"type": "auth_error", "text": "Ожидается hello"})
            await websocket.close(code=1008)
            return

        if CHAT_PASSWORD and hello.get("serverPassword", "") != CHAT_PASSWORD:
            await websocket.send_json({"type": "auth_error", "text": "Неверный пароль сервера"})
            await websocket.close(code=1008)
            return

        auth_action = hello.get("authAction", "login")
        login_name = (hello.get("username") or "").strip()[:32]
        user_password = hello.get("password") or ""

        if auth_action == "register":
            profile, err = db.register_user(
                login_name,
                user_password,
                hello.get("displayName"),
            )
        else:
            profile, err = db.authenticate(login_name, user_password)

        if err or not profile:
            await websocket.send_json({
                "type": "auth_error",
                "text": err or "Ошибка входа",
            })
            await websocket.close(code=1008)
            return

        # В websocket_endpoint, после аутентификации:
        username = profile["displayName"]
        account = profile["username"]

        # Генерируем уникальный ID для каждого подключения
        import uuid
        user_id = uuid.uuid4().hex[:8]
        log.info(f"Generated user_id: {user_id} for {username}")

        print(f"New connection: {username} with ID {user_id}")  # Отладка

        client = room.connect(websocket, user_id, username)
        client.account = account

        await client.websocket.send_json({
            "type": "welcome",
            "userId": client.user_id,
            "username": client.username,
            "account": account,
            "profile": profile,
            "online": room.online_count,
            "users": room.user_list(),
        })
        await _send_general_history(client)

        if room.quiz.active:
            await client.websocket.send_json(room.quiz.state_payload())

        await room.broadcast({
            "type": "user_joined",
            "userId": client.user_id,
            "username": client.username,
            "online": room.online_count,
            "users": room.user_list(),
            "timestamp": _now_iso(),
        }, exclude=client.user_id)
        await room.broadcast({
            "type": "system",
            "text": f"{client.username} присоединился к чату",
            "timestamp": _now_iso(),
        }, exclude=client.user_id)

        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type", "message")

            if msg_type == "ping":
                await client.websocket.send_json({"type": "pong"})
                continue

            if msg_type == "quiz_start":
                err = await room.quiz.start_lobby(client.user_id)
                if err:
                    await client.websocket.send_json(err)
                continue

            if msg_type == "quiz_ready":
                err = await room.quiz.ready_for_quiz(client)
                if err:
                    await client.websocket.send_json(err)
                continue

            if msg_type == "quiz_cancel_lobby":
                err = await room.quiz.cancel_lobby(client)
                if err:
                    await client.websocket.send_json(err)
                continue

            if msg_type == "quiz_exit":
                # Пользователь вышел из викторины - обнуляем его баллы
                if room.quiz.active and room.quiz.session_id:
                    # Обнуляем баллы пользователя в текущей сессии
                    with db.connect() as conn:
                        conn.execute(
                            """
                            UPDATE quiz_players SET score = 0
                            WHERE session_id = ? AND user_id = ?
                            """,
                            (room.quiz.session_id, client.user_id)
                        )
                        conn.commit()
                    
                    # Уведомляем всех о выходе игрока
                    await room.broadcast({
                        "type": "quiz_player_exited",
                        "userId": client.user_id,
                        "username": client.username,
                    })
                continue

            if msg_type == "quiz_answer":
                await room.quiz.submit_answer(client, int(data.get("answerIndex", -1)))
                continue

            if msg_type == "get_user_profile":
                target_id = data.get("user_id", "")
                target_username = data.get("username", "")
                target = room.get_client(target_id)
                if target and hasattr(target, "account"):
                    profile = db.get_profile(target.account)
                    if profile:
                        await client.websocket.send_json({
                            "type": "user_profile",
                            "profile": profile,
                            "requested_user_id": target_id,
                            "requested_username": target_username,
                        })
                continue

            if msg_type == "friend_request":
                to_user_id = data.get("to_user_id", "")
                to_username = data.get("to_username", "")
                target = room.get_client(to_user_id)

                success, msg = db.send_friend_request(
                    client.account, client.username,
                    to_user_id, to_username
                )

                if success and target:
                    await target.websocket.send_json({
                        "type": "friend_request_received",
                        "from_user_id": client.user_id,
                        "from_username": client.username,
                        "timestamp": _now_iso(),
                    })
                    # Also notify target to refresh pending requests
                    await target.websocket.send_json({
                        "type": "pending_requests_updated",
                    })

                await client.websocket.send_json({
                    "type": "friend_request_result",
                    "success": success,
                    "message": msg,
                })
                continue

            if msg_type == "accept_friend":
                from_session_id = data.get("from_user_id", "")
                # Find the target client by session ID to get their account username
                target = room.get_client(from_session_id)
                if not target or not hasattr(target, "account"):
                    log.warning(f"Target not found for session_id: {from_session_id}")
                    continue

                from_username = target.account
                success = db.accept_friend_request(client.account, from_username)

                if success:
                    # Notify both users to refresh their friends lists
                    # Notify the sender of the friend request
                    await target.websocket.send_json({
                        "type": "friend_request_accepted",
                        "by_username": client.username,
                        "timestamp": _now_iso(),
                    })
                    await target.websocket.send_json({
                        "type": "system",
                        "text": f"✅ {client.username} принял(а) вашу заявку в друзья!",
                        "timestamp": _now_iso(),
                    })
                    # Notify the sender to refresh their lists
                    await target.websocket.send_json({
                        "type": "pending_requests_updated",
                    })
                # Notify the user who accepted the request
                await client.websocket.send_json({
                    "type": "friend_list_updated",
                })
                await client.websocket.send_json({
                    "type": "system",
                    "text": f"✅ Вы приняли заявку в друзья!",
                    "timestamp": _now_iso(),
                })
                # Also notify the acceptor to refresh pending requests
                await client.websocket.send_json({
                    "type": "pending_requests_updated",
                })
                continue

            if msg_type == "reject_friend":
                from_session_id = data.get("from_user_id", "")
                # Find the target client by session ID to get their account username
                target = room.get_client(from_session_id)
                if not target or not hasattr(target, "account"):
                    log.warning(f"Target not found for session_id: {from_session_id}")
                    continue

                from_username = target.account
                success = db.reject_friend_request(client.account, from_username)

                if success:
                    await target.websocket.send_json({
                        "type": "friend_request_rejected",
                        "by_user_id": client.user_id,
                        "by_username": client.username,
                    })
                await client.websocket.send_json({
                    "type": "pending_requests_updated",
                })
                continue

            if msg_type == "get_friends":
                try:
                    friends = db.get_friends(client.account)
                    # Add online status and session user_id for each friend
                    for friend in friends:
                        friend_username = friend.get("username", "")
                        # Find the online client with this username
                        for uid, c in room.clients.items():
                            if hasattr(c, "account") and c.account == friend_username:
                                friend["user_id"] = uid
                                friend["is_online"] = True
                                break
                        else:
                            friend["is_online"] = False
                    await client.websocket.send_json({
                        "type": "friends_list",
                        "friends": friends,
                    })
                except Exception as e:
                    log.error(f"Error getting friends: {e}")
                    await client.websocket.send_json({
                        "type": "friends_list",
                        "friends": [],
                    })
                continue

            if msg_type == "get_pending_requests":
                try:
                    pending = db.get_pending_requests(client.account)
                    # Add session user_id for each pending request sender
                    for req in pending:
                        from_username = req.get("username", "")
                        # Find the online client with this username
                        for uid, c in room.clients.items():
                            if hasattr(c, "account") and c.account == from_username:
                                req["from_user_id"] = uid
                                break
                    await client.websocket.send_json({
                        "type": "pending_requests",
                        "requests": pending,
                    })
                except Exception as e:
                    log.error(f"Error getting pending requests: {e}")
                    await client.websocket.send_json({
                        "type": "pending_requests",
                        "requests": [],
                    })
                continue

            if msg_type == "profile_update":
                account = getattr(client, "account", client.username)
                profile = db.update_profile(
                    account,
                    display_name=data.get("displayName"),
                    bio=data.get("bio"),
                )
                if profile:
                    client.username = profile["displayName"]
                    await client.websocket.send_json({
                        "type": "profile_updated",
                        "profile": profile,
                    })
                    await room.broadcast({
                        "type": "user_renamed",
                        "userId": client.user_id,
                        "username": client.username,
                        "users": room.user_list(),
                        "timestamp": _now_iso(),
                    })
                continue

            if msg_type == "avatar_upload":
                account = getattr(client, "account", client.username)
                avatar_b64 = data.get("avatar_data", "")
                
                if not avatar_b64:
                    await client.websocket.send_json({
                        "type": "avatar_result",
                        "success": False,
                        "message": "Нет данных аватарки"
                    })
                    continue
                
                try:
                    import base64
                    # Удаляем data:image/...;base64, префикс если есть
                    if "," in avatar_b64:
                        avatar_b64 = avatar_b64.split(",", 1)[1]
                    
                    avatar_bytes = base64.b64decode(avatar_b64)
                    
                    # Проверяем размер (макс 1MB)
                    if len(avatar_bytes) > 1024 * 1024:
                        await client.websocket.send_json({
                            "type": "avatar_result",
                            "success": False,
                            "message": "Аватарка слишком большая (макс 1MB)"
                        })
                        continue
                    
                    success = db.save_avatar(account, avatar_bytes)
                    
                    await client.websocket.send_json({
                        "type": "avatar_result",
                        "success": success,
                        "message": "Аватарка сохранена" if success else "Ошибка сохранения"
                    })
                except Exception as e:
                    log.error(f"Error saving avatar: {e}")
                    await client.websocket.send_json({
                        "type": "avatar_result",
                        "success": False,
                        "message": "Ошибка при обработке"
                    })
                continue

            if msg_type == "avatar_delete":
                account = getattr(client, "account", client.username)
                success = db.save_avatar(account, None)
                
                await client.websocket.send_json({
                    "type": "avatar_result",
                    "success": success,
                    "message": "Аватарка удалена" if success else "Ошибка удаления"
                })
                continue

            if msg_type == "get_avatar":
                target_username = data.get("username", "")
                avatar_data = db.get_avatar(target_username)
                
                if avatar_data:
                    import base64
                    avatar_b64 = base64.b64encode(avatar_data).decode('utf-8')
                    await client.websocket.send_json({
                        "type": "avatar_data",
                        "username": target_username,
                        "avatar_data": f"data:image/png;base64,{avatar_b64}"
                    })
                else:
                    await client.websocket.send_json({
                        "type": "avatar_data",
                        "username": target_username,
                        "avatar_data": None
                    })
                continue

            if msg_type == "quiz_invite":
                # Приглашение друга в квиз
                target_id = data.get("target_id", "")
                target_username = data.get("target_username", "")
                target = room.get_client(target_id)
                
                if not target:
                    await client.websocket.send_json({
                        "type": "quiz_invite_result",
                        "success": False,
                        "message": "Пользователь не онлайн"
                    })
                    continue
                
                # Проверяем, не идет ли уже викторина
                if room.quiz.active:
                    await client.websocket.send_json({
                        "type": "quiz_invite_result",
                        "success": False,
                        "message": "Викторина уже идет"
                    })
                    continue
                
                # Отправляем приглашение target пользователю
                await target.websocket.send_json({
                    "type": "quiz_invite_received",
                    "from_user_id": client.user_id,
                    "from_username": client.username,
                    "timestamp": _now_iso(),
                })
                
                continue

            if msg_type == "quiz_invite_accept":
                # Принятие приглашения в квиз
                from_user_id = data.get("from_user_id", "")
                from_user = room.get_client(from_user_id)
                
                if not from_user:
                    await client.websocket.send_json({
                        "type": "quiz_invite_result",
                        "success": False,
                        "message": "Пригласивший пользователь offline"
                    })
                    continue
                
                # Запускаем викторину только для этих двух игроков
                # Создаем временную группу из двух игроков
                temp_players = [client, from_user]
                
                # Проверяем, что оба еще онлайн
                if len(temp_players) < 2:
                    await client.websocket.send_json({
                        "type": "quiz_invite_result",
                        "success": False,
                        "message": "Недостаточно игроков"
                    })
                    continue
                
                # Сохраняем игроков для викторины
                room.quiz.invite_players = [client.user_id, from_user.user_id]
                
                # Отправляем обоим уведомление о начале викторины
                for player in temp_players:
                    await player.websocket.send_json({
                        "type": "quiz_invite_accepted",
                        "players": [
                            {"user_id": client.user_id, "username": client.username},
                            {"user_id": from_user.user_id, "username": from_user.username}
                        ]
                    })
                
                # Запускаем викторину
                await room.quiz.start_lobby(client.user_id)
                
                continue

            if msg_type == "quiz_invite_decline":
                # Отклонение приглашения в квиз
                from_user_id = data.get("from_user_id", "")
                from_user = room.get_client(from_user_id)
                
                if from_user:
                    await from_user.websocket.send_json({
                        "type": "quiz_invite_declined",
                        "by_username": client.username,
                    })
                
                continue

            if msg_type == "load_dm":
                to_id = (data.get("toUserId") or "").strip()
                if to_id:
                    await _handle_load_dm(client, to_id)
                continue

            if msg_type == "remove_friend":
                friend_id = data.get("friend_id", "")
                friend_username = data.get("friend_username", "")
                success = db.remove_friend(client.account, friend_username)
                if success:
                    await client.websocket.send_json({
                        "type": "friend_removed",
                        "friend_id": friend_id,
                        "friend_username": friend_username,
                    })
                    target = room.get_client(friend_id)
                    if target:
                        await target.websocket.send_json({
                            "type": "friend_removed",
                            "friend_id": client.user_id,
                            "friend_username": client.username,
                        })
                continue

            if msg_type == "check_friend_status":
                target_username = data.get("username", "")
                is_friend = db.is_friend(client.account, target_username)
                await client.websocket.send_json({
                    "type": "friend_status",
                    "username": target_username,
                    "is_friend": is_friend,
                })
                continue

            if msg_type == "rename":
                new_name = (data.get("username") or "").strip()[:32]
                if new_name:
                    old_name = client.username
                    client.username = new_name
                    await room.broadcast({
                        "type": "user_renamed",
                        "userId": client.user_id,
                        "username": new_name,
                        "oldUsername": old_name,
                        "users": room.user_list(),
                        "timestamp": _now_iso(),
                    })
                continue

            if msg_type == "typing":
                await room.broadcast({
                    "type": "typing",
                    "userId": client.user_id,
                    "username": client.username,
                    "isTyping": bool(data.get("isTyping", True)),
                }, exclude=client.user_id)
                continue

            text = (data.get("text") or "").strip()
            if msg_type == "dm":
                to_id = (data.get("toUserId") or "").strip()
                if text and to_id:
                    await _handle_dm(client, to_id, text)
                continue

            if msg_type == "message" and text:
                await _handle_chat_message(client, text[:4000])
                continue

    except WebSocketDisconnect:
        pass
    except json.JSONDecodeError:
        await websocket.close(code=1003, reason="Invalid JSON")
    except Exception:
        log.exception("WebSocket error")
        if client:
            await websocket.close(code=1011)
    finally:
        if client:
            room.disconnect(client.user_id)
            await room.broadcast({
                "type": "user_left",
                "userId": client.user_id,
                "username": client.username,
                "online": room.online_count,
                "users": room.user_list(),
                "timestamp": _now_iso(),
            })
            await room.broadcast({
                "type": "system",
                "text": f"{client.username} покинул чат",
                "timestamp": _now_iso(),
            })
