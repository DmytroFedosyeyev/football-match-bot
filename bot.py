import logging
from datetime import date, timedelta, datetime
import requests
from bs4 import BeautifulSoup
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import time

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
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
API_KEY = os.environ.get('API_KEY')

if not TELEGRAM_TOKEN or not API_KEY:
    logger.critical("Отсутствует TELEGRAM_TOKEN или API_KEY в .env")
    raise ValueError("Необходимо задать TELEGRAM_TOKEN и API_KEY в .env")

# Список лиг с кодами
LEAGUES = {
    '🏴 Англия (Premier League)': 'PL',
    '🇪🇸 Испания (La Liga)': 'PD',
    '🇩🇪 Германия (Bundesliga)': 'BL1',
    '🇫🇷 Франция (Ligue 1)': 'FL1',
    '🇮🇹 Италия (Serie A)': 'SA',
    '🇳🇱 Нидерланды (Eredivisie)': 'DED',
    '🇵🇹 Португалия (Primeira Liga)': 'PPL',
    '🇺🇦 Украина (Premier League)': 'UPL',
    '🇧🇪 Бельгия (Pro League)': 'BPD',
    '🏴 Шотландия (Premiership)': 'SPL'
}

bot = telebot.TeleBot(TELEGRAM_TOKEN)
user_state = {}


def create_leagues_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False, row_width=2)
    buttons = [KeyboardButton(league) for league in LEAGUES.keys()]
    keyboard.add(*buttons)
    return keyboard


def create_date_keyboard():
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
    if league_code == "UPL":
        return fetch_upl_fixtures(match_date)
    else:
        return fetch_api_fixtures(league_code, match_date)


def fetch_api_fixtures(league_code: str, match_date: str) -> str:
    """Получает расписание матчей через Football-Data.org API"""
    logger.info(f"API-запрос: лига={league_code}, дата={match_date}")
    url = f'https://api.football-data.org/v4/competitions/{league_code}/matches?dateFrom={match_date}&dateTo={match_date}'
    headers = {'X-Auth-Token': API_KEY}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        matches = data.get('matches', [])

        if not matches:
            return f"⚽ На {match_date} нет матчей в этой лиге."

        result = f"📅 Расписание матчей на {match_date}:\n\n"
        for match in matches:
            home = match['homeTeam']['name']
            away = match['awayTeam']['name']
            time_utc = match['utcDate'][11:16]
            status = match['status']
            result += f"🏟️ {home} vs {away}\n🕒 Время (UTC): {time_utc}\n📊 Статус: {status}\n\n"

        return result
    except requests.RequestException as e:
        logger.error(f"Ошибка API: {e}")
        return "❌ Ошибка при получении данных. Попробуйте позже."


def fetch_upl_fixtures(match_date: str) -> str:
    """Парсит расписание матчей УПЛ с flashscore.com.ua через Selenium"""
    logger.info(f"Парсим УПЛ на {match_date} с flashscore.com.ua через Selenium")
    url = "https://www.flashscore.com.ua/football/ukraine/premier-league/fixtures/"

    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        logger.info(f"Страница загружена, URL: {url}")

        soup = BeautifulSoup(driver.page_source, "html.parser")
        driver.quit()

        result = f"📅 Расписание УПЛ на {match_date}:\n\n"
        matches = soup.find_all("div", class_="event__match")
        logger.info(f"Найдено матчей: {len(matches)}")

        found = False
        for match in matches:
            # Извлечение даты и времени
            time_div = match.find("div", class_="event__time")
            if time_div:
                date_time_str = time_div.text.strip()
                logger.info(f"Обрабатываем матч, date_time_str={date_time_str}")

                # Парсинг даты и времени
                parts = date_time_str.split(' ')
                if len(parts) != 2:
                    logger.warning(f"Неверный формат даты: {date_time_str}")
                    continue

                date_str, time_str = parts
                date_str = date_str.replace('.', '')

                try:
                    site_date = f"2025-{date_str[2:4]}-{date_str[0:2]}"
                    logger.info(f"Извлечённая дата: {site_date}, искомая: {match_date}")
                except IndexError:
                    logger.warning(f"Ошибка формата даты: {date_str}")
                    continue

                if site_date != match_date:
                    continue

                # Извлечение команд
                home = match.find("div", class_="event__participant--home").text.strip() if match.find("div",
                                                                                                       class_="event__participant--home") else "N/A"
                away = match.find("div", class_="event__participant--away").text.strip() if match.find("div",
                                                                                                       class_="event__participant--away") else "N/A"
                logger.info(f"Домашняя команда: {home}, Гостевая команда: {away}")

                # Извлечение статуса
                status = match.find("div", class_="event__stage").text.strip() if match.find("div",
                                                                                             class_="event__stage") else "Запланирован"
                logger.info(f"Статус: {status}")

                result += f"🏟️ {home} vs {away}\n🕒 Время: {time_str}\n📊 Статус: {status}\n\n"
                found = True
            else:
                logger.warning("Пропущен матч: нет event__time")

        if not found:
            logger.info(f"Матчи УПЛ на {match_date} не найдены")
            return f"⚽ На {match_date} нет матчей УПЛ."

        return result
    except Exception as e:
        logger.error(f"Неожиданная ошибка в fetch_upl_fixtures: {e}")
        return "❌ Ошибка при получении данных УПЛ."


@bot.message_handler(commands=['start', 'help'])
def handle_start_help(message):
    user_state[message.chat.id] = {}
    welcome_text = (
        "⚽ Добро пожаловать в Football Schedule Bot!\n"
        "Выберите лигу, затем выберите дату.\n\n"
        "Команды:\n/start - Начать\n/help - Показать помощь"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=create_leagues_keyboard())


@bot.message_handler(func=lambda message: message.text in LEAGUES)
def handle_league_selection(message):
    user_state[message.chat.id] = {'league': message.text}
    bot.send_message(
        message.chat.id,
        f"Вы выбрали {message.text}. Теперь выберите дату:",
        reply_markup=create_date_keyboard()
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('date_'))
def handle_date_selection(call):
    chat_id = call.message.chat.id
    if chat_id not in user_state or 'league' not in user_state[chat_id]:
        bot.answer_callback_query(call.id, "Сначала выберите лигу!")
        return

    league_name = user_state[chat_id]['league']
    league_code = LEAGUES[league_name]
    match_date = call.data.split('_')[1]

    fixtures_info = fetch_fixtures(league_code, match_date)
    bot.send_message(chat_id, fixtures_info)
    bot.answer_callback_query(call.id)
    bot.send_message(chat_id, "Выберите другую лигу или дату:", reply_markup=create_leagues_keyboard())


@bot.message_handler(func=lambda message: True)
def handle_unknown(message):
    bot.send_message(message.chat.id, "Пожалуйста, выберите лигу из меню или используйте /start.")


if __name__ == '__main__':
    logger.info("Запуск бота...")
    try:
        bot.infinity_polling()
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}")