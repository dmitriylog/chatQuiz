#!/bin/bash
# Запуск на ВМ Yandex Cloud (Ubuntu 22.04/24.04) под root или через sudo:
#   curl -fsSL ... | bash
# или после копирования проекта в /opt/chat:
#   sudo bash /opt/chat/deploy/setup-vm.sh

set -euo pipefail

CHAT_DIR="${CHAT_DIR:-/opt/chat}"
export DEBIAN_FRONTEND=noninteractive

echo "==> Обновление пакетов..."
apt-get update -qq
apt-get install -y -qq ca-certificates curl git nginx

if ! command -v docker &>/dev/null; then
  echo "==> Установка Docker..."
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
fi

if ! docker compose version &>/dev/null 2>&1; then
  apt-get install -y -qq docker-compose-plugin || true
fi

if [[ ! -f "$CHAT_DIR/docker-compose.yml" ]]; then
  echo "Ошибка: не найден $CHAT_DIR/docker-compose.yml"
  echo "Скопируйте проект на сервер, например: rsync -avz ./chat/ user@IP:/opt/chat/"
  exit 1
fi

echo "==> Сборка и запуск чата..."
cd "$CHAT_DIR"
docker compose build --quiet
docker compose up -d

echo "==> Настройка nginx..."
rm -f /etc/nginx/sites-enabled/default
ln -sf "$CHAT_DIR/deploy/nginx/chat.conf" /etc/nginx/sites-enabled/chat
nginx -t
systemctl enable nginx
systemctl reload nginx

echo ""
echo "Готово. Чат слушает localhost:8765, снаружи — порт 80 (nginx)."
echo "Откройте в браузере: http://$(curl -fsSL -m 2 ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')/"
echo ""
echo "Не забудьте в Yandex Cloud открыть TCP 80 (и 443 для HTTPS) в группе безопасности ВМ."
