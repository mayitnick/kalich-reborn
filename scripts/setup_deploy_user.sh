#!/usr/bin/env bash
# ==============================================================================
# Скрипт создания и изоляции пользователя для безопасного CD (Phase 9.1)
# ==============================================================================
set -euo pipefail

DEPLOY_USER="kalich-deployer"
PROJECT_DIR="/opt/kalich"

echo "=== Создание непривилегированного пользователя: ${DEPLOY_USER} ==="
if ! id -u "${DEPLOY_USER}" >/dev/null 2>&1; then
    useradd -m -s /bin/bash "${DEPLOY_USER}"
    echo "Пользователь ${DEPLOY_USER} успешно создан."
else
    echo "Пользователь ${DEPLOY_USER} уже существует."
fi

# Добавление в группу docker (для управления контейнерами без полного root)
if getent group docker >/dev/null 2>&1; then
    usermod -aG docker "${DEPLOY_USER}"
    echo "Пользователь ${DEPLOY_USER} добавлен в группу docker."
fi

# Настройка sudoers для строго разрешенных команд docker compose
SUDOERS_FILE="/etc/sudoers.d/99-kalich-deployer"
cat << 'EOF' > "${SUDOERS_FILE}"
kalich-deployer ALL=(ALL) NOPASSWD: /usr/bin/docker compose up -d --build, /usr/bin/docker compose down, /usr/bin/docker compose restart
EOF
chmod 440 "${SUDOERS_FILE}"
echo "Правила sudoers настроены: ${SUDOERS_FILE}"

# Настройка SSH ключей Ed25519 для CI/CD
SSH_DIR="/home/${DEPLOY_USER}/.ssh"
mkdir -p "${SSH_DIR}"
chmod 700 "${SSH_DIR}"

KEY_PATH="${SSH_DIR}/id_ed25519"
if [ ! -f "${KEY_PATH}" ]; then
    ssh-keygen -t ed25519 -N "" -f "${KEY_PATH}" -C "kalich-ci-cd-deployer"
    cat "${KEY_PATH}.pub" >> "${SSH_DIR}/authorized_keys"
    chmod 600 "${SSH_DIR}/authorized_keys"
    echo "Сгенерирован новый ключ SSH Ed25519: ${KEY_PATH}"
    echo "Добавьте приватный ключ в GitHub Secrets: DEPLOY_SSH_KEY"
fi

chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "/home/${DEPLOY_USER}"
echo "=== Настройка завершена успешно ==="
