#!/home/kostya/venvs/igis2/bin/python2.7
# -*- coding: utf-8 -*-
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

logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def full_path(filename=SUBSCRIPTIONS):
    return os.path.join(os.path.dirname(__file__), filename)


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


def main():
        logger.debug("Проверяем")
        try:
            with open(full_path()) as f:
                subscriptions = json.load(f)
        except IOError:
            subscriptions = {}
        cleanup = []
        for subs in subscriptions:
            if not subscriptions[subs]:
                continue
            hosp_id = subscriptions[subs][0][1].split('&')[0]
            data = requests.get(
                'http://igis.ru/online{0}&page=zapdoc'.format(hosp_id))
            if not data.ok:
                break
            docs = set([doc[1] for doc in subscriptions[subs]])
            soup = BeautifulSoup(data.text, 'html.parser')
            for c in soup.find_all('table')[5].children:
                if 'Всего номерков' in str(c):
                    href = c.find_all('a')[1].attrs['href']
                    if href in docs:
                        logger.debug("Найдено совпадение: {0}".format(href))
                        cleanup.append(href)
                        for email in [d[2] for d in subscriptions[subs] if d[1] == href]:
                            send_email(email, 'http://igis.ru/online{0}'.format(href))
        if cleanup:
            for hospital in subscriptions:
                current = [d for d in subscriptions.setdefault(hospital, [])
                           if d[1] not in cleanup]
                subscriptions[hospital] = current
            with codecs.open(full_path(), 'w', encoding="utf-8") as f:
                json.dump(subscriptions, f, ensure_ascii=False,
                          encoding='utf-8')


if __name__ == "__main__":
    main()
