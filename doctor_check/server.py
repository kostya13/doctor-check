import logging
from collections import OrderedDict

import requests
import bottle
from bottle import route, run, template, abort, request, response, redirect
from bs4 import BeautifulSoup
from viberbot.api.viber_requests import ViberMessageRequest

from doctor_check import (find_available_tickets, PatientsFile, CookiesFile, DocInfo, AuthFile, SubscriptionsFile,
                          TicketInfo, format_date, templates, DAYS_MAP)
from doctor_check.services import Igis, Viber, Telegram

logger = logging.getLogger()


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
                redirect("/login?{0}".format(request.path))
    return decorated


def _hospital_id(doc_url):
    return doc_url.split('&')[0][5:]


def _doc_id(doc_url):
    return doc_url.split('&')[2][3:]


@route('/signup')
def signup():
    message = request.query.get('msg', '')
    if message == 'passmismatch':
        message = "Пароли не совпадают"
    elif message == 'userexists':
        message = "Пользователь с этим именем уже существует"
    elif message == 'nopassword':
        message = "Пустой пароль"
    return template(templates.signup_page, message=message   )


@route('/signup', method='POST')
def do_signup():
    name = request.forms.name.strip()
    password1 = request.forms.password1
    password2 = request.forms.password2
    if not password1:
        redirect("/signup?" + 'msg=nopassword')
    with AuthFile() as auth:
        if name in auth.registered_users():
            redirect("/signup?" + 'msg=userexists')
        elif password1 != password2:
            redirect("/signup?" + 'msg=passmismatch')
        else:
            auth.db[name] = password1
    response.set_cookie("logined", name, secret='some-secret-key')
    redirect("/")


@route('/login')
def login():
    qkeys = list(request.query.keys())
    return template(templates.login_page, referer=qkeys[0] if qkeys else '/', message='')


@route('/logout')
def logout():
    response.set_cookie("logined", False, secret='some-secret-key')
    redirect("/")


@route('/login', method='POST')
def do_login():
    name = request.forms.name
    password = request.forms.password
    referer = request.forms.referer
    with AuthFile() as auth:
        if auth.db.get(name) == password:
            response.set_cookie("logined", name, secret='some-secret-key')
            redirect(referer)
        else:
            return template(templates.login_page, message='Неверный логин или пароль', referer=referer)


@route('/')
def index():
    if is_logined():
        return template(templates.registered_index_page, username=is_logined())
    else:
        return template(templates.unregistered_index_page, username=is_logined())


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
        user = is_logined()
        with PatientsFile() as patients:
            autousers = patients.get_names(user)
        return template(templates.categories_page, name=zip(images, links, address), category=index,
                        autousers=autousers)
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
        user = is_logined()
        with PatientsFile() as patients:
            autousers = patients.get_names(user)
        back = request.get_header('Referer')
        return template(templates.hospital_page, docs=all_doctors, back=back, name=name,
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
    user = is_logined()
    with PatientsFile() as patients:
        autousers = patients.get_names(user)
    tickets = []
    for href in find_available_tickets(soup):
        info = TicketInfo(href)
        day = info.date
        day_string = "{0}.{1:02}.{2}".format(day[0], day[1], day[2])
        weekday = info.weekday
        tickets.append([info.link, day_string, DAYS_MAP[str(weekday)],
                        info.time, hosp_id])
    return template(templates.doctor_page, name=name, spec=spec, tickets=tickets,
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
            templates.subscribe_error,
            message="Невозможно получить номерок. Не указана фамилия",
            referer=referer)
    if Igis.subscribe(ticket, hosp_id, autouser, referer):
        ticket_date = ticket.split('&')[2][2:]

        ticket_time = ticket.split('&')[3][2:]
        message = 'Номерок: {0} {1}'.format(format_date(ticket_date), ticket_time)
        return template(templates.get_ticket_page, name=doc_name,
                        message=message, referer=referer)
    else:
        return template(
            templates.subscribe_error,
            message="Невозмонжо получить номерок. Возможно вы уже записаны.",
            referer=referer)


@route('/tickets', method='POST')
@check_login
def tickets_view():
    referer = request.headers.get('Referer')
    hosp_id = request.forms.hosp_id
    hosp_name = request.forms.hosp_name
    category = request.forms.category
    autouser = request.forms.autouser
    if not autouser:
        return template(
            templates.subscribe_error,
            message="Невозможно получить номерок. Не указана фамилия.",
            referer=referer)
    igis_page = 'https://igis.ru/online?obj={0}'.format(hosp_id)
    data = Igis.load_page(hosp_id, autouser, igis_page, referer)
    soup = BeautifulSoup(data.text, 'html.parser')
    info = soup.find_all('div', style='margin:15px 0;')
    if info:
        info = info[0].text.split('\n')
    return template(templates.tickets_view_page, hosp_name=hosp_name, name=autouser, info=info,
                    igispage=igis_page, category=category)


@route('/subscriptions')
@check_login
def subscriptions():
    with SubscriptionsFile() as subsdb:
        subs = subsdb.db
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
    return template(templates.subscriptions_page, name=doc_dict, dmap=DAYS_MAP)


@route('/subscribe', method='POST')
@check_login
def subscribe():
    logger.debug('subscribe')
    doc_name = request.forms.doc_name
    doc_url = request.forms.doc_url
    hospital_name = request.forms['hospital_name']
    fromtime = request.forms.fromtime
    totime = request.forms.totime
    weekdays = [request.forms.get(d) for d in ("monday", "tuesday", "wednesday", "thursday", "friday")
                if d in request.forms]
    referer = request.headers.get('Referer')
    if totime < fromtime:
        return template(templates.subscribe_error,
                        message="Время начала больше время окончания",
                        referer=referer)
    autouser = request.forms.autouser
    logger.debug(f'{hospital_name}, {doc_name}, {doc_url},  {fromtime}, {totime}, {weekdays}')
    if not all([hospital_name, doc_name, doc_url,  fromtime, totime]):
        abort(400, "Некорректный запрос")
    hospital_id = _hospital_id(doc_url)
    doc_id = _doc_id(doc_url)
    with SubscriptionsFile() as subs:
        hospital = subs.db.setdefault(hospital_id, {})
        hospital['name'] = hospital_name
        doctors = hospital.setdefault('doctors', {})
        doctor = doctors.setdefault(doc_id, {})
        doctor['name'] = doc_name
        subscriptions = doctor.setdefault('subscriptions', {})
        user = request.get_cookie("logined", secret='some-secret-key')
        user_info = subscriptions.setdefault(user, {})
        user_info['fromtime'] = fromtime
        user_info['totime'] = totime
        user_info['weekdays'] = weekdays
        user_info['autouser'] = autouser
    if autouser:
        with PatientsFile() as patients:
            polis = patients.db[user][autouser]
        with CookiesFile() as cookiedb:
            cookie = cookiedb.get(user, hospital_id, autouser)
        if not cookie:
            cookie = Igis.refresh_cookie(hospital_id, autouser, polis)
        if not cookie:
            return template(templates.subscribe_error,
                            message="Автоматическая запись невозможна",
                            referer=referer)
    return template(templates.subscribed_page, name=doc_name)


@route('/unsubscribe', method='POST')
@check_login
def unsubscribe():
    with SubscriptionsFile() as subsdb:
        subs = subsdb.db
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
    return template(templates.unsubscribed_page, name=doc_name)


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


application = bottle.default_app()
