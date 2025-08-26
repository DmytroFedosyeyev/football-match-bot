import logging
from datetime import date, timedelta
import requests
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import os

# Загрузка переменных из .env
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler('bot_debug.log')]
)
logger = logging.getLogger(__name__)

# Константы
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')  # Токен от BotFather
API_KEY = os.environ.get('API_KEY')  # Ключ от Football-Data.org

# Проверка наличия ключей
if not TELEGRAM_TOKEN or not API_KEY:
    logger.critical("Отсутствует TELEGRAM_TOKEN или API_KEY в .env")
    raise ValueError("Необходимо задать TELEGRAM_TOKEN и API_KEY в .env")

# Список лиг с кодами Football-Data.org
LEAGUES = {
    '🏴󠁧󠁢󠁥󠁮󠁧󠁿 Англия (Premier League)': 'PL',
    '🇪🇸 Испания (La Liga)': 'PD',
    '🇩🇪 Германия (Bundesliga)': 'BL1',
    '🇫🇷 Франция (Ligue 1)': 'FL1',
    '🇮🇹 Италия (Serie A)': 'SA',
    '🇳🇱 Нидерланды (Eredivisie)': 'DED',
    '🇵🇹 Португалия (Primeira Liga)': 'PPL',
    '🇺🇦 Украина (Premier League)': 'UPL',
    '🇧🇪 Бельгия (Pro League)': 'BPD',
    '🏴󠁧󠁢󠁳󠁣󠁴󠁿 Шотландия (Premiership)': 'SPL'
}

bot = telebot.TeleBot(TELEGRAM_TOKEN)
user_state = {}

def create_leagues_keyboard():
    """Создаёт клавиатуру с лигами."""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False, row_width=2)
    buttons = [KeyboardButton(league) for league in LEAGUES.keys()]
    keyboard.add(*buttons)
    return keyboard

def create_date_keyboard():
    """Создаёт инлайн-клавиатуру для выбора даты."""
    keyboard = InlineKeyboardMarkup(row_width=2)
    today = date.today().strftime('%Y-%m-%d')
    tomorrow = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    keyboard.add(
        InlineKeyboardButton("Сегодня", callback_data=f"date_{today}"),
        InlineKeyboardButton("Завтра", callback_data=f"date_{tomorrow}")
    )
    return keyboard

def fetch_fixtures(league_code: str, match_date: str) -> str:
    """Получает расписание матчей для указанной лиги и даты."""
    logger.info(f"Запрос расписания: лига={league_code}, дата={match_date}")
    url = f'http://api.football-data.org/v4/competitions/{league_code}/matches?dateFrom={match_date}&dateTo={match_date}'
    headers = {'X-Auth-Token': API_KEY}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        matches = data.get('matches', [])
        logger.info(f"Получено {len(matches)} матчей для лиги {league_code} на {match_date}")

        if not matches:
            return f"На {match_date} нет матчей в этой лиге."

        result = f"📅 Расписание матчей на {match_date}:\n\n"
        for match in matches:
            home = match['homeTeam']['name']
            away = match['awayTeam']['name']
            time_utc = match['utcDate'][11:16]  # Время в UTC (HH:MM)
            status = match['status']
            result += f"🏟️ {home} vs {away}\n🕒 Время (UTC): {time_utc}\n📊 Статус: {status}\n\n"
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
        logger.info(f"Сообщение отправлено с клавиатурой лиг пользователю {message.chat.id}")
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
        logger.info(f"Отправлена клавиатура дат пользователю {message.chat.id}")
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
        logger.info(f"Расписание отправлено и клавиатура лиг обновлена для {chat_id}")
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