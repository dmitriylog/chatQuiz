#!/bin/bash
# Деплой с вашего компьютера на ВМ Yandex Cloud.
# Использование:
#   export CHAT_SERVER=ubuntu@158.160.xx.xx   # публичный IP ВМ
#   bash deploy/deploy-from-pc.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ -z "${CHAT_SERVER:-}" ]]; then
  echo "Укажите адрес сервера:"
  echo "  export CHAT_SERVER=ubuntu@ВАШ_ПУБЛИЧНЫЙ_IP"
  echo "  # опционально: export CHAT_SSH_KEY=~/.ssh/yandex_chat"
  echo "  bash deploy/deploy-from-pc.sh"
  exit 1
fi

SSH_OPTS=()
RSYNC_SSH="ssh"
if [[ -n "${CHAT_SSH_KEY:-}" ]]; then
  SSH_OPTS=(-i "$CHAT_SSH_KEY")
  RSYNC_SSH="ssh -i $CHAT_SSH_KEY"
fi

echo "==> Копирование файлов на $CHAT_SERVER:/opt/chat ..."
ssh "${SSH_OPTS[@]}" "$CHAT_SERVER" "sudo mkdir -p /opt/chat && sudo chown -R \$(whoami):\$(whoami) /opt/chat"

rsync -avz --delete -e "$RSYNC_SSH" \
  --exclude '.venv' \
  --exclude '.idea' \
  --exclude '__pycache__' \
  --exclude '.git' \
  "$PROJECT_DIR/" "$CHAT_SERVER:/opt/chat/"

echo "==> Установка на сервере..."
ssh -t "${SSH_OPTS[@]}" "$CHAT_SERVER" "sudo bash /opt/chat/deploy/setup-vm.sh"

echo ""
echo "Деплой завершён. Откройте http://$(echo "$CHAT_SERVER" | cut -d@ -f2)/"
