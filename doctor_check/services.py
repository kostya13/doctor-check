# -*- coding: utf-8 -*-
import requests
import logging
import json
import smtplib
from email.mime.text import MIMEText
from doctor_check import (load_file, save_file)


RND = '91755'
logger = logging.getLogger(__name__)
TOKEN = '506351730:AAGjwM8ZCiI19eCN_npFP4acC90lp3O2y2I'


class BotHandler:

    def __init__(self):
        self.api_url = "https://api.telegram.org/bot{0}/".format(TOKEN)

    def get_updates(self, offset=None, timeout=30):
        method = 'getUpdates'
        params = {'timeout': timeout, 'offset': offset}
        resp = requests.get(self.api_url + method, params)
        result_json = resp.json()['result']
        result_json.reverse()
        return result_json

    def send_message(self, chat_id, text):
        params = {'chat_id': chat_id, 'text': text}
        method = 'sendMessage'
        resp = requests.post(self.api_url + method, params)
        return resp

    def get_last_update(self):
        get_result = self.get_updates()

        if len(get_result) > 0:
            last_update = get_result[-1]
        else:
            last_update = get_result[len(get_result)]

        return last_update

def igis_login(hospital_id, surname, polis):
    data = requests.get('http://igis.ru/com/online/login.php',
                        params={'login': '1',
                                'obj': hospital_id,
                                'f': surname,
                                'p': polis,
                                'rnd': RND})
    if data.ok:
        if 'Ошибка авторизации' in data.text.encode('utf-8'):
            return None
        return data.cookies
    else:
        logger.error(
            "Ошибка авторизации: {0}".format(data.text.encode('utf-8')))
        return None


def get_tiket(tiket_info, cookies):
    zapis = requests.get(
        "http://igis.ru{0}&zapis=1&rnd={1}'".format(tiket_info, RND),
        cookies=cookies)
    if zapis.ok:
        if 'У вас уже есть номерок' in zapis.text.encode('utf-8'):
            logger.error("У вас уже есть номерок к данной специальности")
            return False
        else:
            return True
    else:
        logger.error("Ошибка записи: {0}".format(zapis.text))
        return None


def sms_limit(api_id):
    data = requests.get('https://sms.ru/sms/my/free',
                        params={
                            'api_id': api_id,
                            'json': 1})
    if data.ok:
        reply = json.loads(data.text)
        if not reply['used_today']:
            return True
        return reply['total_free'] >= int(reply['used_today'])
    else:
        logger.error("Ошибка отправки SMS: {0}".format(data.text))
        return False


def send_sms(api_id, to, message, test=0):
    if not sms_limit(api_id):
        logger.error("Дневной лимит SMS исчерпан")
        return

    data = requests.get('https://sms.ru/sms/send',
                        params={
                            'api_id': api_id,
                            'to': to,
                            'msg': "{0}".format(message),
                            'json': 1,
                            'test': test})
    if data.ok:
        reply = json.loads(data.text)
        if reply['sms'][to]['status'] == 'ERROR':
            logger.error(
                "Ошибка отправки SMS: {0}".
                format(reply['sms'][to]['status_text'].encode('utf-8')))
        else:
            logger.debug("SMS отправлена.")
    else:
        logger.error("Ошибка отправки SMS: {0}".format(data.text))


def send_email(email, reciever, message):
    gmail_user = email['email']
    gmail_pwd = email['password']

    # Prepare actual message
    msg = MIMEText('{0}'.format(message))
    msg['Subject'] = 'IGIS Новые номерки'
    msg['From'] = gmail_user
    msg['To'] = reciever

    try:
        server = smtplib.SMTP(email['server'], 587)
        server.ehlo()
        server.starttls()
        server.login(gmail_user, gmail_pwd)
        server.sendmail(msg['From'], msg['To'], msg.as_string())
        server.close()
        logger.debug('Почта успешно отправлена')
    except OSError as e:
        logger.error('Не могу отправить почту: {0}'.format(e))


def check_telegram_users(config_file, users):
    config = load_file(config_file)
    bot = BotHandler()
    for u in bot.get_updates():
        message = u['message']['text']
        if message in users and not config.get(message):
            logger.info("Добавлен telegram пользователь: {0}".format(message))
            config[u['message']['text']] = u['message']['chat']['id']
            bot.send_message(u['message']['chat']['id'], "Вы добавлены в список рассылки")
    save_file(config_file, config)


def send_telegram(config ,user, message):
    bot = BotHandler()
    if config.get(user):
        bot.send_message(config[user], message)
