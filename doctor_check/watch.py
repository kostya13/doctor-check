#!/home/u6334sbtt/venv/igis/bin/python
# -*- coding: utf-8 -*-
#!/home/kostya/venvs/igis2/bin/python2.7
import os
import codecs
from bs4 import BeautifulSoup
import requests
import json
import smtplib
from email.mime.text import MIMEText
import logging
import time
import datetime
from collections import namedtuple

Cleanup = namedtuple('Cleanup', "hosp_id, doc_id, user")


EMAILCONFIG = 'email.json'
SUBSCRIPTIONS = 'subscriptions.json'
AUTH_FILE = 'auth.json'

TIME_MIN = '08'
TIME_MAX = '20'
MONDAY = 0
FRIDAY = 4

RND = '91755'

# SMS_TEST = 1
SMS_TEST = 0

logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s',
                    # level=logging.INFO)
                    level=logging.INFO,
                    filename=os.path.join(os.path.dirname(__file__),
                                          'watch.log'))
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def full_path(filename=SUBSCRIPTIONS):
    return os.path.join(os.path.dirname(__file__), filename)


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


def send_sms(api_id, to, url, message, test=0):
    if not sms_limit(api_id):
        logger.error("Дневной лимит SMS исчерпан")
        return

    data = requests.get('https://sms.ru/sms/send',
                        params={
                            'api_id': api_id,
                            'to': to,
                            'msg': "Номерки {0} {1}".format(url, message),
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


def send_email(reciever, info, message):
    with open(full_path(EMAILCONFIG)) as f:
        email = json.load(f)
    gmail_user = email['email']
    gmail_pwd = email['password']

    # Prepare actual message
    msg = MIMEText('{0} {1}'.format(info, message))
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


def is_anytime(fromtime, totime):
    return fromtime == TIME_MIN and totime == TIME_MAX


def is_weekday(fromweekday, toweekday):
    return fromweekday == MONDAY and toweekday == FRIDAY


def get_ticket(fromtime, totime, href, fromweekday, toweekday):
    data = requests.get(
        'http://igis.ru/online{0}'.format(href))
    if not data.ok:
        logger.error("Ошибка загрузки: {0}".format(data.text))
        return False
    soup = BeautifulSoup(data.text, 'html.parser')
    hrefs = [button.attrs['href'].encode('utf-8')
             for button in soup.find_all("a", class_="btn green")]
    hrefs.sort(key=lambda x: x.split('&')[2])
    for href in hrefs:
        items = href.split('&')
        day = items[2][2:]
        t = time.strptime(day, "%Y%m%d")
        weekday = datetime.date(*t[0:3]).weekday()
        if weekday < fromweekday or weekday > toweekday:
                continue
        href_time = href.split('&')[3][2:7].split(':')[0]
        if href_time >= fromtime and href_time <= totime:
            return href.split(',')[1][1:-1]
    return None


def login(hospital_id, surname, polis):
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
        return True
    else:
        logger.error("Ошибка записи: {0}".format(zapis.text))
        return None


def main():
        logger.debug("Проверяем")
        try:
            with codecs.open(full_path(AUTH_FILE),  encoding="utf-8") as f:
                auth_info = json.load(f)
        except IOError:
            logger.error('Невозможно загрузить файл с реквизитами')
        try:
            with open(full_path()) as f:
                subscriptions = json.load(f)
        except IOError:
            subscriptions = {}
            quit(1)
        cleanup = []
        for hosp_id in subscriptions:
            data = requests.get(
                'http://igis.ru/online?obj={0}&page=zapdoc'.format(hosp_id))
            if not data.ok:
                logger.error("Ошибка загрузки: {0}".format(data.text))
                break
            soup = BeautifulSoup(data.text, 'html.parser')
            all_doctors = subscriptions[hosp_id]['doctors']
            for c in soup.find_all('table')[5].children:
                if 'Всего номерков' not in str(c):
                    continue
                href = c.find_all('a')[1].attrs['href']
                doc_id = href.split('&')[2][3:]
                if doc_id in all_doctors.keys():
                    logger.debug("Найдено совпадение: {0}".format(href))
                    for user in all_doctors[doc_id]['subscriptions'].keys():
                        url = 'http://igis.ru/online{0}'.format(href)
                        email = auth_info[user]['email']
                        api_id = auth_info[user]['sms'].get('api_id')
                        tel = auth_info[user]['sms'].get('tel')
                        user_dict = all_doctors[doc_id]['subscriptions'][user]
                        autouser = user_dict['autouser']
                        fromtime = user_dict['fromtime']
                        totime = user_dict['totime']
                        fromweekday = int(user_dict['fromweekday'])
                        toweekday = int(user_dict['toweekday'])
                        message = ''
                        logger.debug(
                            "Пользователь: {0}".format(json.dumps(
                                user_dict, ensure_ascii=False).encode('utf-8')))
                        if not (is_anytime(fromtime, totime) and
                                is_weekday(fromweekday, toweekday)) or autouser:
                            tiket = get_ticket(fromtime, totime, href,
                                               int(fromweekday), int(toweekday))
                            if not tiket:
                                logger.debug("Время не совпадает")
                                continue
                            else:
                                if autouser and auth_info[user].get('auth'):
                                    logger.debug("Автоматическая подписка")
                                    surename = autouser.split(' ')[0]
                                    polis = auth_info[user]['auth'][autouser]
                                    cookies = login(hosp_id, surename, polis)
                                    if cookies:
                                        if get_tiket(tiket, cookies):
                                            message = 'подписаны'
                                        else:
                                            message = 'ошибка автоподписки'
                                            logger.debug(
                                                "Ошибка автоматической подписки")
                                    else:
                                        logger.debug("Ошибка авторизации")
                        send_email(email, url, message)
                        if api_id and tel:
                            send_sms(api_id, tel, url, message, SMS_TEST)
                        cleanup.append(Cleanup(hosp_id, doc_id, user))
        for c in cleanup:
            doctors = subscriptions[c.hosp_id]['doctors']
            del doctors[c.doc_id]['subscriptions'][c.user]
            if not doctors[c.doc_id]['subscriptions']:
                del doctors[c.doc_id]
            if not doctors:
                del subscriptions[c.hosp_id]
        if cleanup:
            with codecs.open(full_path(), 'w', encoding="utf-8") as f:
                json.dump(subscriptions, f, ensure_ascii=False,
                          encoding='utf-8', indent=2)


if __name__ == "__main__":
    main()
