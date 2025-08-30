# Telegram RSS Feed Monitor Bot (Шаблон)

Это шаблон для создания Telegram-бота на Python, который отслеживает RSS-ленты на предмет новых записей и отправляет уведомления пользователям. Проект имеет модульную структуру и хорошо подходит в качестве основы для более сложных ботов.

---

This is a template for creating a Python-based Telegram bot that monitors RSS feeds for new entries and sends notifications to users. The project features a modular architecture, making it a great starting point for more complex bots.

---

## 🇷🇺 Описание на русском

Этот бот предназначен для мониторинга любых RSS-лент (например, с сайтов-агрегаторов торгов, новостных порталов или блогов). Пользователь добавляет ссылку на RSS-ленту, и бот периодически проверяет ее. При появлении новой записи бот отправляет уведомление всем подписанным пользователям.

### ✨ Основные возможности

*   **Модульная архитектура:** Логика разделена на сервисы (работа с ссылками, получение данных, парсинг, отправка уведомлений).
*   **Асинхронные проверки:** Использует `APScheduler` для периодической проверки ссылок в фоновом режиме, не блокируя работу бота.
*   **Хранение данных в JSON:** Простое и понятное хранение данных о пользователях и ссылках в JSON-файлах с потокобезопасной записью.
*   **Надежность:** Автоматические повторные попытки при сетевых ошибках с помощью библиотеки `tenacity`.
*   **Гибкая настройка:** Все ключевые параметры (токен, интервал проверки) вынесены в файл конфигурации `.env`.
*   **Управление подписками:** Пользователи могут добавлять, просматривать и удалять свои подписки, а также задавать для них короткие псевдонимы (алиасы).
*   **Обработка ошибок:** Бот отслеживает ошибки при доступе к ссылкам и автоматически деактивирует "мертвые" ленты.

### 🚀 Установка и запуск

1.  **Клонируйте репозиторий:**
    ```bash
    git clone https://github.com/YourUsername/telegram-rss-monitor-bot-template.git
    cd telegram-rss-monitor-bot-template
    ```

2.  **Создайте и активируйте виртуальное окружение:**
    ```bash
    # Для Windows
    python -m venv venv
    venv\Scripts\activate
    
    # Для macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Установите зависимости:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Настройте переменные окружения:**
    *   Переименуйте файл `.env.example` в `.env`.
    *   Откройте `.env` и вставьте ваш токен, полученный от [@BotFather](https://t.me/BotFather), в переменную `BOT_TOKEN`.

5.  **Запустите бота:**
    ```bash
    python bot.py
    ```

---

## 🇬🇧 English Description

This bot is designed to monitor any RSS feed (e.g., from auction aggregator sites, news portals, or blogs). A user adds an RSS feed URL, and the bot periodically checks it. When a new entry appears, the bot sends a notification to all subscribed users.

### ✨ Features

*   **Modular Architecture:** The logic is split into services (link management, fetching, parsing, notifications).
*   **Asynchronous Checks:** Uses `APScheduler` to periodically check links in the background without blocking the main bot process.
*   **JSON Data Storage:** Simple and straightforward data storage for users and links in JSON files with thread-safe writing operations.
*   **Robustness:** Automatic retries on network errors using the `tenacity` library.
*   **Flexible Configuration:** Key parameters (bot token, check interval) are managed via an `.env` configuration file.
*   **Subscription Management:** Users can add, view, and remove their subscriptions, as well as assign short aliases to them.
*   **Error Handling:** The bot tracks errors when accessing links and automatically deactivates "dead" feeds.

### 🚀 Setup and Launch

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/YourUsername/telegram-rss-monitor-bot-template.git
    cd telegram-rss-monitor-bot-template
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    # For Windows
    python -m venv venv
    venv\Scripts\activate
    
    # For macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure environment variables:**
    *   Rename the `.env.example` file to `.env`.
    *   Open `.env` and paste your token, obtained from [@BotFather](https://t.me/BotFather), into the `BOT_TOKEN` variable.

5.  **Run the bot:**
    ```bash
    python bot.py
    ```