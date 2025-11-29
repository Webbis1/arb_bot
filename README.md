# Arb Bot

Бот для арбитража криптовалют между различными биржами (Binance, OKX, Bitget, KuCoin, HTX).

## Требования

- Python 3.8 или выше
- Poetry (система управления зависимостями)

## Установка

1. Установите Poetry, если он еще не установлен:

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

1. Клонируйте репозиторий:

```bash
git clone https://github.com/Webbis1/arb_bot.git
cd arb_bot
```

1. Установите зависимости с помощью Poetry:

```bash
poetry install
```

## Настройка окружения

1. Создайте файл `.env` в корневой директории проекта со следующей структурой:

```plaintext
BINANCE_API_KEY=your_binance_api_key
BINANCE_API_SECRET=your_binance_api_secret

OKX_API_KEY=your_okx_api_key
OKX_API_SECRET=your_okx_api_secret
OKX_PASSWORD=your_okx_password

BITGET_API_KEY=your_bitget_api_key
BITGET_API_SECRET=your_bitget_api_secret
BITGET_PASSWORD=your_bitget_password

KUCOIN_API_KEY=your_kucoin_api_key
KUCOIN_API_SECRET=your_kucoin_api_secret
KUCOIN_PASSWORD=your_kucoin_password

HTX_API_KEY=your_htx_api_key
HTX_API_SECRET=your_htx_api_secret
```

## Запуск

Для запуска бота используйте команду:

```bash
poetry run python -m src.app
```

## Структура проекта

```plaintext
arb_bot/
├── src/
│   ├── app/
│   │   ├── __main__.py    # Точка входа
│   │   └── config.py      # Конфигурация и загрузка API ключей
│   └── core/
│       ├── entities/      # Основные сущности
│       │   └── ExFactory.py
│       └── models/        # Модели данных
│           └── Coin.py    # Класс для работы с монетами
├── tests/                 # Тесты
├── .env                   # Файл с API ключами (не включается в git)
├── pyproject.toml        # Конфигурация Poetry и зависимости
└── README.md
```

## Разработка

1. Создайте виртуальное окружение Poetry:

```bash
poetry shell
```

1. Запустите тесты:

```bash
poetry run pytest
```

## Важно

- Не включайте файл `.env` в систему контроля версий
- Храните API ключи в безопасном месте
- Регулярно обновляйте зависимости: `poetry update`

## Лицензия

MIT