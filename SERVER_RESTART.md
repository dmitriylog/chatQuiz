# Краткая инструкция по запуску сервера

## Если сервер уже развернут на Yandex Cloud (158.160.231.28)

### 1. Подключитесь к серверу:
```bash
ssh chatuser@158.160.231.28
```

### 2. Перейдите в директорию проекта:
```bash
cd ~/chat
```

### 3. Активируйте виртуальное окружение:
```bash
source .venv/bin/activate
```

### 4. Запустите сервер вручную (для тестирования):
```bash
python run_server.py --host 0.0.0.0 --port 8765
```

### 5. Или управляйте сервисом systemd:
```bash
# Запустить сервис
sudo systemctl start chat-quiz

# Остановить сервис
sudo systemctl stop chat-quiz

# Перезапустить сервис
sudo systemctl restart chat-quiz

# Проверить статус
sudo systemctl status chat-quiz

# Посмотреть логи
sudo journalctl -u chat-quiz -f
```

## Если порт 8765 уже занят:

```bash
# Найдите процесс, занимающий порт
sudo lsof -i :8765

# Убейте все процессы Python
sudo pkill -9 -f "run_server.py"

# Запустите сервис снова
sudo systemctl start chat-quiz
```

## Проверка работы:

```bash
# Проверьте, слушает ли сервер порт
sudo netstat -tulpn | grep 8765

# Или проверьте локально
curl -i http://127.0.0.1:8765/
```

## Для подключения клиента:

На клиентском устройстве:
1. Запустите `python main.py`
2. В поле "Адрес сервера" укажите: `158.160.231.28`
3. Введите логин и пароль