from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import logging
import time

logger = logging.getLogger("matchbot")

def sofascore_selenium_parse(league_slug: str, date_iso: str):
    """
    Парсим SofaScore через Selenium, если API вернул 403 или не дал матчей.
    """
    try:
        url = f"https://www.sofascore.com/{league_slug}/matches/{date_iso}"
        logger.info(f"SOFA-Selenium: loading {url}")

        # Настройки Chrome
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--log-level=3")

        # Правильный способ инициализации драйвера
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )

        driver.get(url)

        # Ждём пока появятся матчи
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a[href*='/match/']"))
        )

        time.sleep(2)

        matches = []
        match_elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='/match/']")

        for el in match_elements:
            try:
                text = el.text.strip()
                if text:
                    matches.append(text)
            except:
                continue

        driver.quit()

        logger.info(f"SOFA-Selenium: найдено матчей = {len(matches)}")
        return matches

    except Exception as e:
        logger.error(f"Selenium fallback failed: {e}")
        return []
