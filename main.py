import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time
import os
import random
import platform
import subprocess
import imaplib
import email
import re
import logging
import pickle
import shutil
import sqlite3
import datetime
import sys
import json
import requests
from collections import defaultdict

# === Настройка логирования ===
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# === Вспомогательные функции ===
def human_pause(min_t=0.07, max_t=0.18):
    time.sleep(random.uniform(min_t, max_t))

def human_type(element, text):
    for c in text:
        element.send_keys(c)
        human_pause()

def human_click(actions, element):
    actions.move_to_element(element).pause(random.uniform(0.1, 0.25)).click().perform()
    human_pause(0.15, 0.3)

def human_focus(actions, element):
    actions.move_to_element(element).pause(random.uniform(0.1, 0.2)).click().perform()
    human_pause(0.1, 0.2)

def authorize_on_kick(driver, actions, login, password):
    """Авторизация на сайте kick.com с имитацией действий человека."""
    wait = WebDriverWait(driver, 20)
    try:
        logger.info('Открываю сайт https://kick.com/')
        driver.get('https://kick.com/')
        logger.info('Ожидание кнопки входа...')
        login_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='login']")))
        logger.info('Кнопка входа найдена, имитирую наведение и клик...')
        human_click(actions, login_btn)
        logger.info('Ожидание поля email/username...')
        email_input = wait.until(EC.presence_of_element_located((By.NAME, 'emailOrUsername')))
        email_input.clear()
        logger.info('Навожу мышь и фокусирую поле логина')
        human_focus(actions, email_input)
        logger.info(f'Ввожу логин: {login}')
        human_type(email_input, login)
        email_input.send_keys(Keys.TAB)
        logger.info('Ожидание поля пароля...')
        password_input = wait.until(EC.presence_of_element_located((By.NAME, 'password')))
        password_input.clear()
        logger.info('Навожу мышь и фокусирую поле пароля')
        human_focus(actions, password_input)
        logger.info('Ввожу пароль (скрыто)')
        human_type(password_input, password)
        password_input.send_keys(Keys.TAB)
        logger.info('Ожидание кнопки подтверждения входа...')
        submit_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']")))
        logger.info('Навожу мышь и кликаю по кнопке подтверждения...')
        human_click(actions, submit_btn)
        logger.info('Ожидание завершения авторизации...')
        time.sleep(5)
        logger.info('Авторизация завершена.')
        return True
    except Exception as e:
        logger.error(f'Ошибка авторизации на kick.com: {e}')
        import traceback; traceback.print_exc()
        return False

