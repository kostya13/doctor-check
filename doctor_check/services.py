# -*- coding: utf-8 -*-
import requests
import logging
import json
import smtplib
from email.mime.text import MIMEText
from doctor_check import (load_file, save_file, EMAILCONFIG, TELEGRAM_FILE)


RND = '91755'
logger = logging.getLogger(__name__)

TOKEN = '506351730:AAGjwM8ZCiI19eCN_npFP4acC90lp3O2y2I'

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
        data = requests.get('http://igis.ru/com/online/login.php',
                            params={'login': '1',
                                    'obj': hospital_id,
                                    'f': surname,
                                    'p': polis,
                                    'rnd': RND}, verify=False)
        if data.ok:
            if 'Ошибка авторизации' in data.text.encode('utf-8'):
                return None
            return data.cookies
        else:
            logger.error(
                "Ошибка авторизации: {0}".format(data.text.encode('utf-8')))
            return None

    @staticmethod
    def subscribe(ticket_info, cookies):
        zapis = requests.get(
            "https://igis.ru{0}&zapis=1&rnd={1}'".format(ticket_info, RND),
            cookies=cookies, verify=False)
        if zapis.ok:
            if 'У вас уже есть номерок' in zapis.text.encode('utf-8'):
                logger.error("У вас уже есть номерок к данной специальности")
                return False
            else:
                return True
        else:
            logger.error("Ошибка записи: {0}".format(zapis.text))
            return None


class Sms:
    @staticmethod
    def limit(api_id):
        data = requests.get('https://sms.ru/sms/my/free',
                            params={
                                'api_id': api_id,
                                'json': 1}, verify=False)
        if data.ok:
            reply = json.loads(data.text)
            if not reply['used_today']:
                return True
            return reply['total_free'] >= int(reply['used_today'])
        else:
            logger.error("Ошибка отправки SMS: {0}".format(data.text))
            return False

    @staticmethod
    def send(auth_info, user,  message):
        api_id = auth_info[user]['sms'].get('api_id')
        tel = auth_info[user]['sms'].get('tel')
        if not (api_id and tel):
            return
        if not Sms.limit(api_id):
            logger.error("Дневной лимит SMS исчерпан")
            return

        data = requests.get('https://sms.ru/sms/send',
                            params={
                                'api_id': api_id,
                                'to': tel,
                                'msg': "{0}".format(message),
                                'json': 1,
                                'test': SMS_TEST}, verify=False)
        if data.ok:
            reply = json.loads(data.text)
            if reply['sms'][tel]['status'] == 'ERROR':
                logger.error(
                    "Ошибка отправки SMS: {0}".
                    format(reply['sms'][tel]['status_text'].encode('utf-8')))
            else:
                logger.debug("SMS отправлена.")
        else:
            logger.error("Ошибка отправки SMS: {0}".format(data.text))


def send_email(reciever, message):
    email = load_file(EMAILCONFIG)
    user = email['email']
    pwd = email['password']

    # Prepare actual message
    msg = MIMEText('{0}'.format(message))
    msg['Subject'] = 'IGIS Новые номерки'
    msg['From'] = user
    msg['To'] = reciever

    try:
        server = smtplib.SMTP(email['server'], 587)
        server.ehlo()
        server.starttls()
        server.login(user, pwd)
        server.sendmail(msg['From'], msg['To'], msg.as_string())
        server.close()
        logger.debug('Почта успешно отправлена')
    except OSError as e:
        logger.error('Не могу отправить почту: {0}'.format(e))
