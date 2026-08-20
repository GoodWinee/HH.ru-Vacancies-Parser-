# Используем легкий образ Python на базе Debian (Bookworm)
FROM python:3.11-slim

# Устанавливаем Chromium и ChromeDriver, а также необходимые системные библиотеки
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Указываем пути к браузеру и драйверу для Linux
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем файл зависимостей и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь остальной код проекта
COPY . .

# Команда запуска по умолчанию
CMD ["python", "main.py"]