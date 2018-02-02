# -*- coding: utf-8 -*-
from bottle import route, run, template, abort, request, response, redirect
import requests
import time
import datetime
from bs4 import BeautifulSoup
from collections import OrderedDict
from doctor_check.services import igis_login, get_subscribe
from doctor_check import (SUBSCRIPTIONS, AUTH_FILE, LOCK_FILE,
                          load_file, save_file)
from filelock import FileLock


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
Пройдите авторизацию снова <a href="/login">Авторизация</a>
<br><br>
<a href="/">Главная</a>
""")

index_page = html.format("""
<table>
    <tr>
        <td><img src="ждун.png"></td>
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

hosp_page = html.format("""
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
                <option value="06">06</option>
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
                <option value="06">06</option>
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
         <form action='/appointment' method="post">
                          {{t[1]}} {{t[2]}} {{t[3]}}
             <input type="hidden" name="doc_name" value="{{name}}">
             <input type="hidden" name="tiket" value="{{t[0]}}">
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


sub_page = html.format("""
<a href='/'> Назад</a><br><br>
<ul>
% for item in name:
    % if len(name[item]):
    <li><b>{{item}}</b></li>
        <ul>
        % for doc in name[item]:
            <li><form action='/unsubscribe' method="post">
            <a href='http://igis.ru/online{{doc[1]}}'>{{doc[0]}}</a>
            {{doc[2]['fromtime']}}:00 - {{doc[2]['totime']}}:00
            [{{dmap[doc[2]['fromweekday']]}} - {{dmap[doc[2]['toweekday']]}}]
            % if doc[2]['autouser']:
                (Автозапись: {{doc[2]['autouser']}})
            % end
                <input type="hidden" name="doc_url" value="{{doc[1]}}">
                <input type="hidden" name="doc_name" value="{{doc[0]}}">
                <input type="hidden" name="hospital_name" value="{{item}}">
            <input type="submit" value="Отписаться">
            </form></li>
        % end
        </ul>
    % end
% end
</ul>
""")

cat_page = html.format("""
<a href='/'> Назад</a><br><br>
<ul>
% for item in name:
    <li><a href='/hospital/{{item[0]}}'> {{item[1]}}</a></li>
% end
</ul>
""")

subs_page = html.format("""
<b>Подписка оформлена для: {{name}}</b>!
<br>
<a href='/'>Назад</a>
""")

appointment_page = html.format("""
<b>Номерок оформлена для: {{name}}</b>!
<br>
{{message}}
<br>
<a href='/'>Назад</a>
""")


subs_error = html.format("""
<b>Ошибка подписки: {{message}}</b>!
<br>
<a href='{{referer}}'>Назад</a>
""")

unsubs_page = html.format("""
<b>Подписка удалена для: {{name}}</b>!
<br>
<a href='/'>Назад</a>
""")


def is_logined():
    return request.get_cookie("logined", secret='some-secret-key')


def check_login(f):
    def decorated(*args, **kwargs):
        if is_logined():
            return f(*args, **kwargs)
        else:
            redirect("/login")
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


@route('/login')
def login():
    referer = request.headers.get('Referer')
    return template(login_page, referer=referer if referer else '/')


@route('/logout')
def logout():
    response.set_cookie("logined", False, secret='some-secret-key')
    redirect("/")


@route('/login', method='POST')
def do_login():
    name = request.forms.get('name')
    password = request.forms.get('password')
    if validate(name, password):
        response.set_cookie("logined", name, secret='some-secret-key')
        redirect('/')
    else:
        return template(not_autorized_page)


@route('/')
@check_login
def index():
    return template(index_page,
                    username=request.get_cookie("logined",
                                                secret='some-secret-key'))


@route('/category/<index>')
@check_login
def categories(index):
    data = requests.get('http://igis.ru/online?tip={0}'.format(index))
    links = []
    if data.ok:
        soup = BeautifulSoup(data.text, 'html.parser')
        for link in soup.find_all('a'):
            href = link.attrs.get('href')
            if href and 'obj='in href:
                links.append((href[5:], link.b.text))
        return template(cat_page, name=links)
    else:
        abort(400, "Какая-то ошибка")


@route('/hospital/<index>')
@check_login
def hospital(index):
    data = requests.get(
        'http://igis.ru/online?obj={0}&page=zapdoc'.format(index))
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
        auth_info = load_file(AUTH_FILE)
        user = request.get_cookie("logined", secret='some-secret-key')
        autousers = [u for u in auth_info[user].get('auth', [])]
        back = request.get_header('Referer')
        return template(hosp_page, docs=all_doctors, back=back, name=name,
                        autousers=autousers)
    else:
        abort(400, "Ошибка")


@route('/doctor/<hosp_id>/<doc_id>')
@check_login
def doctor(hosp_id, doc_id):
    data = requests.get(
        'http://igis.ru/online?obj={0}&page=doc&id={1}'.format(hosp_id, doc_id))
    if not data.ok:
        abort(400, "Ошибка загрузки страницы")
    soup = BeautifulSoup(data.text, 'html.parser')
    hrefs = [button.attrs['href'].encode('utf-8')
             for button in soup.find_all("a", class_="btn green")
             if button.attrs['href'].startswith('javascript:winbox')]
    doc_info = soup.find("div", style="line-height:1.5;")
    name = doc_info.find_all("b")[0].text
    spec = [i for i in doc_info.children][5]
    hrefs.sort(key=lambda x: x.split('&')[2])
    auth_info = load_file(AUTH_FILE)
    user = request.get_cookie("logined", secret='some-secret-key')
    autousers = [u for u in auth_info[user].get('auth', [])]
    tickets = []
    for href in hrefs:
        items = href.split('&')
        day = items[2][2:]
        day_string = "{0}.{1}.{2}".format(day[0:4], day[4:6], day[6:8])
        t = time.strptime(day, "%Y%m%d")
        weekday = datetime.date(*t[0:3]).weekday()
        href_time = href.split('&')[3][2:7]
        link = href.split(',')[1][1:-1]
        tickets.append([link, day_string, DAYS_MAP[str(weekday)], href_time,
                        hosp_id])
    return template(doctor_page, name=name, spec=spec, tickets=tickets,
                    autousers=autousers)


@route('/appointment', method='POST')
@check_login
def appointment():
    hosp_id = request.forms.hosp_id
    doc_name = request.forms.doc_name
    tiket = request.forms.tiket
    autouser = request.forms.autouser
    referer = request.headers.get('Referer')
    if not autouser:
        return template(
            subs_error,
            message="Невозмоно получить номерок. Нет указана фамилия",
            referer=referer)
    surename = autouser.split(' ')[0]
    auth_info = load_file(AUTH_FILE)
    user = request.get_cookie("logined", secret='some-secret-key')
    polis = auth_info[user]['auth'][autouser]
    cookies = igis_login(hosp_id, surename,
                         polis)
    if cookies:
        if get_subscribe(tiket, cookies):
            tiket_date = tiket.split('&')[2]
            tiket_time = tiket.split('&')[3]
            message = 'Номерок: {0} {1}'.format(tiket_date, tiket_time)
            return template(appointment_page, name=doc_name,
                            message=message, referer=referer)
        else:
            return template(
                subs_error,
                message="Невозмоно получить номерок. Возможно вы уже записаны.",
                referer=referer)
    else:
        return template(subs_error, message="Невозможно авторизоваться",
                        referer=referer)


@route('/subscriptions')
@check_login
def subscriptions():
    subs = load_file(SUBSCRIPTIONS)
    user = request.get_cookie("logined", secret='some-secret-key')
    doc_dict = {}
    for hospital in subs:
        doc_dict[subs[hospital]['name']] = []
        all_doctors = subs[hospital]['doctors']
        for doc in all_doctors:
            if user in all_doctors[doc]['subscriptions'].keys():
                doc_url = '?obj={0}&page=doc&id={1}'.format(hospital, doc)
                user_info = all_doctors[doc]['subscriptions'][user]
                doc_dict[subs[hospital]['name']].append(
                    (all_doctors[doc]['name'], doc_url, user_info))
    return template(sub_page, name=doc_dict, dmap=DAYS_MAP)


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
        return template(subs_error,
                        message="Время начала больше время окончания",
                        referer=referer)
    if toweekday < fromweekday:
        return template(subs_error,
                        message="Неправильно заданы дни недели",
                        referer=referer)
    autouser = request.forms.autouser
    if not all([hospital_name, doc_name, doc_url,  fromtime, totime]):
        abort(400, "Некорректный запрос")
    user = request.get_cookie("logined", secret='some-secret-key')
    hospital_id = _hospital_id(doc_url)
    doc_id = _doc_id(doc_url)
    lock = FileLock(LOCK_FILE)
    with lock:
        subs = load_file(SUBSCRIPTIONS)
        hospital = subs.setdefault(hospital_id, {})
        hospital['name'] = hospital_name
        doctors = hospital.setdefault('doctors', {})
        doctor = doctors.setdefault(doc_id, {})
        doctor['name'] = doc_name
        subscriptions = doctor.setdefault('subscriptions', {})
        users = subscriptions.setdefault(user, {})
        users['fromtime'] = fromtime
        users['totime'] = totime
        users['fromweekday'] = fromweekday
        users['toweekday'] = toweekday
        users['autouser'] = autouser
        if autouser:
            surename = autouser.split(' ')[0]
            auth_info = load_file(AUTH_FILE)
            polis = auth_info[user]['auth'][autouser]
            if not igis_login(hospital_id, surename, polis):
                return template(subs_error,
                                message="Автоматическая запись невозможна",
                                referer=referer)
        save_file(SUBSCRIPTIONS, subs)
    return template(subs_page, name=doc_name)


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
    return template(unsubs_page, name=doc_name)


def main():
    run(host='localhost', port=8000, reloader=True, debug=True)


def cgi():
    run(server='cgi', debug=True)
