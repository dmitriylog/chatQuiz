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

Содержимое:
```ini
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

Содержимое:
```nginx
server {
    listen 80;
    server_name 158.160.231.28;  # Или ваш домен

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

### Включите сайт:
```bash
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

### Проверьте логи сервера:
```bash
sudo journalctl -u chat-quiz -f
```

### Проверьте подключение:
```bash
curl -i http://158.160.231.28:8765/
```

Должен вернуться HTML файл.

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

### Рекомендации:
1. Используйте HTTPS (настройте SSL через Let's Encrypt)
2. Установите сложный пароль сервера (`CHAT_PASSWORD`)
3. Регулярно обновляйте систему: `sudo apt update && sudo apt upgrade`
4. Настройте fail2ban для защиты от брутфорса

### Настройка SSL (Let's Encrypt):
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d ваш-домен.ru
```

## 11. Мониторинг

### Установите htop для мониторинга:
```bash
sudo apt install htop
htop
```

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