def input_confirmation_code(driver, code):
    """Вводит код подтверждения на сайте kick.com."""
    wait = WebDriverWait(driver, 30)
    try:
        # После переключения на вкладку kick.com — пауза и клик по body
        time.sleep(1)
        try:
            driver.find_element(By.TAG_NAME, 'body').click()
        except Exception:
            pass
        logger.info('Ожидание поля для ввода кода подтверждения...')
        code_input = wait.until(
            EC.presence_of_element_located((
                By.CSS_SELECTOR, "input[type='text'], input[type='number'], input[name*='code'], input[autocomplete*='one-time-code']"
            ))
        )
        logger.info('Ввожу код подтверждения...')
        code_input.clear()
        code_input.send_keys(code)
        logger.info('Код подтверждения введён.')
        return True
    except Exception as e:
        logger.error(f'Не удалось ввести код подтверждения: {e}')
        # Сохраняем HTML для отладки
        try:
            with open('kick_debug.html', 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            logger.info('Сохранён HTML страницы kick_debug.html для отладки.')
        except Exception:
            pass
        import traceback; traceback.print_exc()
        return False

def save_cookies(driver, cookies_path):
    import pickle
    with open(cookies_path, 'wb') as f:
        pickle.dump(driver.get_cookies(), f)
    logger.info(f'Cookies Gmail сохранены в {cookies_path}')

def load_cookies(driver, cookies_path):
    import pickle
    with open(cookies_path, 'rb') as f:
        cookies = pickle.load(f)
    # Открываем mail.google.com
    driver.get('https://mail.google.com')
    for cookie in cookies:
        cookie.pop('sameSite', None)
        # Добавляем только куки для google.com и поддоменов
        if 'google.com' in cookie.get('domain', ''):
            try:
                driver.add_cookie(cookie)
            except Exception:
                pass
    logger.info(f'Cookies Gmail загружены из {cookies_path}')

def gmail_login_and_save_cookies(login, password, cookies_path):
    options = uc.ChromeOptions()
    options.add_argument('--start-maximized')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-infobars')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = uc.Chrome(options=options, use_subprocess=True)
    try:
        driver.get('https://mail.google.com/')
        wait = WebDriverWait(driver, 30)
        email_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[type="email"]')))
        actions = ActionChains(driver)
        actions.move_to_element(email_input).pause(0.1).click().perform()
        driver.execute_script("arguments[0].focus();", email_input)
        time.sleep(0.2)
        email_input.clear()
        try:
            human_type(email_input, login)
        except Exception:
            email_input.send_keys(login)
        next_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '#identifierNext')))
        human_click(ActionChains(driver), next_btn)
        password_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[type="password"]')))
        actions = ActionChains(driver)
        actions.move_to_element(password_input).pause(0.1).click().perform()
        driver.execute_script("arguments[0].focus();", password_input)
        time.sleep(0.2)
        password_input.clear()
        try:
            human_type(password_input, password)
        except Exception:
            password_input.send_keys(password)
        next_btn2 = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '#passwordNext')))
        human_click(ActionChains(driver), next_btn2)
        # Ждём загрузки почты
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="main"]')))
        logger.info('Вход в Gmail выполнен.')
        save_cookies(driver, cookies_path)
        input('Почта открыта. Нажмите Enter для выхода...')
    except Exception as e:
        logger.error(f'Ошибка входа в Gmail: {e}')
        import traceback; traceback.print_exc()
    finally:
        driver.quit()

def gmail_login_with_cookies(cookies_path):
    options = uc.ChromeOptions()
    options.add_argument('--start-maximized')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-infobars')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = uc.Chrome(options=options, use_subprocess=True)
    try:
        driver.get('https://mail.google.com/')
        if os.path.exists(cookies_path):
            load_cookies(driver, cookies_path)
            driver.refresh()
            time.sleep(3)
            # Проверяем, залогинен ли пользователь (по наличию inbox)
            try:
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="main"]')))
                logger.info('Вход в Gmail по cookies выполнен.')
                input('Почта открыта по cookies. Нажмите Enter для выхода...')
            except Exception:
                print('Cookies невалидны или сессия истекла. Войдите вручную для обновления cookies.')
                driver.quit()
                return False
        else:
            print('Файл cookies не найден. Войдите вручную для их создания.')
            driver.quit()
            return False
    except Exception as e:
        logger.error(f'Ошибка входа в Gmail по cookies: {e}')
        import traceback; traceback.print_exc()
    finally:
        driver.quit()
    return True

def open_linux_terminal():
    """Открывает терминал Linux после завершения работы скрипта."""
    if platform.system().lower() == 'linux':
        logger.info('Открываю терминал Linux...')
        for term in ['gnome-terminal', 'xterm', 'konsole']:
            try:
                subprocess.Popen([term])
                break
            except FileNotFoundError:
                continue

