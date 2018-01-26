#!/home/kostya/venvs/igis2/bin/python2.7
# -*- coding: utf-8 -*-
#!/home/u6334sbtt/venv/igis/bin/python
import os
import codecs
from bs4 import BeautifulSoup
import requests
import json
import smtplib
from email.mime.text import MIMEText
import logging


EMAILCONFIG = 'email.json'
SUBSCRIPTIONS = 'subscriptions.json'
AUTH_FILE = 'auth.json'

TIME_MIN = '06'
TIME_MAX = '20'

logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s',
                    level=logging.INFO)
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
        return reply['total_free'] >= int(reply['used_today'])
    else:
        logger.error("Ошибка отправки SMS: {0}".format(data.text))
        return False


def send_sms(api_id, to, url, test=0):
    if not sms_limit(api_id):
        logger.error("Дневной лимит SMS исчерпан")
        return

    data = requests.get('https://sms.ru/sms/send',
                        params={
                            'api_id': api_id,
                            'to': to,
                            'msg': "Номерки {0}".format(url),
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


def send_email(reciever, info):
    with open(full_path(EMAILCONFIG)) as f:
        email = json.load(f)
    gmail_user = email['email']
    gmail_pwd = email['password']

    # Prepare actual message
    msg = MIMEText(info)
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


def main():
        logger.debug("Проверяем")
        try:
            with open(full_path(AUTH_FILE)) as f:
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
                    cleanup.append((hosp_id, doc_id))
                    for user in all_doctors[doc_id]['subscriptions'].keys():
                        url = 'http://igis.ru/online{0}'.format(href)
                        email = auth_info[user]['email']
                        api_id = auth_info[user].get('api_id')
                        tel = auth_info[user].get('tel')
                        send_email(email, url)
                        if api_id and tel:
                            send_sms(api_id, tel, url, 1)
        for c in cleanup:
            del subscriptions[c[0]]['doctors'][c[1]]
            if not subscriptions[c[0]]['doctors']:
                del subscriptions[c[0]]
        with codecs.open(full_path(), 'w', encoding="utf-8") as f:
            json.dump(subscriptions, f, ensure_ascii=False,
                      encoding='utf-8')


if __name__ == "__main__":
    main()
