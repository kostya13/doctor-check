# -*- coding: utf-8 -*-
import requests
import logging
from viberbot import Api
from viberbot.api.bot_configuration import BotConfiguration
from viberbot.api.messages import TextMessage

import json
from doctor_check import (load_file, save_file, registered_users, AUTH_FILE, MESSENGERS_FILE)
from doctor_check.tokens import TELEGRAM_TOKEN, VIBER_TOKEN, VIBER_NAME

logger = logging.getLogger()

RND = '91755'


def parse_chat_message(transport, chat_id, msg):
    messengers_config = load_file(MESSENGERS_FILE)
    users = load_file(AUTH_FILE)
    if msg == '/pass':
        for u in messengers_config.keys():
            t_chat = messengers_config[u].get(transport.NAME)
            if t_chat:
                transport.send(u, "Ваш пароль: {}".format(users[u]['password']))
                break
        else:
            transport._send_message(chat_id, "Вы не зарегистированы в системе")
    else:
        user = msg
        if user in registered_users():
            if messengers_config.get(user):
                if messengers_config[user].get(transport.NAME):
                    transport.send(user, 'Вы уже зарегистрированы')
                else:
                    messengers_config[user][transport.NAME] = chat_id
                    save_file(MESSENGERS_FILE, messengers_config)
                    transport.send(user, "Вы добавлены в список рассылки")
            else:
                messengers_config.setdefault(user, {})
                messengers_config[user][transport.NAME] = chat_id
                save_file(MESSENGERS_FILE, messengers_config)
                transport.send(user, "Вы добавлены в список рассылки")

        else:
            transport._send_message(chat_id, "Вы не зарегистированы в системе")


class Telegram:
    NAME = 'telegram'
    def __init__(self):
        self.api_url = "https://api.telegram.org/bot{0}/".format(TELEGRAM_TOKEN)

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

    def check_users(self, data):
        chat_id = data['message']['chat']['id']
        msg = data['message']['text']
        parse_chat_message(self, chat_id, msg)


    def send(self, user, message):
        config = load_file(MESSENGERS_FILE)
        if config.get(user):
            chat_id = config[user].get('telegram')
            if chat_id:
                self._send_message(chat_id, message)


class Viber:
    NAME = 'viber'
    def __init__(self):
        bot_configuration = BotConfiguration(
            name=VIBER_NAME,
            avatar='',
            auth_token=VIBER_TOKEN
        )
        self.api = Api(bot_configuration)

    def _send_message(self, chat_id, text):
        msg = TextMessage(text=text)
        resp = self.api.send_messages(chat_id, msg)
        return resp

    def check_users(self, viber_request):
        msg = viber_request.message.text
        chat_id = viber_request.sender.id
        parse_chat_message(self, chat_id, msg)

    def send(self, user, message):
        config = load_file(MESSENGERS_FILE)
        if config.get(user):
            chat_id = config[user].get('viber')
            if chat_id:
                self._send_message(chat_id, message)


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