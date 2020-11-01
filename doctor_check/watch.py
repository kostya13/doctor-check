#!/usr/bin/env python3 
# -*- coding: utf-8 -*-
import json
import logging
from collections import namedtuple

import requests
import urllib3
from bs4 import BeautifulSoup
from filelock import FileLock

from doctor_check import (LOCK_FILE, SUBSCRIPTIONS,
                          load_file, save_file, registered_users,
                          find_available_tickets, TicketInfo)
from doctor_check.services import (Igis, Telegram, Viber)

urllib3.disable_warnings()


Cleanup = namedtuple('Cleanup', "hosp_id, doc_id, user")


TIME_MIN = '08'
TIME_MAX = '20'
MONDAY = 0
FRIDAY = 4

logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s',
                    level=logging.INFO)
# level=logging.INFO, filename='watch.log')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def is_anytime(fromtime, totime):
    return fromtime == TIME_MIN and totime == TIME_MAX


def is_allweek(fromweekday, toweekday):
    return fromweekday == MONDAY and toweekday == FRIDAY


def find_ticket(fromtime, totime, href, fromweekday, toweekday):
    data = requests.get(
        'https://igis.ru/online{0}'.format(href), verify=False)
    if not data.ok:
        logger.error("Ошибка загрузки: {0}".format(data.text))
        return ''
    soup = BeautifulSoup(data.text, 'html.parser')
    hrefs = find_available_tickets(soup)
    for href in hrefs:
        info = TicketInfo(href)
        weekday = info.weekday
        if weekday < fromweekday or weekday > toweekday:
                continue
        href_hours = info.time.split(b':')[0]
        if href_hours.decode() >= fromtime and href_hours.decode() <= totime:
            return info.link
    return ''


def auto_subscribe(autouser, polis, hosp_id, ticket):
    logger.debug("Автоматическая подписка")
    surename = autouser.split(' ')[0]
    if not polis:
        logger.debug("Ошибка автоматической подписки: полис не найден.")
        return False
    cookies = Igis.login(hosp_id, surename, polis)
    if cookies:
        if Igis.subscribe(ticket, cookies):
            return True
        else:
            logger.debug("Ошибка автоматической подписки")
            return False
    else:
        logger.debug("Ошибка авторизации")
    return False


def delete_completed(cleanup):
    with FileLock(LOCK_FILE):
        subscriptions_reloaded = load_file((SUBSCRIPTIONS))
        for c in cleanup:
            doctors = subscriptions_reloaded[c.hosp_id]['doctors']
            del doctors[c.doc_id]['subscriptions'][c.user]
            if not doctors[c.doc_id]['subscriptions']:
                del doctors[c.doc_id]
            if not doctors:
                del subscriptions_reloaded[c.hosp_id]
        save_file((SUBSCRIPTIONS), subscriptions_reloaded)


def main():
    logger.debug("Проверяем")
    telegram = Telegram()
    viber = Viber()
    telegram.check_users(registered_users())
    subscriptions = load_file(SUBSCRIPTIONS)
    cleanup = []
    for hosp_id, hosp_info in subscriptions.items():
        data = requests.get(
            'https://igis.ru/online?obj={0}&page=zapdoc'.format(hosp_id), verify=False)
        if not data.ok:
            logger.error("Ошибка загрузки: {0}".format(data.text))
            break
        soup = BeautifulSoup(data.text, 'html.parser')
        all_doctors = hosp_info['doctors']
        doctors_list = [c for c in soup.find_all('table')[5].children
                        if 'Всего номерков' in str(c)]
        for c in doctors_list:
            href = c.find_all('a')[1].attrs['href']
            doc_id = href.split('&')[2][3:]
            if doc_id not in all_doctors.keys():
                continue
            logger.debug("Найдено совпадение: {0}".format(href))
            for user in all_doctors[doc_id]['subscriptions'].keys():
                user_dict = all_doctors[doc_id]['subscriptions'][user]
                doctor_name = all_doctors[doc_id]['name']
                message = '{0} https://dc.kx13.ru/doctor/{1}/{2}'.\
                    format(doctor_name, hosp_id, doc_id)
                logger.debug("Пользователь: {0}".format(json.dumps(
                    user_dict, ensure_ascii=False)))
                fromtime = user_dict['fromtime']
                totime = user_dict['totime']
                fromweekday = int(user_dict['fromweekday'])
                toweekday = int(user_dict['toweekday'])
                autouser = user_dict['autouser']
                always = (is_anytime(fromtime, totime) and
                          is_allweek(fromweekday, toweekday))
                if not always or autouser:
                    ticket = find_ticket(fromtime, totime, href,
                                        fromweekday, toweekday)
                    if not ticket:
                        logger.debug("Нет подходящих номерков")
                        continue
                    ticket = ticket.decode()
                    if autouser:
                        polis = auth_info[user]['auth'].get(autouser)
                        if auto_subscribe(autouser, polis, hosp_id, ticket):
                            ticket_date = ticket.split('&')[2][2:]
                            ticket_time = ticket.split('&')[3][2:]
                            ticket_date = '{}-{}-{}'.format(ticket_date[:4],ticket_date[4:6], ticket_date[6:])
                            message = 'Записан: {0} {1} {2}'.\
                                format(ticket_date, ticket_time, message)
                        else:
                            message = 'Ошибка автозаписи: {0}'.format(message)
                telegram.send(user, message)
                viber.send(user, message)
                cleanup.append(Cleanup(hosp_id, doc_id, user))
    delete_completed(cleanup)


if __name__ == "__main__":
    main()
