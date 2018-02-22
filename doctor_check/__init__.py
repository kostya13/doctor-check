# -*- coding: utf-8 -*-
import json
import codecs
import time
import datetime

__version__ = '1.0'

EMAILCONFIG = 'email.json'
SUBSCRIPTIONS = 'subscriptions.json'
AUTH_FILE = 'auth.json'
LOCK_FILE = '/tmp/subscriptions.lock'
TELEGRAM_FILE = 'telegram.json'


def load_file(filename):
    try:
        with open(filename) as f:
            content = json.load(f)
    except (IOError, ValueError):
        content = {}
    return content


def save_file(filename, content):
    with codecs.open(filename, 'w', encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, encoding='utf-8', indent=2)


def find_available_tickets(soup):
    hrefs = [button.attrs['href'].encode('utf-8')
             for button in soup.find_all("a", class_="btn green")
             if button.attrs['href'].startswith('javascript:winbox')]
    hrefs.sort(key=lambda x: x.split('&')[2])
    return hrefs


class TicketInfo:
    """
    Пример ссылки:
    javascript:winbox(2,
    '/com/online/zapis.php?obj=39&kw=54005&d=20180215&t=08:00',
    '%D0%97%D00%BD%D0%B0%20%D0%BF%D1%80%D0%B8%D0%B5%D0%BC',
    400,null,wbclose())
    """
    def __init__(self, href):
        self.href = href
        self.items = href.split('&')

    @property
    def daystring(self):
        return self.items[2][2:]

    @property
    def time(self):
        return self.items[3][2:7]

    @property
    def date(self):
        return time.strptime(self.daystring, "%Y%m%d")

    @property
    def weekday(self):
        return datetime.date(*self.date[0:3]).weekday()

    @property
    def link(self):
        return self.href.split(',')[1][1:-1]
