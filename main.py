import os
import platform
import random
import time

import vk_api
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from vk_api.utils import get_random_id

from constants import KEYWORD, LOCATION, MAX_SEARCH_PAGES, SEARCH_URL
from database import init_db, is_vacancy_processed, save_vacancy

load_dotenv()


def search_vacancy(html_content, target_location, global_count):
    """Поиск вакансий по KEYWORD с фильтрацией по LOCATION или удаленке."""
    soup = BeautifulSoup(html_content, features='lxml')
    vacancy_all_cards = soup.find_all(
        "article", attrs={"data-qa": "vacancy-serp__vacancy"}
    )
    count = 0
    print(f"📦 Всего на странице обнаружено вакансий: {len(vacancy_all_cards)}")
    for vac in vacancy_all_cards:
        title_link = vac.find("a", attrs={"data-qa": "serp-item__title"})
        if not title_link:
            continue
        title_text = title_link.get_text(strip=True)
        job_url = title_link.get("href")
        if is_vacancy_processed(job_url):
            print(f"⏭️ Пропуск (уже в базе): {title_text}")
            continue
        if KEYWORD.lower() not in title_text.lower():
            continue
        desc_tag = vac.find("div", attrs={"data-qa": "vacancy-serp__vacancy_snippet_responsibility"})
        description = desc_tag.get_text(strip=True) if desc_tag else "Описание не найдено"
        exp_tag = vac.find(
            "data", attrs={"data-qa": lambda x: x and "work-experience" in x}
        )
        if exp_tag:
            exp_qa = exp_tag.get("data-qa", "").lower()
            exp_text = exp_tag.get_text(strip=True)
        else:
            exp_qa = ""
            exp_text = "Не указан"
        exp_text_lower = exp_text.lower()
        is_no_experience = "noexperience" in exp_qa or "без опыта" in exp_text_lower
        is_1_to_3_years = (
            "between1and3" in exp_qa or
            "1-3" in exp_text_lower or
            "от 1 года" in exp_text_lower or
            "1 год" in exp_text_lower
        )
        if not (is_no_experience or is_1_to_3_years):
            continue
        city_tag = vac.find("span", attrs={"data-qa": "vacancy-serp__vacancy-address"})
        city_text = city_tag.get_text(strip=True).lower() if city_tag else "неизвестный город"
        remote_tag = vac.find("span", attrs={"data-qa": "vacancy-label-work-schedule-remote"})
        is_remote = remote_tag is not None
        if not is_remote:
            remote_text = vac.get_text().lower()
            is_remote = any(word in remote_text for word in ["можно удалённо", "удаленная работа", "удалённо"])
        is_location_match = target_location.lower() in city_text
        is_suitable = is_remote or is_location_match
        if not is_suitable:
            print(f"⏭️ Пропуск (локация): {title_text} | Город: {city_text} | Удалёнка: {'Да' if is_remote else 'Нет'}")
            continue
        count += 1
        global_count += 1
        work_text = "Можно удалённо" if is_remote else "Офис"
        send_to_vk(global_count, title_text, job_url, exp_text, work_text, city_text, description)
        save_vacancy(job_url)
    print(f"\n На этой странице найдено: {count} | Всего: {global_count}")
    return global_count


def send_to_vk(count, title_text, job_url, exp_text, work_text, city_text, description):
    token = os.getenv("VK_TOKEN")
    user_id = os.getenv("VK_USER_ID")
    if not token or not user_id:
        print("⚠️ VK_TOKEN или VK_USER_ID не найдены в .env. Отправка в VK пропущена.")
    else:
        try:
            session = vk_api.VkApi(token=token)
            vk = session.get_api()
            message_text = (
                f"✅ НАЙДЕНА ВАКАНСИЯ #{count}\n"
                f"📌 Название: {title_text}\n"
                f"🔗 Ссылка: {job_url}\n"
                f"💼 Опыт: {exp_text}\n"
                f"🏢 Формат: {work_text}\n"
                f"📍 Локация: {city_text.capitalize()}\n"
                f" Описание: {description[:500]}..."
            )
            vk.messages.send(
                user_id=int(user_id),
                message=message_text,
                random_id=get_random_id()
            )
            print("📩 Уведомление успешно отправлено в VK!")
        except vk_api.exceptions.ApiError as e:
            print(f"❌ Ошибка API VK: {e}")
        except Exception as e:
            print(f"❌ Неизвестная ошибка при отправке в VK: {e}")
    print(f"\n✅ НАЙДЕНА ВАКАНСИЯ #{count}")
    print(f"📌 Название: {title_text}")
    print(f" Ссылка:   {job_url}")
    print(f"💼 Опыт:     {exp_text}")
    print(f"🏢 Формат:   {work_text}")
    print(f" Локация:  {city_text.capitalize()}")
    print(f"📝 Описание: {description[:500]}...\n")


def main():
    print("🚀 Запуск браузера...")
    init_db()
    options = Options()
    # Определяем операционную систему
    is_linux = platform.system() == "Linux"
    if is_linux:
        # Настройки для Docker / Linux
        options.binary_location = os.getenv("CHROME_BIN", "/usr/bin/chromium")
        options.add_argument("--no-sandbox")  # КРИТИЧНО для Docker
        options.add_argument("--disable-dev-shm-usage")  # КРИТИЧНО для Docker (избегает ошибок памяти)
        options.add_argument("--headless=new")
    else:
        # Твои оригинальные настройки для Windows
        options.add_argument(r"--user-data-dir=C:\Users\goodw\Desktop\selenium_hh_parser\selenium_profile")
        options.add_argument("--remote-debugging-port=9222")
        options.add_argument("--headless=new") # Для работы в фоне/С открытым окном - закомментируй
        options.add_argument("--window-size=1920,1080") # Для работы в фоне/С открытым окном - закомментируй

    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    driver = webdriver.Chrome(options=options)
    # driver.maximize_window() # Для работы с открытым окном
    global_count = 0
    try:
        for page in range(MAX_SEARCH_PAGES):
            print(f"\n{'='*60}")
            print(f" Страница {page + 1} из {MAX_SEARCH_PAGES}")
            print(f"{'='*60}")
            # Формируем URL: page=0 — первая страница, page=1 — вторая и т.д.
            separator = "&" if "?" in SEARCH_URL else "?"
            page_url = f"{SEARCH_URL}{separator}page={page}"
            print(f"🌐 Переход по ссылке: {page_url}")
            driver.get(page_url)
            time.sleep(2)
            print("📜 Начинаем плавный скролл вниз...")
            for _ in range(70):
                driver.execute_script("window.scrollBy({top: 400, behavior: 'smooth'});")
                time.sleep(0.2)
            print("✅ Плавный скролл завершен!")
            time.sleep(2)
            print("\n🔍 Передаем страницу для анализа...")
            html_content = driver.page_source
            global_count = search_vacancy(html_content, LOCATION, global_count)
            # Пауза между страницами
            if page < MAX_SEARCH_PAGES - 1:
                wait = random.uniform(3, 6)
                print(f" Ждём {wait:.1f} сек перед следующей страницей...")
                time.sleep(wait)
        print(f"\n{'='*60}")
        print(f"🏁 Парсинг завершён! Всего найдено вакансий: {global_count}")
        print(f"{'='*60}")
    except Exception as e:
        print(f" Произошла ошибка: {e}")
    finally:
        print("🛑 Закрытие браузера...")
        driver.quit()


if __name__ == "__main__":
    main()
