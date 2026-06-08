# Развертывание на Yandex Cloud (обновленная инструкция)

## Предварительные требования
- Виртуальная машина в Yandex Cloud с публичным IP (например, `158.160.231.28`)
- Установленные Python 3.10+, pip, git
- Домен (опционально, для HTTPS)

## 1. Подготовка сервера

### Подключитесь к серверу:
```bash
ssh root@158.160.231.28
```

### Установите зависимости:
```bash
sudo apt update
sudo apt install -y python3-pip python3-venv git nginx
```

### Создайте пользователя для приложения:
```bash
sudo adduser chatuser
sudo usermod -aG sudo chatuser
su - chatuser
```

## 2. Установка приложения

### Клонируйте репозиторий:
```bash
cd ~
git clone <ваш_репозиторий> chat
cd chat
```

### Создайте виртуальное окружение:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Настройте базу данных:
```bash
# База данных создастся автоматически при первом запуске
# Для сброса существующей БД:
rm -f data/chat.db
```

## 3. Настройка сервера

### Создайте файл окружения:
```bash
nano .env
```

Содержимое:
```
# Порт сервера
PORT=8765

# Пароль сервера (опционально)
CHAT_PASSWORD=ваш_секретный_пароль

# Ключ шифрования (опционально, для безопасности сообщений)
# Сгенерируйте ключ: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
CHAT_ENCRYPTION_KEY=ваш_ключ_шифрования

# Хост для прослушивания
HOST=0.0.0.0
```

### Создайте systemd сервис:
```bash
sudo nano /etc/systemd/system/chat-quiz.service
```

Содержимое (начинайте с `[Unit]`, а не с `ini`):
```
[Unit]
Description=Chat Quiz WebSocket Server
After=network.target

[Service]
Type=simple
User=chatuser
WorkingDirectory=/home/chatuser/chat
Environment="PATH=/home/chatuser/chat/.venv/bin"
ExecStart=/home/chatuser/chat/.venv/bin/python run_server.py --host 0.0.0.0 --port 8765
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Запустите сервис:
```bash
sudo systemctl daemon-reload
sudo systemctl enable chat-quiz
sudo systemctl start chat-quiz
sudo systemctl status chat-quiz
```

## 4. Настройка Nginx (опционально, для проксирования)

### Создайте конфиг Nginx:
```bash
sudo nano /etc/nginx/sites-available/chat
```

Содержимое (убедитесь, что нет лишних символов в начале файла):
```nginx
server {
    listen 80;
    server_name 158.160.231.28;

    location /ws {
        proxy_pass http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }

    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**Важно:** Убедитесь, что в файле нет лишних строк в начале (особенно слов "nginx" или других директив вне блока server). Файл должен начинаться сразу с `server {`.

### Включите сайт:
```bash
# Удаляем старую ссылку если существует
sudo rm -f /etc/nginx/sites-enabled/chat

# Создаем новую ссылку
sudo ln -s /etc/nginx/sites-available/chat /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 5. Настройка брандмауэра

### Откройте порты:
```bash
sudo ufw allow 80/tcp
sudo ufw allow 8765/tcp
sudo ufw enable
```

## 6. Настройка клиента

### На клиентских устройствах:
1. Установите Python 3.10+
2. Установите зависимости: `pip install -r requirements.txt`
3. Запустите клиент: `python main.py`
4. В поле "Адрес сервера" укажите: `158.160.231.28` (или ваш домен)
5. Введите логин и пароль

### Для Windows/Mac можно создать установщик:
```bash
# На машине разработки (Linux/Mac/Windows)
pip install pyinstaller
pyinstaller --onefile --windowed --name="ChatQuiz" main.py
# Исполняемый файл появится в dist/ChatQuiz.exe (Windows) или dist/ChatQuiz (Mac/Linux)
```

## 7. Проверка работы

### Проверьте статус сервиса:
```bash
sudo systemctl status chat-quiz
```

Если сервис не запущен, запустите его:
```bash
sudo systemctl start chat-quiz
```

### Проверьте логи сервера:
```bash
sudo journalctl -u chat-quiz -f
```

Или последние 50 строк:
```bash
sudo journalctl -u chat-quiz -n 50 --no-pager
```

### Проверьте, слушает ли сервер порт:
```bash
sudo netstat -tulpn | grep 8765
# или
sudo ss -tulpn | grep 8765
```

### Проверьте подключение:
```bash
curl -i http://127.0.0.1:8765/
```

Должен вернуться HTML файл. Если на localhost работает, но по внешнему IP нет - проверьте брандмауэр:
```bash
sudo ufw status
sudo ufw allow 8765/tcp
```

### Если сервис не запускается:
1. Проверьте, что виртуальное окружение активно: `source /home/chatuser/chat/.venv/bin/activate`
2. Попробуйте запустить сервер вручную для отладки:
   ```bash
   cd /home/chatuser/chat
   source .venv/bin/activate
   python run_server.py --host 0.0.0.0 --port 8765
   ```
3. Проверьте логи на ошибки Python: `sudo journalctl -u chat-quiz -xe`

### Если сервис постоянно перезапускается (activating/auto-restart):

1. **Остановите сервис:**
```bash
sudo systemctl stop chat-quiz
```

2. **Проверьте логи:**
```bash
sudo journalctl -u chat-quiz -n 30 --no-pager
```

3. **Попробуйте запустить вручную для отладки:**
```bash
cd /home/chatuser/chat
source .venv/bin/activate
python run_server.py --host 0.0.0.0 --port 8765
```

4. **Если ошибка "address already in use" - убейте процесс:**
```bash
# Найдите процесс, использующий port 8765
sudo lsof -i :8765
# или
sudo netstat -tulpn | grep 8765

# Убейте процесс
sudo kill -9 <PID>
```

5. **Запустите сервис снова:**
```bash
sudo systemctl start chat-quiz
sudo systemctl status chat-quiz
```

6. **Если все еще не работает - проверьте права доступа:**
```bash
# Убедитесь что chatuser владеет файлами
sudo chown -R chatuser:chatuser /home/chatuser/chat

# Проверьте что виртуальное окружение работает
sudo -u chatuser /home/chatuser/chat/.venv/bin/python --version
```

## 8. Обновление приложения

### Для обновления кода:
```bash
cd ~/chat
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart chat-quiz
```

## 9. Резервное копирование

### База данных находится в:
```
/home/chatuser/chat/data/chat.db
```

### Для резервного копирования:
```bash
cp /home/chatuser/chat/data/chat.db /backup/chat_$(date +%Y%m%d).db
```

## 10. Безопасность


## 11. Мониторинг

### Просмотр использования ресурсов:
```bash
# Память и CPU
sudo systemctl status chat-quiz

# Логи
sudo journalctl -u chat-quiz --since "1 hour ago"

# Активные подключения
sudo netstat -tulpn | grep 8765
```

## Готово!

Приложение должно быть доступно по адресу:
- WebSocket: `ws://158.160.231.28:8765/ws`
- HTTP: `http://158.160.231.28:8765/`

Для подключения клиентов используйте IP `158.160.231.28` в настройках клиента.