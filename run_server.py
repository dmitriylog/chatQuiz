#!/usr/bin/env python3
"""Запуск сервера чата (для связи между компьютерами)."""

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Сервер чата — запустите на одном ПК или в Yandex Cloud"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="0.0.0.0 — доступ из сети/интернета (по умолчанию)",
    )
    parser.add_argument("--port", type=int, default=8765, help="Порт (8765)")
    args = parser.parse_args()

    print(f"Сервер чата: ws://<IP>:{args.port}/ws")
    print("На других компьютерах запустите клиент: python main.py")
    print("Укажите этот IP в поле «Адрес сервера».")
    if not __import__("os").environ.get("CHAT_PASSWORD"):
        print("Подсказка: CHAT_PASSWORD=секрет python run_server.py — защита паролем.")
    print("Ctrl+C — остановка.\n")

    uvicorn.run("server:app", host=args.host, port=args.port, log_level="debug")


if __name__ == "__main__":
    main()
