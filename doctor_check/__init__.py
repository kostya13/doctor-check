# -*- coding: utf-8 -*-
import codecs
from collections import namedtuple
import datetime
import json
import logging
import os
import time
from requests.cookies import RequestsCookieJar

from filelock import FileLock

__version__ = '1.3'
HOST = 'https://doctor.kx13.ru'


logger = logging.getLogger()

handler = logging.FileHandler(
    os.path.join(os.path.dirname(__file__), '..', 'server.log'), encoding='utf-8')
logger.setLevel(logging.ERROR)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s - %(lineno)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


DocInfo = namedtuple('DocInfo', 'name url user')

DAYS_MAP = {'0': 'Понедельник',
            '1': 'Вторник',
            '2': 'Среда',
            '3': 'Четверг',
            '4': 'Пятница'}


def format_date(date):
    return '{}-{}-{}'.format(date[:4], date[4:6], date[6:])


class ConfigFile:
    def __init__(self, filename):
        self.filename = filename
        self.lock_file = filename + '.lock'
        self.file_lock = FileLock(self.lock_file)
        self.db = {}

    def load(self):
        if self.file_lock.is_locked:
            raise RuntimeError('Нельзя использвать на заблокированных файлах')
        else:
            with self.file_lock:
                return self._load_file()

    def _load_file(self):
        try:
            with open(self.filename, encoding='utf8') as f:
                self.db = json.load(f)
        except FileNotFoundError:
            self.db = {}
        except Exception as e:
            logger.error(e)
            self.file_lock.release()
            raise


    def _save_file(self):
        with codecs.open(self.filename, 'w', encoding='utf8') as f:
            json.dump(self.db, f, ensure_ascii=False, indent=2)

    def _check_locked(self):
        if not self.file_lock.is_locked:
            raise RuntimeError('Нельзя использвать без блокировки')

    def __enter__(self):
        self.file_lock.acquire(60)
        self._load_file()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type:
            logger.error(f'{exc_type} {exc_value} {traceback}')
        else:
            self._save_file()
        self.file_lock.release()
        return None


class AuthFile(ConfigFile):
    """Конфигурация аутентификации в формате {login: password,...}"""
    def __init__(self):
        super().__init__('auth.json')

    def registered_users(self):
        self._check_locked()
        return list(self.db.keys())

class CookiesFile(ConfigFile):
    """Файл с печеньками для уже зарегистированных пользвоателей на igis
     используется, чтобы уменьшить количество логинов в систему igis
    в формате {login: {autouser: cookie,...},...}"""
    def __init__(self):
        super().__init__('cookies.json')

    def get(self, user, hospital_id, autouser):
        self._check_locked()
        cookie_dict = self.db.get(user, {}).get(hospital_id, {}).get(autouser)
        if cookie_dict:
            c = RequestsCookieJar()
            c.update(cookie_dict)
            return c


    def set(self, user, autouser, hospital_id, cookie):
        self._check_locked()
        self.db.setdefault(user, {}).setdefault(hospital_id, {}).setdefault(autouser, cookie.get_dict())
        pass

class PatientsFile(ConfigFile):
    """Конфигурация пациентов с полисами. Для каждого зарегистрированого пользователя
    может быть несколько пациентов в формате
    {login: {"фамилия имя": "номер полиса", ...}}
    """
    def __init__(self):
        super().__init__('patients.json')

    def get_names(self, user):
        self._check_locked()
        return list(self.db.get(user, {}).keys())


class MessengersFile(ConfigFile):
    """Конфигурации мессенджеров для пользователей в формате
    {login: {"viber": "chat_id",
            {"telegram": "chat_id"}
    """
    def __init__(self):
        super().__init__('messengers.json')


def find_available_tickets(soup):
    hrefs = [button.attrs['href'].encode('utf-8')
             for button in soup.find_all("a", class_="btn green")
             if button.attrs['href'].startswith('javascript:winbox')]
    hrefs.sort(key=lambda x: x.split(b'&')[2])
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
        self.items = href.split(b'&')

    @property
    def daystring(self):
        return self.items[2][2:]

    @property
    def time(self):
        return self.items[3][2:7]

    @property
    def date(self):
        return time.strptime(self.daystring.decode(), "%Y%m%d")

    @property
    def weekday(self):
        return datetime.date(*self.date[0:3]).weekday()

    @property
    def link(self):
        return self.href.split(b',')[1][1:-1]

class SubscriptionsFile(ConfigFile):
    """Конфигурация активных подписок для ползователей
    формат конфигурации
    {"hosp_id": {"name": "название больницы",
                 "doctors": { "doctor_id" :{
                        "name": "ФИО доктора",
                        "subscriptions": {
                                  "login": {
                                    "fromtime": "08",
                                    "totime": "20",
                                    "fromweekday": "0",
                                    "toweekday": "4",
                                    "autouser": "ФИ из patients.json"
                                  }}
                              }}}
    """
    def __init__(self):
        super().__init__('subscriptions.json')