#!/usr/bin/env python3 
# -*- coding: utf-8 -*-
from bottle import route, run, template, abort, request, response, redirect
import requests 
from bs4 import BeautifulSoup
from collections import OrderedDict
from doctor_check.services import Igis, Viber, Telegram
from viberbot.api.viber_requests import ViberMessageRequest
from doctor_check import (SUBSCRIPTIONS, AUTH_FILE, LOCK_FILE,
                          load_file, save_file, find_available_tickets,
                          TicketInfo)
from filelock import FileLock
from collections import namedtuple

import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.FileHandler('/home/u63341pyl/domains/kx13.ru/public_html/dc/server.log', encoding='utf-8')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

DocInfo = namedtuple('DocInfo', 'name url user')

DAYS_MAP = {'0': 'Понедельник',
            '1': 'Вторник',
            '2': 'Среда',
            '3': 'Четверг',
            '4': 'Пятница'}

html = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Номеркождун</title>
  <style>
    body {{
      line-height: 1.5;
      background-color: #BEF7F5;}}
     ul li {{
      margin-top: 20px;}}
  </style>
  <script>
  //Здесь можно вставить скрипт
  </script>
</head>
<body>
{0}
</body>
</html>
"""

login_page = html.format("""
<form action="/login" method="post">
    Имя: <input name="name" type="text" />
    Пароль: <input name="password" type="password" />
    <input name="referer" value="{{referer}}" type="hidden" />
    <input value="Логин" type="submit" />
</form>
""")

not_autorized_page = html.format("""
Пройдите авторизацию снова <a href="/login?{{referer}}">Авторизация</a>
<br><br>
<a href="/">Главная</a>
""")

index_page = html.format("""
<table>
    <tr>
        <td><img src="waiter.png"></td>
        <td><h1>Номеркождун:<br> {{username}}</h1></td>
    </tr>
</table>
<a href='category/1'>Взрослые больницы</a><br>
<a href='category/2'>Детские больницы</a><br>
<a href='category/3'>Стоматологии</a><br>
<a href='category/4'>Диспансеры и спецучереждения</a>
<br><br>
<b><a href='subscriptions'>Текущие подписки</a></b>
<br><br>
<a href='logout'>Выход</a>
""")

hospital_page = html.format("""
<a href='{{back}}'> Назад</a><br><br>
<h2>{{name}}</h2>
<ul>
% for item in docs:
    <li><b>{{item}}</b></li>
        <ul>
        % for doc in docs[item]:
            % if docs[item][doc][2]:
            <li><a href='/doctor/{{docs[item][doc][2]}}/{{docs[item][doc][3]}}'>
                        {{doc}}</a>
            % else:
               <li>{{doc}}
            % end
                        <b>{{docs[item][doc][1]}}</b>&nbsp;
                        <a href='http://igis.ru/online{{docs[item][doc][0]}}'>
                         На сайт igis.ru</a>
            <form action='/subscribe' method="post">
             <input type="hidden" name="doc_name" value="{{doc}}">
             <input type="hidden" name="doc_url" value="{{docs[item][doc][0]}}">
             <input type="hidden" name="hospital_name" value="{{name}}">
              Время от:  <select name="fromtime">
                <option value="08">08</option>
                <option value="09">09</option>
                <option value="10">10</option>
                <option value="11">11</option>
                <option value="12">12</option>
                <option value="13">13</option>
                <option value="14">14</option>
                <option value="15">15</option>
                <option value="16">16</option>
                <option value="17">17</option>
                <option value="18">18</option>
                <option value="19">19</option>
                <option value="20">20</option>
            </select>
              до:  <select name="totime">
                <option value="08">08</option>
                <option value="09">09</option>
                <option value="10">10</option>
                <option value="11">11</option>
                <option value="12">12</option>
                <option value="13">13</option>
                <option value="14">14</option>
                <option value="15">15</option>
                <option value="16">16</option>
                <option value="17">17</option>
                <option value="18">18</option>
                <option value="19">19</option>
                <option selected="selected" value="20">20</option>
            </select>
              День от:  <select name="fromweekday">
                <option value="0">Понедельник</option>
                <option value="1">Вторник</option>
                <option value="2">Среда</option>
                <option value="3">Четверг</option>
                <option value="4">Пятница</option>
            </select>
              До дня недели:  <select name="toweekday">
                <option value="0">Понедельник</option>
                <option value="1">Вторник</option>
                <option value="2">Среда</option>
                <option value="3">Четверг</option>
                <option selected="selected" value="4">Пятница</option>
            </select>
            Автоподписка <select name="autouser">
                <option value="">-----</option>
                % for user in autousers:
                <option value="{{user}}">{{user}}</option>
                % end
            <input type="submit" value="Подписаться">
            </form></li>
        % end
        </ul>
% end
</ul>
""")


doctor_page = html.format("""
<a href='/'> Назад</a><br><br>
<b>{{name}}<br>
{{spec}}</b>
<br>
Номерки<br>
<ul>
% for t in tickets:
     <li>
         <form action='/get-ticket' method="post">
                          {{t[1]}} {{t[2]}} {{t[3]}}
             <input type="hidden" name="doc_name" value="{{name}}">
             <input type="hidden" name="ticket" value="{{t[0]}}">
             <input type="hidden" name="hosp_id" value="{{t[4]}}">
            <select name="autouser">
                <option value="">-----</option>
                % for user in autousers:
                <option value="{{user}}">{{user}}</option>
                % end
            <input type="submit" value="Записаться">
            </form>
     </li>
% end
</ul>
""")


subscriptions_page = html.format("""
<a href='/'> Назад</a><br><br>
<ul>
% for item in name:
    % if len(name[item]):
    <li><b>{{item}}</b></li>
        <ul>
        % for doc in name[item]:
           <li><form action='/unsubscribe' method="post">
           <a href='http://igis.ru/online{{doc.url}}'>{{doc.name}}</a>
           {{doc.user['fromtime']}}:00 - {{doc.user['totime']}}:00
           [{{dmap[doc.user['fromweekday']]}}-{{dmap[doc.user['toweekday']]}}]
           % if doc.user['autouser']:
               (Автозапись: {{doc.user['autouser']}})
           % end
               <input type="hidden" name="doc_url" value="{{doc.url}}">
               <input type="hidden" name="doc_name" value="{{doc.name}}">
               <input type="hidden" name="hospital_name" value="{{item}}">
           <input type="submit" value="Отписаться">
           </form></li>
        % end
        </ul>
    % end
% end
</ul>
""")

categories_page = html.format("""
<a href='/'> Назад</a><br><br>
% for item in name:
        <table>
        <tr>
            <td><img src="http://igis.ru/{{item[0]}}"></td>
            <td><a href='/hospital/{{item[1][0]}}'> {{item[1][1]}}</a><br>
               {{item[2]}}<br>
                <form action='/tickets' method="post">
                    <input type="hidden" name="hosp_name" value="{{item[1][1]}}">
                    <input type="hidden" name="hosp_id" value="{item[1][0]{}}">
                    <input type="submit" value="Посмотреть номерки">
                    </form>
        </tr>
        </table>
% end
""")


get_ticket_page = html.format("""
<b>Номерок оформлена для: {{name}}</b>!
<br>
{{message}}
<br>
<a href='/'>На главную</a>
""")


tickets_page_get = html.format("""
<b>Вы: {{name}}</b>!
<br>
{{message}}
<br>
<a href='/'>На главную</a>
""")


subscribed_page = html.format("""
<b>Подписка оформлена для: {{name}}</b>!
<br>
<a href='/'>На главную</a>
""")


subscribe_error = html.format("""
<b>Ошибка подписки: {{message}}</b>!
<br>
<a href='{{referer}}'>Назад</a>
""")

unsubscribed_page = html.format("""
<b>Подписка удалена для: {{name}}</b>!
<br>
<a href='/'>На главную</a>
""")


tickets_view_page = html.format("""
<h1>{{hosp_name}}</h1>
<h2>Пациент: {{name}}</h2>
""")


def is_logined():
    return request.get_cookie("logined", secret='some-secret-key')


def check_login(f):
    def decorated(*args, **kwargs):
        if is_logined():
            return f(*args, **kwargs)
        else:
            if request.path == '/':
                redirect("/login")
            else:
                redirect("/login{0}".format(request.path))
    return decorated


def validate(name, password):
    users = load_file(AUTH_FILE)
    if users.get(name):
        if users[name].get('password') == password:
            return True
    return False


def _hospital_id(doc_url):
    return doc_url.split('&')[0][5:]


def _doc_id(doc_url):
    return doc_url.split('&')[2][3:]


def check_igis_login(hospital_id, autouser):
    user = request.get_cookie("logined", secret='some-secret-key')
    surename = autouser.split(' ')[0]
    auth_info = load_file(AUTH_FILE)
    polis = auth_info[user]['auth'][autouser]
    return Igis.login(hospital_id, surename, polis)


def get_auto_users():
    auth_info = load_file(AUTH_FILE)
    user = request.get_cookie("logined", secret='some-secret-key')
    return [u for u in auth_info[user].get('auth', [])]


@route('/login')
def login():
    qkeys = list(request.query.keys())
    return template(login_page, referer=qkeys[0] if qkeys else '/')


@route('/logout')
def logout():
    response.set_cookie("logined", False, secret='some-secret-key')
    redirect("/")


@route('/login', method='POST')
def do_login():
    name = request.forms.get('name')
    password = request.forms.get('password')
    referer = request.forms.get('referer')
    if validate(name, password):
        response.set_cookie("logined", name, secret='some-secret-key')
        redirect(referer)
    else:
        return template(not_autorized_page, referer=referer)


@route('/')
@check_login
def index():
    return template(index_page,
                    username=request.get_cookie("logined",
                                                secret='some-secret-key'))


@route('/category/<index>')
@check_login
def categories(index):
    data = requests.get('https://igis.ru/online?tip={0}'.format(index), verify=False)
    links = []
    if data.ok:
        soup = BeautifulSoup(data.text, 'html.parser')
        images = [i.attrs['style'].split(' ')[1][4:-1]
                  for i in soup.find_all('div', class_='hide-sm')[1:]]
        links = [(i.attrs['href'][5:], i.b.text)
                 for i in soup.find_all('a') if i.attrs.get('href')
                 and 'obj=' in i.attrs['href']]
        address = [i.text for i in soup.find_all('div')
                   if i.attrs.get('style')
                   and 'padding:10px 0 0 0;' in i.attrs['style']]
        return template(categories_page, name=zip(images, links, address))
    else:
        abort(400, "Какая-то ошибка")


@route('/hospital/<index>')
@check_login
def hospital(index):
    data = requests.get(
        'https://igis.ru/online?obj={0}&page=zapdoc'.format(index), verify=False)
    all_doctors = OrderedDict()
    if data.ok:
        soup = BeautifulSoup(data.text, 'html.parser')
        name = soup.find_all('h2')[1].text
        for c in soup.find_all('table')[5].children:
            try:
                category = c.h2.text
                continue
            except AttributeError:
                pass
            doc = all_doctors.setdefault(category, {})
            if 'Номерков нет' in str(c):
                doc[c.b.text] = (c.a.attrs['href'], '0', 0, 0)
            if 'Всего номерков' in str(c):
                items = c.a.attrs['href'].split('&')
                doc[c.b.text] = (c.find_all('a')[1].attrs['href'],
                                 c.find_all('a')[1].u.text,
                                 items[0][5:], items[2][3:])
        autousers = get_auto_users()
        back = request.get_header('Referer')
        return template(hospital_page, docs=all_doctors, back=back, name=name,
                        autousers=autousers)
    else:
        abort(400, "Ошибка")


@route('/doctor/<hosp_id>/<doc_id>')
@check_login
def doctor(hosp_id, doc_id):
    data = requests.get(
        'https://igis.ru/online?obj={0}&page=doc&id={1}'.format(hosp_id, doc_id), verify=False)
    if not data.ok:
        abort(400, "Ошибка загрузки страницы")
    soup = BeautifulSoup(data.text, 'html.parser')
    doc_info = soup.find("div", style="line-height:1.5;")
    name = doc_info.find_all("b")[0].text
    spec = [i for i in doc_info.children][5]
    autousers = get_auto_users()
    tickets = []
    for href in find_available_tickets(soup):
        info = TicketInfo(href)
        day = info.date
        day_string = "{0}.{1:02}.{2}".format(day[0], day[1], day[2])
        weekday = info.weekday
        tickets.append([info.link, day_string, DAYS_MAP[str(weekday)],
                        info.time, hosp_id])
    return template(doctor_page, name=name, spec=spec, tickets=tickets,
                    autousers=autousers)


@route('/get-ticket', method='POST')
@check_login
def get_ticket():
    hosp_id = request.forms.hosp_id
    doc_name = request.forms.doc_name
    ticket = request.forms.ticket
    autouser = request.forms.autouser
    referer = request.headers.get('Referer')
    if not autouser:
        return template(
            subscribe_error,
            message="Невозмоно получить номерок. Нет указана фамилия",
            referer=referer)
    cookies = check_igis_login(hosp_id, autouser)
    if cookies:
        if Igis.subscribe(ticket, cookies):
            ticket_date = ticket.split('&')[2][2:]
            ticket_time = ticket.split('&')[3][2:]
            message = 'Номерок: {0} {1}'.format(ticket_date, ticket_time)
            return template(get_ticket_page, name=doc_name,
                            message=message, referer=referer)
        else:
            return template(
                subscribe_error,
                message="Невозмоно получить номерок. Возможно вы уже записаны.",
                referer=referer)
    else:
        return template(subscribe_error, message="Невозможно авторизоваться",
                        referer=referer)


@route('/tickets', method='POST')
@check_login
def tickets_view():
    referer = request.headers.get('Referer')
    hosp_id = request.forms.hosp_id
    hosp_name = request.forms.hosp_name
    autouser = request.forms.autouser
    name = 'name'
    if not autouser:
        return template(
            subscribe_error,
            message="Невозмоно получить номерок. Нет указана фамилия",
            referer=referer)
    cookies = check_igis_login(hosp_id, autouser)
    if cookies:
        data = requests.get(
            'https://igis.ru/online?obj={0}}'.format(hosp_id),
            cookies=cookies, verify=False)
        if not data.ok:
            abort(400, "Ошибка загрузки страницы")
    else:
        return template(subscribe_error, message="Невозможно авторизоваться",
                        referer=referer)
    soup = BeautifulSoup(data.text, 'html.parser')
    return template(tickets_view_page, hosp_name=hosp_name, name=name)


@route('/subscriptions')
@check_login
def subscriptions():
    subs = load_file(SUBSCRIPTIONS)
    user = request.get_cookie("logined", secret='some-secret-key')
    doc_dict = {}
    for hosp_id, hosp_info in subs.items():
        doc_dict[hosp_info['name']] = []
        for doc_id, doc_info in hosp_info['doctors'].items():
            if user in doc_info['subscriptions'].keys():
                doc_url = '?obj={0}&page=doc&id={1}'.format(hosp_id, doc_id)
                user_info = doc_info['subscriptions'][user]
                doc_dict[hosp_info['name']].append(
                    DocInfo(doc_info['name'], doc_url, user_info))
    return template(subscriptions_page, name=doc_dict, dmap=DAYS_MAP)


@route('/subscribe', method='POST')
@check_login
def subscribe():
    doc_name = request.forms.doc_name
    doc_url = request.forms.doc_url
    hospital_name = request.forms.hospital_name
    fromtime = request.forms.fromtime
    totime = request.forms.totime
    fromweekday = request.forms.fromweekday
    toweekday = request.forms.toweekday
    referer = request.headers.get('Referer')
    if totime < fromtime:
        return template(subscribe_error,
                        message="Время начала больше время окончания",
                        referer=referer)
    if toweekday < fromweekday:
        return template(subscribe_error,
                        message="Неправильно заданы дни недели",
                        referer=referer)
    autouser = request.forms.autouser
    if not all([hospital_name, doc_name, doc_url,  fromtime, totime]):
        abort(400, "Некорректный запрос")
    hospital_id = _hospital_id(doc_url)
    doc_id = _doc_id(doc_url)
    with FileLock(LOCK_FILE):
        subs = load_file(SUBSCRIPTIONS)
        hospital = subs.setdefault(hospital_id, {})
        hospital['name'] = hospital_name
        doctors = hospital.setdefault('doctors', {})
        doctor = doctors.setdefault(doc_id, {})
        doctor['name'] = doc_name
        subscriptions = doctor.setdefault('subscriptions', {})
        user = request.get_cookie("logined", secret='some-secret-key')
        user_info = subscriptions.setdefault(user, {})
        user_info['fromtime'] = fromtime
        user_info['totime'] = totime
        user_info['fromweekday'] = fromweekday
        user_info['toweekday'] = toweekday
        user_info['autouser'] = autouser
        save_file(SUBSCRIPTIONS, subs)
    if autouser:
        if not check_igis_login(hospital_id, autouser):
            return template(subscribe_error,
                            message="Автоматическая запись невозможна",
                            referer=referer)
    return template(subscribed_page, name=doc_name)


@route('/unsubscribe', method='POST')
@check_login
def unsubscribe():
    lock = FileLock(LOCK_FILE)
    with lock:
        subs = load_file(SUBSCRIPTIONS)
        if not subs:
            return template("Нет подписок")
        doc_name = request.forms.doc_name
        doc_url = request.forms.doc_url
        hospital_name = request.forms.hospital_name
        name = request.get_cookie("logined", secret='some-secret-key')
        if not all([subs, doc_name, doc_url, hospital_name, name]):
            abort(400, "Некорректный запрос")
        hospital_id = _hospital_id(doc_url)
        doc_id = _doc_id(doc_url)
        del subs[hospital_id]['doctors'][doc_id]['subscriptions'][name]
        if not subs[hospital_id]['doctors'][doc_id]['subscriptions']:
            del subs[hospital_id]['doctors'][doc_id]
        if not subs[hospital_id]['doctors']:
            del subs[hospital_id]
        save_file(SUBSCRIPTIONS, subs)
    return template(unsubscribed_page, name=doc_name)


@route('/viber', method='POST')
def incoming():
    viber = Viber()
    logger.debug("Viber endpoint")

    data = request.body.read()
    if not viber.api.verify_signature(data, request.headers.get('X-Viber-Content-Signature')):
        return abort(403)
    viber_request = viber.api.parse_request(data)
    if isinstance(viber_request, ViberMessageRequest):
        viber.check_users(viber_request)


@route('/telegram', method='POST')
def incoming():
    telegram = Telegram()
    logger.debug("Telegram endpoint ")
    data = request.json
    telegram.check_users(data)


def main():
    run(host='localhost', port=8000, reloader=True, debug=True)


def cgi():
    run(server='cgi', debug=True)


if __name__ == '__main__':
    cgi()
    #main()
