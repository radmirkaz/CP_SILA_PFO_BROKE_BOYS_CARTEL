# ЦП ПФО Кейс от "Сила" | Broke Boys Cartel

Retrieval-Augmented Generation (RAG) для ответов на вопросы на основе текстовой базы данных. Ниже описаны инструкции по запуску системы RAG и Telegram бота.

Весь код продукоментирован, если есть какие то вопросы, пишите нам в телеграм (@radmirkaz)

Все отвеченные вопросы лучшей моделью находятся в файле **answers.docx**

БОТ захосчен по ссылке https://t.me/hackatonsilabot (Доступен до награждения)

## Установка зависимостей
Рекомендуется использовать Linux с GPU, но проект также поддерживается на macOS и WSL2.

1. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/radmirkaz/CP_SILA_PFO_BROKE_BOYS_CARTEL.git
   cd CP_SILA_PFO_BROKE_BOYS_CARTEL
   ```

2. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

## Запуск RAG

Для запуска RAG-системы доступны два варианта:
1. **Запуск через `main.py`**:
   ```bash
   python main.py
   ```

2. **Запуск в Jupyter Notebook**:
   Откройте и выполните ячейки в `demo.ipynb`, чтобы запустить систему и протестировать её.

## Запуск Telegram Бота

Бот может работать через локальный сервер с публичным доступом с помощью `ngrok` или без него.

### Запуск через `ngrok`
1. **Консоль 1**:
    ```bash
    cd tgbot
    python bot.py
    ```

2. **Консоль 2**:
    ```bash
    uvicorn api:app --port 1337
    ```

3. **Консоль 3**:
    ```bash
    ngrok http 1337 --domain=your-custom-domain.ngrok-free.app
    ```
    > Примечание: замените `your-custom-domain.ngrok-free.app` на домен, привязанный к вашему `ngrok` аккаунту. Также измените URL на строке 49 в файле `bot.py` на этот новый домен.

### Запуск без `ngrok` (на localhost)
Если публичный доступ не требуется, используйте localhost. Измените строку 49 в файле `bot.py` на `http://127.0.0.1:1337/predict`.

**Запуск сервера**:
1. Выполните шаги 1 и 2, описанные выше (Консоль 1 и Консоль 2).
