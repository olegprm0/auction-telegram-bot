# 🏛️ Аукционный Telegram Бот

Полнофункциональный аукционный бот для Telegram с веб-панелью управления и автоматическими ставками.

## 🚀 Возможности

### Для пользователей:

- 📦 Участие в аукционах с автоматическими ставками
- 💰 Прогрессивная система ставок
- 🔔 Уведомления о перебитых ставках
- 📱 Удобный интерфейс в Telegram
- 📄 Автоматическая генерация документов передачи прав
авоыовыдаыаываыва
### Для продавцов:

- 🛍️ Создание лотов с изображениями и файлами
- 📊 Управление аукционами через веб-панель
- 💳 Интеграция с платежными системами
- 📈 Аналитика и статистика

### Для администраторов:

- 🔧 Полная панель управления
- 👥 Модерация пользователей и лотов
- 🛡️ Система безопасности и блокировок

## 🏗️ Архитектура

```
ПРОЕКТ/
├── bot/                    # Telegram бот
│   ├── handlers/          # Обработчики команд
│   ├── utils/             # Утилиты и хелперы
│   └── templates/         # Шаблоны документов
├── management/            # Веб-панель управления
│   ├── views/            # Интерфейсы
│   ├── core/             # Основная логика
│   └── ui/               # UI файлы
├── database/             # База данных
│   ├── models.py         # Модели данных
│   └── repositories/     # Репозитории
├── config/               # Конфигурация
└── media/               # Медиа файлы
```

## 🛠️ Технологии

- **Backend**: Python 3.8+
- **Framework**: aiogram (Telegram Bot API)
- **Database**: SQLAlchemy + SQLite
- **Web UI**: PyQt5
- **Notifications**: Telegram Bot API

## 📦 Установка

1. **Клонируйте репозиторий:**

```bash
git clone https://github.com/your-username/auction-bot.git
cd auction-bot
```

2. **Установите зависимости:**

```bash
pip install -r requirements.txt
```

3. **Настройте конфигурацию:**

```bash
# Скопируйте и отредактируйте config/settings.py
cp config/settings.py.example config/settings.py
```

4. **Настройте переменные окружения:**

```bash
# Создайте файл .env
BOT_TOKEN=your_telegram_bot_token
TELEGRAM_GROUP_ID=your_channel_id
```

5. **Инициализируйте базу данных:**

```bash
python -c "from database.db import init_db; init_db()"
```

## 🚀 Запуск

### Telegram Bot:

```bash
python run.py
```

### Web Management Panel:

```bash
python management/main.py
```

## 📋 Конфигурация

Основные настройки в `config/settings.py`:

- `BOT_TOKEN` - токен Telegram бота
- `TELEGRAM_GROUP_ID` - ID канала для публикации лотов
- `TELEGRAM_API_TIMEOUT` - таймаут API запросов
- `TELEGRAM_RETRY_DELAY` - задержка между повторными попытками

## 🔧 Разработка

### Структура проекта:

- `bot/handlers/` - обработчики команд бота
- `bot/utils/` - утилиты и хелперы
- `management/views/` - интерфейсы веб-панели
- `database/models.py` - модели данных
- `config/` - конфигурация

### Добавление новых функций:

1. Создайте обработчик в `bot/handlers/`
2. Добавьте модель в `database/models.py` если нужно
3. Обновите веб-панель в `management/views/`
4. Добавьте тесты в `tests/`

## 🔒 Безопасность

- Валидация всех входных данных
- Защита от SQL-инъекций
- Система блокировок пользователей
- Безопасное хранение токенов
- Логирование подозрительной активности

## 📝 Лицензия

MIT License - см. файл [LICENSE](LICENSE)

## 🤝 Вклад в проект

1. Форкните репозиторий
2. Создайте ветку для новой функции
3. Внесите изменения
4. Добавьте тесты
5. Создайте Pull Request

## 📞 Поддержка

- 📧 Email: lanthe421@gmail.com
- 💬 Telegram: @artem_smirnov52
- 🐛 Issues: [GitHub Issues](https://github.com/lanthe421/auction-telegram-bot/issues)

---

⭐ Если проект вам понравился, поставьте звездочку!
