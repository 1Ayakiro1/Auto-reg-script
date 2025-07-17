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

def save_mail_credentials(login, password, user_mail_profile):
    """Сохраняет логин и пароль в credentials.txt с правами только для владельца."""
    creds_path = os.path.join(user_mail_profile, 'credentials.txt')
    with open(creds_path, 'w') as f:
        f.write(f'{login}:{password}')
    os.chmod(creds_path, 0o600)
    logger.info(f'Данные почты сохранены в {creds_path}')

def setup_mail_profile(login):
    """Создаёт директорию для хранения профиля и куков почты."""
    mail_cookies_dir = os.path.join(os.path.expanduser('~'), '.mail_cookies')
    os.makedirs(mail_cookies_dir, exist_ok=True)
    user_mail_profile = os.path.join(mail_cookies_dir, login.replace('@', '_'))
    os.makedirs(user_mail_profile, exist_ok=True)
    return user_mail_profile

def get_confirmation_code_from_mail(login, password):
    """Подключается к Rambler-почте и извлекает 6-значный код из последнего письма."""
    try:
        mail = imaplib.IMAP4_SSL('imap.rambler.ru')
        mail.login(login, password)
        mail.select('inbox')
        result, data = mail.search(None, 'ALL')
        ids = data[0].split()
        if not ids:
            logger.error('Нет писем в почтовом ящике!')
            return None
        latest_id = ids[-1]
        result, msg_data = mail.fetch(latest_id, '(RFC822)')
        msg = email.message_from_bytes(msg_data[0][1])
        # Получаем тело письма
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                cdispo = str(part.get('Content-Disposition'))
                if ctype == 'text/plain' and 'attachment' not in cdispo:
                    body = part.get_payload(decode=True).decode(errors='ignore')
                    break
        else:
            body = msg.get_payload(decode=True).decode(errors='ignore')
        code_match = re.search(r'\b\d{6}\b', body)
        if not code_match:
            logger.error('6-значный код не найден в последнем письме!')
            return None
        code = code_match.group()
        logger.info(f'Код подтверждения из почты: {code}')
        return code
    except Exception as e:
        logger.error(f'Ошибка при получении кода из почты: {e}')
        import traceback; traceback.print_exc()
        return None

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
    wait = WebDriverWait(driver, 20)
    try:
        logger.info('Ожидание поля для ввода кода подтверждения...')
        code_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text']")))
        logger.info('Ввожу код подтверждения...')
        human_type(code_input, code)
        logger.info('Код подтверждения введён.')
        return True
    except Exception as e:
        logger.error(f'Не удалось ввести код подтверждения: {e}')
        import traceback; traceback.print_exc()
        return False

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

def main():
    # Получение логина и пароля пользователя
    creds = input("Введите логин и пароль через двоеточие (login:password): ")
    if ':' not in creds:
        logger.error('Ошибка: используйте формат login:password')
        exit(1)
    login, password = creds.split(':', 1)

    # Настройка профиля для kick.com
    user_data_dir = os.path.join(os.path.expanduser('~'), '.kickcom_profile')
    os.makedirs(user_data_dir, exist_ok=True)
    options = uc.ChromeOptions()
    options.add_argument('--start-maximized')
    options.add_argument(f'--user-data-dir={user_data_dir}')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-infobars')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    driver = uc.Chrome(options=options, use_subprocess=True)
    actions = ActionChains(driver)

    # Настройка и сохранение профиля почты
    user_mail_profile = setup_mail_profile(login)
    save_mail_credentials(login, password, user_mail_profile)

    try:
        # Авторизация на kick.com
        if not authorize_on_kick(driver, actions, login, password):
            return
        # Получение кода подтверждения из почты
        logger.info('Пытаюсь получить код подтверждения из почты...')
        code = get_confirmation_code_from_mail(login, password)
        if not code:
            return
        # Ввод кода подтверждения на сайте
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

if __name__ == '__main__':
    main()
