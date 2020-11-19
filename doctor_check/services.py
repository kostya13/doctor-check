# -*- coding: utf-8 -*-
import requests
import logging
from bottle import abort, request, template
from viberbot import Api
from viberbot.api.bot_configuration import BotConfiguration
from viberbot.api.messages import TextMessage
from doctor_check.tokens import TELEGRAM_TOKEN, VIBER_TOKEN, VIBER_NAME
from doctor_check import CookiesFile, PatientsFile, MessengersFile, AuthFile, templates

logger = logging.getLogger()

RND = '91755'


def parse_chat_message(transport, chat_id, msg):
    with AuthFile() as auth:
        registered_users = auth.registered_users()
        users = auth.db
    with MessengersFile() as messengerdb:
        messengers_config = messengerdb.db
    if msg == '/login':
        for u in messengers_config.keys():
            t_chat = messengers_config[u].get(transport.NAME)
            if t_chat:
                transport.send(u, "Ваш логин: {}\nВаш пароль: {}".format(u, users[u]))
                break
        else:
            transport._send_message(chat_id, "Вы не зарегистированы в системе")
    else:
        user = msg
        if user in registered_users:
            if messengers_config.get(user):
                if messengers_config[user].get(transport.NAME):
                    transport.send(user, 'Вы уже зарегистрированы')
                else:
                    with MessengersFile() as messengerdb:
                        messengerdb.db[user][transport.NAME] = chat_id
                    transport.send(user, "Вы добавлены в список рассылки. Чтобы узнать свой логин и пароль"
                                   " отправьте в чат комманду /login")
            else:
                with MessengersFile() as messengerdb:
                    messengerdb.db.setdefault(user, {})
                    messengerdb.db[user][transport.NAME] = chat_id
                transport.send(user, "Вы добавлены в список рассылки")
        else:
            transport._send_message(chat_id, "Вы не зарегистированы в системе")


class Telegram:
    NAME = 'telegram'
    def __init__(self):
        self.api_url = "https://api.telegram.org/bot{0}/".format(TELEGRAM_TOKEN)

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
        with MessengersFile() as messengerdb:
            config = messengerdb.db
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
        with MessengersFile() as messengerdb:
            config = messengerdb.db
        if config.get(user):
            chat_id = config[user].get('viber')
            if chat_id:
                self._send_message(chat_id, message)


class Igis:
    @staticmethod
    def refresh_cookie(hospital_id, autouser, polis):
        user = request.get_cookie("logined", secret='some-secret-key')
        surename = autouser.split(' ')[0]
        cookie = Igis.login(hospital_id, surename, polis)
        if cookie:
            with CookiesFile() as cookiedb:
                cookiedb.set(user, autouser, hospital_id, cookie)
        return cookie

    @staticmethod
    def load_page(hospital_id, autouser, igis_page, referer='', user=None):
        def is_correct_reply(data):
            return data.ok and 'Ошибка авторизации' not in data.text
        if not user:
            user = request.get_cookie("logined", secret='some-secret-key')
        with PatientsFile() as patients:
            polis = patients.db[user][autouser]
        logger.debug(f'{hospital_id}, {autouser}, {polis}')
        cookie = None
        cached = False
        with CookiesFile() as cookiedb:
            cookie = cookiedb.get(user, hospital_id, autouser)
            if cookie:
                cached = True
        if not cookie:
            cookie = Igis.refresh_cookie(hospital_id, autouser, polis)
        if cookie:
            data = requests.get(igis_page, cookies=cookie, verify=False)
            if is_correct_reply(data):
                return data
            else:
                if cached:
                    cookie = Igis.refresh_cookie(hospital_id, autouser, polis)
                    data = requests.get(igis_page, cookies=cookie, verify=False)
                    if is_correct_reply(data):
                        return data
                    else:
                        abort(400, "Ошибка загрузки страницы")
        return template(templates.subscribe_error, message="Невозможно авторизоваться",
                        referer=referer)

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
    def subscribe(ticket_info, hospital_id, autouser, referer, user=None):
        igis_page=  "https://igis.ru{0}&zapis=1&rnd={1}'".format(ticket_info, RND)
        zapis = Igis.load_page(hospital_id, autouser, igis_page, referer, user)
        if zapis.ok:
            if 'У вас уже есть номерок' in zapis.text:
                logger.error("У вас уже есть номерок к данной специальности")
                return False
            else:
                return True
        else:
            logger.error("Ошибка записи: {0}".format(zapis.text))
            return None