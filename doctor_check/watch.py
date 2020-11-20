#!/usr/bin/env python3 
# -*- coding: utf-8 -*-
import json
import logging
from collections import namedtuple

import requests
import urllib3
from bs4 import BeautifulSoup
from filelock import FileLock

from doctor_check import (find_available_tickets, TicketInfo, format_date, SubscriptionsFile, PatientsFile)
from doctor_check.services import (Igis, Telegram, Viber)

urllib3.disable_warnings()
logger = logging.getLogger()


Cleanup = namedtuple('Cleanup', "hosp_id, doc_id, user")


TIME_MIN = '08'
TIME_MAX = '20'


def is_anytime(fromtime, totime):
    return fromtime == TIME_MIN and totime == TIME_MAX


def is_allweek(weekdays):
    return len(weekdays) == 5


def find_ticket(fromtime, totime, href, weekdays):
    data = requests.get(
        'https://igis.ru/online{0}'.format(href), verify=False)
    if not data.ok:
        logger.error("Ошибка загрузки: {0}".format(data.text))
        return ''
    soup = BeautifulSoup(data.text, 'html.parser')
    hrefs = find_available_tickets(soup)
    for href in hrefs:
        info = TicketInfo(href)
        if str(info.weekday) not in weekdays:
                continue
        href_hours = info.time.split(b':')[0]
        if href_hours.decode() >= fromtime and href_hours.decode() <= totime:
            return info.link
    return ''


def auto_subscribe(user, autouser, polis, hosp_id, ticket):
    logger.debug("Автоматическая подписка")
    surename = autouser.split(' ')[0]
    if not polis:
        logger.debug("Ошибка автоматической подписки: полис не найден.")
        return False
    cookies = Igis.login(hosp_id, surename, polis)
    if cookies:
        if Igis.subscribe(ticket, hosp_id, autouser, '', user):
            return True
        else:
            logger.debug("Ошибка автоматической подписки")
            return False
    else:
        logger.debug("Ошибка авторизации")
    return False


def delete_completed(cleanup):
    with SubscriptionsFile() as subsdb:
        subscriptions_reloaded = subsdb.db
        for c in cleanup:
            doctors = subscriptions_reloaded[c.hosp_id]['doctors']
            del doctors[c.doc_id]['subscriptions'][c.user]
            if not doctors[c.doc_id]['subscriptions']:
                del doctors[c.doc_id]
            if not doctors:
                del subscriptions_reloaded[c.hosp_id]


def main():
    logger.debug("Проверяем")
    telegram = Telegram()
    viber = Viber()
    with SubscriptionsFile() as subsdb:
        subscriptions = subsdb.db
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
                    message = '{0} \n https://doctor.kx13.ru/doctor/{1}/{2} \n https://igis.ru/online?obj={1}&page=doc&id={2}'.\
                        format(doctor_name, hosp_id, doc_id)
                    logger.debug("Пользователь: {0}".format(json.dumps(
                        user_dict, ensure_ascii=False)))
                    fromtime = user_dict['fromtime']
                    totime = user_dict['totime']
                    weekdays = user_dict['weekdays']
                    autouser = user_dict['autouser']
                    always = (is_anytime(fromtime, totime) and
                              is_allweek(weekdays))
                    if not always or autouser:
                        ticket = find_ticket(fromtime, totime, href, weekdays)
                        if not ticket:
                            logger.debug("Нет подходящих номерков")
                            continue
                        ticket = ticket.decode()
                        if autouser:
                            with PatientsFile() as auth:
                                auth_info = auth.db
                                polis = auth_info[user].get(autouser)
                            if auto_subscribe(user, autouser, polis, hosp_id, ticket):
                                ticket_date = ticket.split('&')[2][2:]
                                ticket_time = ticket.split('&')[3][2:]
                                ticket_date = format_date(ticket_date)
                                message = 'Записан: {0} {1} \n {2}'.\
                                    format(ticket_date, ticket_time, message)
                            else:
                                message = 'Ошибка автозаписи: {0}'.format(message)
                    logger.debug(f'{user} {message}')
                    telegram.send(user, message)
                    viber.send(user, message)
                    cleanup.append(Cleanup(hosp_id, doc_id, user))
    delete_completed(cleanup)


if __name__ == "__main__":
    main()
