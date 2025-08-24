import logging
from datetime import date, timedelta
import requests
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler('bot_debug.log')]
)
logger = logging.getLogger(__name__)

# Константы
TELEGRAM_TOKEN = '8151541901:AAGnxY97wkYdGEVtmqy8JZmWJkT4JA13pEU'  # Токен от BotFather
API_KEY = 'cb415bb6e8054319b1b88077e16b0361'  # Ключ от Football-Data.org

# Список лиг с кодами Football-Data.org
LEAGUES = {
    '🏴󠁧󠁢󠁥󠁮󠁧󠁿 Англия (Premier League)': 'PL',
    '🇪🇸 Испания (La Liga)': 'PD',
    '🇩🇪 Германия (Bundesliga)': 'BL1',
    '🇫🇷 Франция (Ligue 1)': 'FL1',
    '🇮🇹 Италия (Serie A)': 'SA',
    '🇳🇱 Нидерланды (Eredivisie)': 'DED',
    '🇵🇹 Португалия (Primeira Liga)': 'PPL',
    '🇷🇺 Россия (Premier League)': 'RPL',
    '🇧🇪 Бельгия (Pro League)': 'BPD',
    '🏴󠁧󠁢󠁳󠁣󠁴󠁿 Шотландия (Premiership)': 'SPL'
}

bot = telebot.TeleBot(TELEGRAM_TOKEN)
user_state = {}


def create_leagues_keyboard():
    """Создаёт клавиатуру с лигами."""
    logger.debug("Создание клавиатуры лиг...")
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False, row_width=2)
    buttons = [KeyboardButton(league) for league in LEAGUES.keys()]
    keyboard.add(*buttons)
    logger.debug(f"Клавиатура создана с кнопками: {list(LEAGUES.keys())}")
    return keyboard


def create_date_keyboard():
    """Создаёт инлайн-клавиатуру для выбора даты."""
    logger.debug("Создание клавиатуры дат...")
    keyboard = InlineKeyboardMarkup(row_width=2)
    today = date.today().strftime('%Y-%m-%d')
    tomorrow = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    keyboard.add(
        InlineKeyboardButton("Сегодня", callback_data=f"date_{today}"),
        InlineKeyboardButton("Завтра", callback_data=f"date_{tomorrow}")
    )
    logger.debug(f"Клавиатура дат создана: Сегодня ({today}), Завтра ({tomorrow})")
    return keyboard


def fetch_fixtures(league_code: str, match_date: str) -> str:
    """Получает расписание матчей для указанной лиги и даты."""
    logger.debug(f"Запрос расписания: лига={league_code}, дата={match_date}")
    url = f'http://api.football-data.org/v4/competitions/{league_code}/matches?dateFrom={match_date}&dateTo={match_date}'
    headers = {'X-Auth-Token': API_KEY}

    # Словарь для перевода статусов
    status_translation = {
        'TIMED': 'Запланирован',
        'SCHEDULED': 'Запланирован',
        'LIVE': 'Идёт',
        'IN_PLAY': 'В процессе',
        'PAUSED': 'Перерыв',
        'FINISHED': 'Завершён',
        'POSTPONED': 'Отложен',
        'CANCELLED': 'Отменён'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        logger.debug(f"API ответ: {data.get('matches', 'Нет данных')}")

        matches = data.get('matches', [])
        if not matches:
            return f"На {match_date} нет матчей в этой лиге."

        result = f"📅 Расписание матчей на {match_date}:\n\n"
        for match in matches:
            home = match['homeTeam']['name']
            away = match['awayTeam']['name']
            time_utc = match['utcDate'][11:16]  # Время в UTC (HH:MM)
            status = match['status']
            status_rus = status_translation.get(status, status)  # Перевод статуса
            result += f"🏟️ {home} vs {away}\n🕒 Время (UTC): {time_utc}\n📊 Статус: {status_rus}\n"

            # Добавляем счёт для завершённых матчей
            if status == 'FINISHED':
                score = match['score']['fullTime']
                home_score = score['home'] if score['home'] is not None else '-'
                away_score = score['away'] if score['away'] is not None else '-'
                result += f"⚽ Счёт: {home_score} - {away_score}\n"

            result += "\n"
        return result

    except requests.RequestException as e:
        logger.error(f"Ошибка API: {e}")
        return "Ошибка при получении данных. Попробуйте позже."
    except Exception as e:
        logger.error(f"Неожиданная ошибка в fetch_fixtures: {e}")
        return "Произошла ошибка. Попробуйте снова."


@bot.message_handler(commands=['start', 'help'])
def handle_start_help(message):
    """Обработчик команд /start и /help."""
    logger.info(f"Обработка /start или /help от пользователя {message.chat.id}")
    user_state[message.chat.id] = {}
    welcome_text = (
        "⚽ Добро пожаловать в Football Schedule Bot!\n"
        "Выберите лигу из списка ниже, чтобы узнать расписание матчей.\n"
        "После выбора лиги выберите дату: сегодня или завтра.\n\n"
        "Команды:\n/start - Начать\n/help - Показать помощь"
    )
    try:
        bot.send_message(message.chat.id, welcome_text, reply_markup=create_leagues_keyboard())
        logger.debug(f"Сообщение отправлено с клавиатурой лиг пользователю {message.chat.id}")
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения с клавиатурой: {e}")


@bot.message_handler(func=lambda message: message.text in LEAGUES)
def handle_league_selection(message):
    """Обработчик выбора лиги."""
    logger.info(f"Выбор лиги '{message.text}' от пользователя {message.chat.id}")
    user_state[message.chat.id] = {'league': message.text}
    try:
        bot.send_message(
            message.chat.id,
            f"Вы выбрали {message.text}. Теперь выберите дату:",
            reply_markup=create_date_keyboard()
        )
        logger.debug(f"Отправлена клавиатура дат пользователю {message.chat.id}")
    except Exception as e:
        logger.error(f"Ошибка отправки клавиатуры дат: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('date_'))
def handle_date_selection(call):
    """Обработчик выбора даты."""
    chat_id = call.message.chat.id
    logger.info(f"Выбор даты от пользователя {chat_id}")
    if chat_id not in user_state or 'league' not in user_state[chat_id]:
        bot.answer_callback_query(call.id, "Сначала выберите лигу!")
        logger.warning(f"Попытка выбора даты без лиги от {chat_id}")
        return

    league_name = user_state[chat_id]['league']
    league_code = LEAGUES[league_name]
    match_date = call.data.split('_')[1]

    fixtures_info = fetch_fixtures(league_code, match_date)
    try:
        bot.send_message(chat_id, fixtures_info)
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "Выберите другую лигу или дату:", reply_markup=create_leagues_keyboard())
        logger.debug(f"Расписание отправлено и клавиатура лиг обновлена для {chat_id}")
    except Exception as e:
        logger.error(f"Ошибка отправки расписания: {e}")


@bot.message_handler(func=lambda message: True)
def handle_unknown(message):
    """Обработчик неизвестных сообщений."""
    logger.warning(f"Неизвестное сообщение '{message.text}' от {message.chat.id}")
    bot.send_message(message.chat.id, "Пожалуйста, выберите лигу из меню или используйте /start.")


if __name__ == '__main__':
    logger.info("Запуск бота...")
    try:
        bot.infinity_polling()
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}")