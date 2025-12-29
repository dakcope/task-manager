# Асинхронный сервис управления задачами

Задача покрывает асинхронность путем горизонтального масштабирования.
В качестве отказоустойчивого решения реализация включает Outbox-модуль, который непосредственно взаимодействует с RabbitMQ.
Под него была создана отдельная таблица.

## Содержание
- [1. Запуск в Docker](#1-запуск-в-docker)
- [2. Настройка окружения](#2-настройка-окружения)
- [3. Запуск тестов](#3-запуск-тестов)
  - [3.1. Юнит-тесты](#31-юнит-тесты)
  - [3.2. Интеграционные тесты](#32-интеграционные-тесты)
- [4. Общая документация](#4-общая-документация)

---

## 1. Запуск в Docker

Система приоритетов реализована настройкой воркера [WORKER_QUEUES] - то какую очередь он слушает.
Перед запуском контейнера важно под текущую необходимость настроить воркеров.
В текущей реализации docker-compose реализованы 2 типа воркеров - слушающий только high очередь и слушающие low и medium

```yaml
  worker:
    build: .
    restart: unless-stopped
    env_file: [ .env ]
    depends_on:
      postgres:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
    environment:
      WORKER_QUEUES: "tasks.high,tasks.medium,tasks.low"
    command: python -m app.workers.run
```

Поднимаем контейнер, сразу на данном этапе скалируем воркеров
```bash
docker compose up -d --scale worker_high=1 --scale worker=2
```

## 2. Настройка окружения

В корне проекта есть .env.example - как "ленивое" решение, его можно просто переименовать.

настройки БД

POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_HOST
POSTGRES_PORT


RABBITMQ_URL - Строка подключения RabbitMQ вида - amqp://guest:guest@rabbitmq:5672/

####  Дополнительно:

WORKER_PREFETCH -сколько сообщений воркер может забрать не подтверждая prefetch_count
MAX_RETRIES - количество повторных попыток обработки сообщения воркером перед dlq
RETRY_DELAYS_SECONDS - количество retry очередей и их таймер в сек (через запятую)

OUTBOX_POLL_INTERVAL - каунт оубокса на проверку бд
OUTBOX_BATCH_SIZE - каунт пачки сообщений для оутбокс паблиш
OUTBOX_MAX_ATTEMPTS- количество попыток обработки перед статусом FAILED


## 3. Запуск тестов

### 3.1 Юнит-тесты
```bash
pytest tests/unit -vv  
```

### 3.2 Интеграционные тесты
```bash
pytest tests/integration -vv 
```

## 4 Общая документация
[Документация](./documents/)

