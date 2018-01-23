from bs4 import BeautifulSoup
import requests
import json
import smtplib
from email.message import EmailMessage
from doctor_check.server import FILENAME
from time import sleep
import logging
logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

EMAILCONFIG = 'email.json'
SUBSCRIPTIONS = FILENAME


def send_email(info):
    with open(EMAILCONFIG) as f:
        email = json.load(f)
    gmail_user = email['email']
    gmail_pwd = email['password']

    # Prepare actual message
    msg = EmailMessage()
    msg.set_content(info)
    msg['Subject'] = 'IGIS Новые номерки'
    msg['From'] = gmail_user
    msg['To'] = gmail_user

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.ehlo()
        server.starttls()
        server.login(gmail_user, gmail_pwd)
        # server.sendmail(FROM, TO, message)
        server.send_message(msg)
        server.close()
        logger.debug('Почта успешно отправлена')
    except OSError as e:
        logger.error('Не могу отправить почту: {}'.format(e))


def main():
    while True:
        logger.debug("Проверяем")
        try:
            with open(SUBSCRIPTIONS) as f:
                subscriptions = json.load(f)
        except IOError:
            subscriptions = {}
        cleanup = []
        for subs in subscriptions:
            if not subscriptions[subs]:
                break
            hosp_id = subscriptions[subs][0][1].split('&')[0]
            data = requests.get(
                'http://igis.ru/online{}&page=zapdoc'.format(hosp_id))
            if not data.ok:
                break
            docs = [doc[1] for doc in subscriptions[subs]]
            soup = BeautifulSoup(data.text, 'html.parser')
            for c in soup.find_all('table')[5].children:
                if 'Всего номерков' in str(c):
                    href = c.find_all('a')[1].attrs['href']
                    if href in docs:
                        logger.debug("Найдено совпадение: {}".format(href))
                        cleanup.append(href)
                        send_email('http://igis.ru/online{}'.format(href))
        if cleanup:
            for hospital in subscriptions:
                current = [d for d in subscriptions.setdefault(hospital, [])
                           if d[1] not in cleanup]
                subscriptions[hospital] = current
            with open(FILENAME, 'w') as f:
                json.dump(subscriptions, f, ensure_ascii=False)
        sleep(30 * 60)


if __name__ == "__main__":
    main()
