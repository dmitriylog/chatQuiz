# Как добавить вопросы в базу данных викторины

## Способ 1: Через Python скрипт

Создайте файл `add_questions.py`:

```python
#!/usr/bin/env python3
"""Скрипт для добавления вопросов в базу данных викторины."""

from db.database import get_db

def add_questions():
    db = get_db()
    
    # Пример добавления вопроса
    # Вопрос, 4 варианта ответа, индекс правильного ответа (0-3)
    
    questions = [
        {
            "question": "Столица Франции?",
            "options": ["Лондон", "Берлин", "Париж", "Мадрид"],
            "correct_index": 2  # Париж
        },
        {
            "question": "Сколько планет в Солнечной системе?",
            "options": ["7", "8", "9", "10"],
            "correct_index": 1  # 8
        },
        # Добавьте свои вопросы здесь...
    ]
    
    for q in questions:
        question_id = db.add_question(
            q["question"],
            q["options"],
            q["correct_index"]
        )
        print(f"Добавлен вопрос ID={question_id}: {q['question']}")
    
    print(f"\nВсего вопросов в базе: {db.get_question_count()}")

if __name__ == "__main__":
    add_questions()
```

Запустите скрипт:
```bash
python add_questions.py
```

## Способ 2: Прямой SQL запрос

Можно добавить вопросы напрямую через SQLite:

```bash
sqlite3 data/chat.db
```

```sql
-- Добавление вопроса
INSERT INTO quiz_questions (question, option_a, option_b, option_c, option_d, correct_index, sort_order)
VALUES (
    'Ваш вопрос здесь?',
    'Вариант A',
    'Вариант B', 
    'Вариант C',
    'Вариант D',
    0,  -- индекс правильного ответа (0=A, 1=B, 2=C, 3=D)
    (SELECT MAX(sort_order) + 1 FROM quiz_questions)
);

-- Проверка количества вопросов
SELECT COUNT(*) FROM quiz_questions;

-- Просмотр всех вопросов
SELECT id, question, option_a, option_b, option_c, option_d, correct_index 
FROM quiz_questions ORDER BY sort_order;

-- Удаление вопроса по ID
DELETE FROM quiz_questions WHERE id = 1;

.exit
```

## Способ 3: Массовое добавление из JSON файла

Создайте файл `questions.json`:

```json
[
    {
        "question": "Вопрос 1?",
        "options": ["A", "B", "C", "D"],
        "correct_index": 0
    },
    {
        "question": "Вопрос 2?",
        "options": ["A", "B", "C", "D"],
        "correct_index": 2
    }
]
```

Скрипт `import_json.py`:

```python
#!/usr/bin/env python3
import json
from db.database import get_db

def import_from_json(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        questions = json.load(f)
    
    db = get_db()
    for q in questions:
        db.add_question(q['question'], q['options'], q['correct_index'])
    
    print(f"Импортировано {len(questions)} вопросов")
    print(f"Всего вопросов: {db.get_question_count()}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Использование: python import_json.py questions.json")
    else:
        import_from_json(sys.argv[1])
```

## Формат вопросов

Каждый вопрос должен содержать:
- `question` - текст вопроса
- `options` - список из 4 вариантов ответа
- `correct_index` - индекс правильного ответа (0, 1, 2 или 3)

## Примеры вопросов для футбольной викторины

```python
questions = [
    {
        "question": "Какая страна выиграла первый чемпионат мира по футболу?",
        "options": ["Бразилия", "Уругвай", "Аргентина", "Италия"],
        "correct_index": 1
    },
    {
        "question": "Кто является рекордсменом по количеству голов за сборную?",
        "options": ["Пеле", "Марадона", "Криштиану Роналду", "Месси"],
        "correct_index": 2
    },
    {
        "question": "В каком году прошел первый чемпионат мира?",
        "options": ["1928", "1930", "1934", "1938"],
        "correct_index": 1
    },
    # Добавьте больше вопросов...
]
```

## Проверка работы

После добавления вопросов:
1. Перезапустите сервер: `python run_server.py`
2. Запустите викторину через интерфейс клиента
3. Вопросы будут выбираться случайным образом из базы данных