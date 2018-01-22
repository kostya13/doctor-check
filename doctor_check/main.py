from bs4 import BeautifulSoup
import requests
from pprint import pprint
import json
import smtplib


FILENAME = 'doctors.json'


def send_email(info):
    gmail_user = 'kx13gogl@gmail.com'
    gmail_pwd = 'qazxswed'
    FROM = gmail_user
    TO = gmail_user
    SUBJECT = 'subject'

    # Prepare actual message
    message = """From: {}\nTo: {}\nSubject: {}\n\n{}
    """.format(FROM, TO, SUBJECT, info)
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.ehlo()
        server.starttls()
        server.login(gmail_user, gmail_pwd)
        server.sendmail(FROM, TO, message)
        server.close()
        print('successfully sent the mail')
    except OSError:
        print('failed to send mail')


def main():
    data = requests.get('http://igis.ru/online?obj=39&page=zapdoc')
    try:
        with open(FILENAME) as f:
            all_doctors = json.load(f)
    except IOError:
        all_doctors = {}
    if data.ok:
        soup = BeautifulSoup(data.text, 'html.parser')
        for c in soup.find_all('table')[5].children:
            try:
                category = c.h2.text
                continue
            except AttributeError:
                pass
            if 'Номерков нет' in str(c):
                continue
            if 'Всего номерков' in str(c):
                doc = all_doctors.setdefault(category, {})
                doc[c.b.text] = c.find_all('a')[1].u.text
        pprint(all_doctors)
        with open(FILENAME, 'w') as f:
            json.dump(all_doctors, f)
        send_email(json.dumps(all_doctors))
    else:
        print("Ошибка чтения")
        exit(1)


if __name__ == "__main__":
    main()