def get_confirmation_code_from_gmail_selenium(driver, gmail_login, gmail_password):
    logger.info('Открываю новую вкладку для Gmail...')
    try:
        driver.switch_to.new_window('tab')
        logger.info(f'Переключаюсь на новую вкладку: {driver.current_window_handle}')
    except Exception:
        logger.info('driver.switch_to.new_window не поддерживается, fallback на window.open')
        old_tabs = driver.window_handles
        driver.execute_script("window.open('about:blank', '_blank');")
        time.sleep(1)
        new_tabs = driver.window_handles
        new_tab = [h for h in new_tabs if h not in old_tabs][0]
        driver.switch_to.window(new_tab)
        logger.info(f'Переключаюсь на новую вкладку: {new_tab}')
    # Используем только официальный короткий URL для входа в Gmail
    login_url = 'https://accounts.google.com/signin/v2/identifier?service=mail'
    driver.get(login_url)
    wait = WebDriverWait(driver, 30)
    # Вводим логин
    email_input = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[type="email"]')))
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[type="email"]')))
    email_input.clear()
    email_input.send_keys(gmail_login)
    next_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '#identifierNext')))
    human_click(ActionChains(driver), next_btn)
    # Вводим пароль
    password_input = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[type="password"]')))
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[type="password"]')))
    password_input.clear()
    password_input.send_keys(gmail_password)
    next_btn2 = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '#passwordNext')))
    human_click(ActionChains(driver), next_btn2)
    # Ждём загрузки почты
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="main"]')))
    time.sleep(2)
    # Ждём появления хотя бы одного письма
    try:
        mail_rows = WebDriverWait(driver, 60).until(lambda d: d.find_elements(By.CSS_SELECTOR, 'tr.zA'))
        first_mail_row = mail_rows[0]
        first_mail_row.click()
        time.sleep(2)
        # Пробуем взять код из темы письма
        try:
            subject_elem = driver.find_element(By.CSS_SELECTOR, 'h2.hP')
            subject_text = subject_elem.text
            code_match = re.search(r'\b\d{6}\b', subject_text)
            if code_match:
                code = code_match.group()
                logger.info(f'Код подтверждения из темы письма: {code}')
                return code
        except Exception:
            pass
        # Если не нашли — ищем в теле письма
        mail_body = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.a3s')))
        body_text = mail_body.text
        code_match = re.search(r'\b\d{6}\b', body_text)
        if code_match:
            code = code_match.group()
            logger.info(f'Код подтверждения из тела письма: {code}')
            return code
        else:
            logger.error('6-значный код не найден ни в теме, ни в теле письма!')
            return None
    except Exception as e:
        logger.error(f'Ошибка при поиске письма или кода: {e}')
        import traceback; traceback.print_exc()
        return None

def main():
    while True:
        print('1. Зарегистрировать аккаунт на kick.com (и получить код с Gmail через браузер)')
        print('0. Выход')
        mode = input('Выберите режим (0/1): ')
        if mode == '1':
            creds = input("Введите логин и пароль через двоеточие (login:password): ")
            if ':' not in creds:
                logger.error('Ошибка: используйте формат login:password')
                continue
            login, password = creds.split(':', 1)
            options = uc.ChromeOptions()
            options.add_argument('--start-maximized')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-infobars')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            driver = uc.Chrome(options=options, use_subprocess=True)
            actions = ActionChains(driver)
            try:
                # Вкладка 1: kick.com
                if not authorize_on_kick(driver, actions, login, password):
                    return
                logger.info('Открываю Gmail во второй вкладке для получения кода...')
                code = get_confirmation_code_from_gmail_selenium(driver, login, password)
                if not code:
                    return
                # Переключаемся обратно на kick.com
                driver.switch_to.window(driver.window_handles[0])
                if not input_confirmation_code(driver, code):
                    return
                logger.info('Все этапы успешно завершены. Проверьте браузер.')
                input('Нажмите Enter для выхода...')
            except Exception as e:
                logger.critical(f'Необработанная ошибка: {e}')
                import traceback; traceback.print_exc()
            finally:
                driver.quit()
                open_linux_terminal()
        elif mode == '0':
            print('Выход. До свидания!')
            break
        else:
            print('Некорректный выбор. Введите 0 или 1.')

if __name__ == '__main__':
    main()
