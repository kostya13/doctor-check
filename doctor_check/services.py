# -*- coding: utf-8 -*-
import requests
import logging
import json
import smtplib
from email.mime.text import MIMEText
from doctor_check import full_path, EMAILCONFIG


RND = '91755'
logger = logging.getLogger(__name__)


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


def send_email(reciever, message):
    with open(full_path(EMAILCONFIG)) as f:
        email = json.load(f)
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
