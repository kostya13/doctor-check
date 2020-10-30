# -*- coding: utf-8 -*-
import requests
import logging
import json
import smtplib
from email.mime.text import MIMEText
from doctor_check import (load_file, save_file, EMAILCONFIG, TELEGRAM_FILE)
from tetoken import TOKEN


RND = '91755'
logger = logging.getLogger(__name__)


SMS_TEST = 1
# SMS_TEST = 0


class Telegram:
    def __init__(self):
        self.api_url = "https://api.telegram.org/bot{0}/".format(TOKEN)

    def _get_updates(self, offset=None, timeout=30):
        method = 'getUpdates'
        params = {'timeout': timeout, 'offset': offset}
        resp = requests.get(self.api_url + method, params, verify=False)
        result_json = resp.json()['result']
        result_json.reverse()
        return result_json

    def _send_message(self, chat_id, text):
        params = {'chat_id': chat_id, 'text': text}
        method = 'sendMessage'
        resp = requests.post(self.api_url + method, params)
        return resp

    def check_users(self, users):
        config = load_file(TELEGRAM_FILE)
        for u in self._get_updates():
            user = u['message']['text']
            if user in users and not config.get(user):
                logger.info(
                    "Добавлен telegram пользователь: {0}".format(user))
                chat_id = u['message']['chat']['id']
                config[user] = chat_id
                self._send_message(chat_id,
                                   "Вы добавлены в список рассылки")
        save_file(TELEGRAM_FILE, config)

    def send(self, user, message):
        config = load_file(TELEGRAM_FILE)
        if config.get(user):
            self._send_message(config[user], message)


class Igis:
    @staticmethod
    def login(hospital_id, surname, polis):
        data = requests.get('https://igis.ru/com/online/login.php',
                            params={'login': '1',
                                    'obj': hospital_id,
                                    'f': surname,
                                    'p': polis,
                                    'rnd': RND}, verify=False)
        if data.ok:
            if 'Ошибка авторизации' in data.text:
                return None
            return data.cookies
        else:
            logger.error(
                "Ошибка авторизации: {0}".format(data.text))
            return None

    @staticmethod
    def subscribe(ticket_info, cookies):
        zapis = requests.get(
            "https://igis.ru{0}&zapis=1&rnd={1}'".format(ticket_info, RND),
            cookies=cookies, verify=False)
        if zapis.ok:
            if 'У вас уже есть номерок' in zapis.text:
                logger.error("У вас уже есть номерок к данной специальности")
                return False
            else:
                return True
        else:
            logger.error("Ошибка записи: {0}".format(zapis.text))
            return None