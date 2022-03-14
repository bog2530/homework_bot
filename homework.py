import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exception import BotTaskError

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    level=logging.INFO,
    filename='bot.log',
    filemode='a',
)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 60 * 9
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
}


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logging.info(f'Сообщение отправлено: {message}')
    except telegram.error.TelegramError as error:
        raise BotTaskError(f'Ошибка: {error}. При отправке: {message}.')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинта API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        logging.info(response.status_code)
        if response.status_code != HTTPStatus.OK:
            raise BotTaskError(response.status_code)
        return response.json()
    except Exception as error:
        raise BotTaskError(f'API недоступно: {error}.')


def check_response(response):
    """Проверяет ответ API на корректность."""
    if response is None:
        message = 'Нет данных от API.'
        raise TypeError(message)
    if not isinstance(response, dict):
        message = 'Ответ API не является словарем.'
        raise TypeError(message)
    homeworks = response.get('homeworks')
    if homeworks is None:
        message = 'Нет списка домашних работ.'
        raise BotTaskError(message)
    if not isinstance(homeworks, list):
        message = 'Homework Не является списком.'
        raise BotTaskError(message)
    return homeworks


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_name is None:
        message = 'Отсутствует название работы.'
        raise KeyError(message)
    verdict = HOMEWORK_STATUSES.get(homework_status)
    if verdict is None:
        message = 'Отсутствует статус работы.'
        raise KeyError(message)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if (TELEGRAM_TOKEN and PRACTICUM_TOKEN and TELEGRAM_CHAT_ID) is None:
        return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        message = 'Отсутствует переменная окружения.'
        logging.critical(message)
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    start = 'START'
    send_message(bot, start)
    logging.info(start)
    current_timestamp = int(time.time())
    current_message = None
    current_error = None
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            current_timestamp = response.get('current_date')
            if len(homeworks) == 0:
                logging.info('Обновлений нет.')
                continue
            message = parse_status(homeworks[0])
            if message != current_message:
                current_message = message
                send_message(bot, message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message != current_error:
                try:
                    send_message(bot, message)
                except Exception as error:
                    logging.error(f'Нет доступа к телеграм {error}')
                current_error = message
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Ручное отключение.')
        logging.info('Ручное отключение.')
