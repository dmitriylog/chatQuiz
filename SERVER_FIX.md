# Исправление ошибки systemd-сервиса

## Проблема
Сервер не запускается из-за ошибки:
```
Failed to locate executable /home/chatuser/chat/.venv/bin/python: No such file or directory
```

## Причина
Systemd-сервис настроен на запуск Python из виртуального окружения, которого нет на сервере.

## Решение

### Вариант 1: Создать виртуальное окружение на сервере

1. Подключитесь к серверу:
```bash
ssh chatuser@compute-vm-2-2-93-ssd-1780238751724
```

2. Перейдите в директорию проекта:
```bash
cd /home/chatuser/chat
```

3. Создайте виртуальное окружение:
```bash
python3 -m venv .venv
```

4. Активируйте виртуальное окружение:
```bash
source .venv/bin/activate
```

5. Установите зависимости:
```bash
pip install -r requirements.txt
```

6. Выйдите из виртуального окружения:
```bash
deactivate
```

7. Перезапустите сервис:
```bash
sudo systemctl restart chat-quiz
```

8. Проверьте статус:
```bash
sudo systemctl status chat-quiz
```

### Вариант 2: Изменить systemd-сервис для использования системного Python

Если вы не хотите использовать виртуальное окружение, измените сервис:

1. Откройте файл сервиса:
```bash
sudo nano /etc/systemd/system/chat-quiz.service
```

2. Найдите строку с `ExecStart` и измените путь к Python:
```ini
# Было:
ExecStart=/home/chatuser/chat/.venv/bin/python /home/chatuser/chat/run_server.py

# Стало (используем системный Python):
ExecStart=/usr/bin/python3 /home/chatuser/chat/run_server.py
```

3. Перезагрузите конфигурацию systemd:
```bash
sudo systemctl daemon-reload
```

4. Перезапустите сервис:
```bash
sudo systemctl restart chat-quiz
```

### Вариант 3: Использовать абсолютный путь к Python в скрипте

Также можно изменить `run_server.py`, добавив shebang:
```python
#!/usr/bin/env python3
```

И сделать файл исполняемым:
```bash
chmod +x run_server.py
```

Затем в systemd-сервисе указать:
```ini
ExecStart=/home/chatuser/chat/run_server.py
```

## Проверка

После исправления проверьте логи:
```bash
sudo journalctl -u chat-quiz -f
```

Сервер должен запуститься без ошибок.