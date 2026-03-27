# Используем легкий образ Python 3.13
FROM python:3.13-slim

# Устанавливаем рабочую директорию
WORKDIR /transport_app

# Устанавливаем переменные окружения, чтобы Python не создавал .pyc файлы и сразу выводил логи в консоль
# Переменные окружения для Python и Poetry
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=2.3.2 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_HOME="/opt/poetry" \
    FLASK_APP=transportapp.py

# Добавляем Poetry в PATH
ENV PATH="$POETRY_HOME/bin:$PATH"

# Устанавливаем системные зависимости и Poetry
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && apt-get purge -y --auto-remove curl \
    && rm -rf /var/lib/apt/lists/*

# Копируем только файлы зависимостей (для кеширования слоев Docker)
COPY pyproject.toml poetry.lock ./

# Устанавливаем зависимости через Poetry (без создания venv и без dev-пакетов)
RUN poetry install --no-interaction --no-ansi --no-root --only main

# Копируем остальной код проекта
COPY . .

# Открываем порт
EXPOSE 5000

# Запуск через flask
CMD ["flask", "run", "--host=0.0.0.0"]