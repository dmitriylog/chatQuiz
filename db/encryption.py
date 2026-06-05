"""Модуль шифрования сообщений и паролей."""

from __future__ import annotations

import base64
import hashlib
import os
from typing import Tuple

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

# Ключ шифрования хранится в переменной окружения CHAT_ENCRYPTION_KEY
# Если не задан - генерируется новый при каждом запуске (не рекомендуется для продакшена)

ENCRYPTION_KEY_ENV = "CHAT_ENCRYPTION_KEY"
SALT_FILE = os.path.join(os.path.dirname(__file__), "..", "data", ".encryption_salt")


def get_or_create_key() -> bytes:
    """Получить ключ шифрования из переменной окружения или сгенерировать новый."""
    # Проверяем переменную окружения
    env_key = os.environ.get(ENCRYPTION_KEY_ENV)
    if env_key:
        try:
            return base64.urlsafe_b64decode(env_key)
        except Exception:
            pass
    
    # Пытаемся прочитать из файла
    salt_path = os.path.abspath(SALT_FILE)
    os.makedirs(os.path.dirname(salt_path), exist_ok=True)
    
    if os.path.exists(salt_path):
        with open(salt_path, "rb") as f:
            stored_key = f.read()
            if len(stored_key) == 44:  # Base64 encoded Fernet key
                return base64.urlsafe_b64decode(stored_key)
    
    # Генерируем новый ключ
    key = Fernet.generate_key()
    
    # Сохраняем в файл
    with open(salt_path, "wb") as f:
        f.write(base64.urlsafe_b64encode(key))
    
    # Устанавлим права только для владельца
    os.chmod(salt_path, 0o600)
    
    return key


def get_fernet() -> Fernet:
    """Получить экземпляр Fernet для шифрования/дешифрования."""
    key = get_or_create_key()
    return Fernet(key)


def encrypt_message(message: str) -> str:
    """Зашифровать сообщение."""
    f = get_fernet()
    encrypted = f.encrypt(message.encode("utf-8"))
    return base64.urlsafe_b64encode(encrypted).decode("utf-8")


def decrypt_message(encrypted_message: str) -> str:
    """Расшифровать сообщение."""
    f = get_fernet()
    try:
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_message.encode("utf-8"))
        decrypted = f.decrypt(encrypted_bytes)
        return decrypted.decode("utf-8")
    except Exception as e:
        print(f"Error decrypting message: {e}")
        return encrypted_message  # Возвращаем как есть при ошибке


def hash_password_secure(password: str, salt: bytes = None) -> Tuple[str, str]:
    """
    Хэшировать пароль с солью используя PBKDF2.
    Возвращает (хэш, соль) в base64.
    """
    if salt is None:
        salt = os.urandom(32)
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = kdf.derive(password.encode("utf-8"))
    return base64.urlsafe_b64encode(key).decode("utf-8"), base64.urlsafe_b64encode(salt).decode("utf-8")


def verify_password_secure(password: str, stored_hash: str, stored_salt: str) -> bool:
    """
    Проверить пароль против сохраненного хэша.
    """
    try:
        salt = base64.urlsafe_b64decode(stored_salt.encode("utf-8"))
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = kdf.derive(password.encode("utf-8"))
        return base64.urlsafe_b64encode(key).decode("utf-8") == stored_hash
    except Exception:
        return False