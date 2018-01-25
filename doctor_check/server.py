#!/home/kostya/venvs/igis2/bin/python2.7
# -*- coding: utf-8 -*-
import codecs
from bottle import route, run, template, abort, request, response, redirect
import requests
from bs4 import BeautifulSoup
import json
from collections import OrderedDict
import sys


FILENAME = 'subscriptions.json'

login_page = """
<form action="/login" method="post">
    Имя: <input name="name" type="text" />
    Пароль: <input name="password" type="password" />
    <input name="referer" value="{{referer}}" type="hidden" />
    <input value="Логин" type="submit" />
</form>
"""

not_autorized_page = """
Пройдите авторизацию снова <a href="/login">Авторизация</a>
<br><br>
<a href="/">Главная</a>
"""

index_page = """
<h1>Пользователь: {{username}}</h1>
<a href='category/1'>Взрослые больницы</a><br>
<a href='category/2'>Детские больницы</a><br>
<a href='category/3'>Стоматологии</a><br>
<a href='category/4'>Диспансеры и спецучереждения</a>
<br><br>
<a href='subscriptions'>Текущие подписки</a>
<br><br>
<a href='logout'>Выход</a>
"""

hosp_page = """
<a href='{{back}}'> Назад</a><br><br>
<h2>{{name}}</h2>
<ul>
% for item in docs:
    <li><b>{{item}}</b></li>
        <ul>
        % for doc in docs[item]:
            % if docs[item][doc][1] == '0':
            <li><form action='/subscribe' method="post">
            {{doc}}
              <input type="hidden" name="doctor" value="{{doc}}">
              <input type="hidden" name="doc_id" value="{{docs[item][doc][0]}}">
              <input type="hidden" name="hospital" value="{{name}}">
            <input type="submit" value="Подписаться">
            </form></li>
            % else:
            <li><a href='http://igis.ru/online{{docs[item][doc][0]}}'>
                {{doc}}</a> {{docs[item][doc][1]}}</li>
            % end
        % end
        </ul>
% end
</ul>
"""

sub_page = """
<a href='/'> Назад</a><br><br>
<ul>
% for item in name:
    % if len(name[item]):
    <li>{{item}}</li>
        <ul>
        % for doc in name[item]:
            <li><form action='/unsubscribe' method="post">
            <a href='http://igis.ru/online{{doc[1]}}'>{{doc[0]}}</a>
                <input type="hidden" name="doc_id" value="{{doc[1]}}">
                <input type="hidden" name="doctor" value="{{doc[0]}}">
                <input type="hidden" name="hospital" value="{{item}}">
            <input type="submit" value="Отписаться">
            </form></li>
        % end
        </ul>
    % end
% end
</ul>
"""

cat_page = """
<a href='/'> Назад</a><br><br>
<ul>
% for item in name:
    <li><a href='/hospital/{{item[0]}}'> {{item[1]}}</a></li>
% end
</ul>
"""

subs_page = """
<b>Подписка оформлена для: {{name}}</b>!
<br>
<a href='/'>Назад</a>
"""

unsubs_page = """
<b>Подписка удалена для: {{name}}</b>!
<br>
<a href='/'>Назад</a>
"""


def load_file(filename):
    try:
        with open(filename) as f:
            content = json.load(f)
    except (IOError, ValueError):
        content = {}
    return content


def save_file(filename, content):
    with codecs.open(filename, 'w', encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, encoding='utf-8')


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
    users = load_file('auth.json')
    if users.get(name):
        if users[name].get('password') == password:
            return users[name]['email']
    return None


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
    email = validate(name, password)
    if email:
        response.set_cookie("logined", email, secret='some-secret-key')
        response.set_cookie("username", name, secret='some-secret-key')
        redirect(request.forms.get('referer'))
    else:
        return template(not_autorized_page)


@route('/')
@check_login
def index():
    return template(index_page,
                    username=request.get_cookie("username",
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
            if 'Номерков нет' in str(c):
                doc = all_doctors.setdefault(category, {})
                doc[c.b.text] = (c.a.attrs['href'], '0')
            if 'Всего номерков' in str(c):
                doc = all_doctors.setdefault(category, {})
                doc[c.b.text] = (c.find_all('a')[1].attrs['href'],
                                 c.find_all('a')[1].u.text)
        back = request.get_header('Referer')
        return template(hosp_page, docs=all_doctors, back=back, name=name)
    else:
        abort(400, "!!!")


@route('/subscriptions')
@check_login
def subscriptions():
    subs = load_file(FILENAME)
    email = request.get_cookie("logined", secret='some-secret-key')
    doc_dict = {}
    for hospital in subs:
        doc_dict[hospital] = []
        for doc in subs[hospital]:
            if email in subs[hospital][doc]['emails']:
                doc_dict[hospital].append([subs[hospital][doc]['name'], doc])
    return template(sub_page, name=doc_dict)


@route('/subscribe', method='POST')
@check_login
def subscribe():
    subs = load_file(FILENAME)
    doctor = request.forms.doctor
    doc_id = request.forms.doc_id
    hospital = request.forms.hospital
    if not all([hospital, doctor, doc_id]):
        abort(400, "Некорректный запрос")
    email = request.get_cookie("logined", secret='some-secret-key')
    hospital_key = subs.setdefault(hospital, {})
    doc_id_key = hospital_key.setdefault(doc_id, {})
    doc_id_key['name'] = doctor
    emails = doc_id_key.setdefault('emails', [])
    if email not in emails:
        emails.append(email)
    save_file(FILENAME, subs)
    return template(subs_page, name=doctor)


@route('/unsubscribe', method='POST')
@check_login
def unsubscribe():
    subs = load_file(FILENAME)
    if not subs:
        return template("Нет подписок")
    doctor = request.forms.doctor
    hospital = request.forms.hospital
    doc_id = request.forms.doc_id
    email = request.get_cookie("logined", secret='some-secret-key')
    if not all([subs, doctor, doc_id, email]):
        abort(400, "Некорректный запрос")
    hospital_key = subs.setdefault(hospital, {})
    doc_id_key = hospital_key.setdefault(doc_id, {})
    if not doc_id_key:
        abort(400, "Некого отписывать")
    emails = doc_id_key.setdefault('emails', [])
    emails.remove(email)
    if not emails:
        del subs[hospital][doc_id]
    if not subs[hospital]:
        del subs[hospital]
    save_file(FILENAME, subs)
    return template(unsubs_page, name=doctor)


def main():
    run(host='localhost', port=8000, reloader=True, debug=True)


def cgi():
    run(server='cgi', debug=True)


if len(sys.argv) == 1:
    cgi()
else:
    main()
