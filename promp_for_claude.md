# Техническое задание

## 1. Цель проекта

Разработать CLI-утилиту, которая:

1. Получает список опросов из беседы VK за заданный период
2. Извлекает:

   * кто проголосовал “будет”
   * кто “не будет”
   * кто не голосовал
3. Формирует Excel-файл:

   * матрица участник × дата
   * агрегированная статистика по каждому участнику

---

## 2. Технологический стек

* Язык: **Python 3.11+**
* HTTP: `httpx` (async)
* Асинхронность: `asyncio`
* Excel: `pandas + openpyxl`
* Конфиг: `.env` + `pydantic-settings` или `python-dotenv`
* CLI: `argparse`

---

## 3. Архитектура проекта

Сгенерировать структуру:

```
vk_poll_tracker/
│
├── app/
│   ├── main.py
│   ├── config.py
│   │
│   ├── vk/
│   │   ├── client.py
│   │   ├── rate_limiter.py
│   │   ├── methods.py
│   │
│   ├── services/
│   │   ├── poll_service.py
│   │   ├── user_service.py
│   │   ├── analytics_service.py
│   │
│   ├── models/
│   │   ├── poll.py
│   │   ├── user.py
│   │   ├── record.py
│   │
│   ├── exporters/
│   │   ├── excel_exporter.py
│
├── .env.example
├── requirements.txt
├── README.md
```

---

## 4. Конфигурация (.env)

```
VK_TOKEN=your_token_here
VK_API_VERSION=5.131
PEER_ID=2000000000  # id беседы
RATE_LIMIT_PER_SEC=3
MAX_CONCURRENT_REQUESTS=5
```

---

## 5. VK клиент

### Требования

Реализовать `VKClient`:

* асинхронный
* использует `httpx.AsyncClient`
* автоматически добавляет:

  * `access_token`
  * `v`

---

## 6. Ограничение скорости (ключевой блок)

Реализовать:

### 6.1 Semaphore

* ограничение одновременных запросов (`asyncio.Semaphore`)

### 6.2 Rate limiting

* не более `RATE_LIMIT_PER_SEC` запросов в секунду
* реализовать через:

  * time window
  * или токен-бакет

### 6.3 Retry + backoff

При ошибках VK:

* `error_code = 6` (too many requests)
* `error_code = 9`

→ делать retry с exponential backoff:

```python
delay = base * (2 ** attempt)
```

---

## 7. Методы VK (обязательные)

Реализовать обёртки:

### messages.getHistory

→ получение сообщений с опросами

### polls.getById

→ получение структуры опроса

### polls.getVoters

→ получение голосовавших

### messages.getConversationMembers

→ список участников

---

## 8. Логика сбора данных

## 8.1 Получение опросов

* брать сообщения из беседы

* фильтровать:

  ```python
  attachment.type == "poll"
  ```

* фильтр по дате:

  * `date_from`
  * `date_to`

---

## 8.2 Классификация ответов

Нужно автоматически определить:

* YES (будет)
* NO (не будет)

Правило:

```python
text = answer["text"].lower()

if any(word in text for word in ["буду", "приду", "да"]):
    YES
elif any(word in text for word in ["не", "нет"]):
    NO
else:
    IGNORE
```

---

## 8.3 Формирование записей

Модель:

```
Record:
    user_id
    poll_date
    status: YES | NO | UNKNOWN
```

---

## 8.4 Обработка отсутствующих голосов

Если пользователь:

* есть в участниках
* но нет в voters

→ статус = UNKNOWN

---

## 9. Аналитика

Для каждого пользователя:

```
attended = count(YES)
missed = count(NO)
unknown = count(UNKNOWN)
total = attended + missed + unknown
```

---

## 10. Excel экспорт

Файл: `report.xlsx`

### Лист 1: matrix

| user | 01.03 | 05.03 | ... |

значения:

* YES
* NO
* UNKNOWN

---

### Лист 2: summary

| user | attended | missed | unknown | total |

---

## 11. CLI интерфейс

Пример запуска:

```bash
python -m app.main \
    --date-from 2026-03-01 \
    --date-to 2026-03-31 \
    --output report.xlsx
```

---

## 12. MVP требования

Claude должен:

1. Сгенерировать весь проект
2. Реализовать:

   * VK клиент
   * rate limiter
   * сбор опросов
   * сбор голосов
   * Excel экспорт
3. Добавить логирование:

   * этапы
   * ошибки
4. Сделать код **запускаемым сразу после заполнения .env**

---

## 13. Дополнительные требования

* Все функции типизированы
* Минимум магии, максимум явной логики
* Код разбит по слоям (client / services / exporters)
* Без лишних абстракций

---

## 14. README.md

Должен содержать:

* как получить токен VK
* как узнать `peer_id`
* как запустить
* пример результата
