#!/home/kostya/venvs/igis2/bin/python2.7
# -*- coding: utf-8 -*-
#!/home/u6334sbtt/venv/igis/bin/python
import codecs
from bs4 import BeautifulSoup
import requests
import json
import logging
import time
import datetime
from collections import namedtuple
from doctor_check.services import (igis_login, get_tiket, send_sms,
                                   send_email)

from doctor_check import (full_path, AUTH_FILE, LOCK_FILE, SUBSCRIPTIONS,
                          load_file, save_file)
from filelock import FileLock

Cleanup = namedtuple('Cleanup', "hosp_id, doc_id, user")


TIME_MIN = '08'
TIME_MAX = '20'
MONDAY = 0
FRIDAY = 4


SMS_TEST = 1
# SMS_TEST = 0

logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s',
                    level=logging.INFO)
                    # level=logging.INFO,
                    # filename=os.path.join(os.path.dirname(__file__),
                                          # 'watch.log'))
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


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


def main():
        logger.debug("Проверяем")
        auth_info = load_file(full_path(AUTH_FILE))
        if not auth_info:
            logger.error('Невозможно загрузить файл с реквизитами')
            quit(1)
        subscriptions = load_file(full_path(SUBSCRIPTIONS))
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
                        doctor_name = all_doctors[doc_id]['name'].encode('utf-8')
                        message = '{0} {1}'.format(doctor_name, url)
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
                                    cookies = igis_login(hosp_id, surename,
                                                         polis)
                                    if cookies:
                                        if get_tiket(tiket, cookies):
                                            tiket_date = tiket.split('&')[2]
                                            tiket_time = tiket.split('&')[3]
                                            message = 'Номерок: {0} {1} {2} {3}'.format(doctor_name, tiket_date, tiket_time, url)
                                        else:
                                            message = 'Ошибка автоподписки'.format(url)
                                            logger.debug(
                                                "Ошибка автоматической подписки")
                                    else:
                                        logger.debug("Ошибка авторизации")
                        send_email(email, message)
                        if api_id and tel:
                            send_sms(api_id, tel, message, SMS_TEST)
                        cleanup.append(Cleanup(hosp_id, doc_id, user))
        if cleanup:
            lock = FileLock(LOCK_FILE)
            with lock:
                subscriptions_reloaded = load_file(full_path(SUBSCRIPTIONS))
                for c in cleanup:
                    doctors = subscriptions_reloaded[c.hosp_id]['doctors']
                    del doctors[c.doc_id]['subscriptions'][c.user]
                    if not doctors[c.doc_id]['subscriptions']:
                        del doctors[c.doc_id]
                    if not doctors:
                        del subscriptions_reloaded[c.hosp_id]
                # save_file(full_path(SUBSCRIPTIONS))


if __name__ == "__main__":
    main()
