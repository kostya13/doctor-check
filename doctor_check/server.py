from bottle import route, run, template, abort, request
import requests
from bs4 import BeautifulSoup
import json


FILENAME = 'subscriptions.json'

@route('/')
def index():
    index_page = """
    <a href='category/1'>Взрослые больницы</a><br>
    <a href='category/2'>Детские больницы</a><br>
    <a href='category/3'>Стоматологии</a><br>
    <a href='category/4'>Диспансеры и спецучереждения</a>
    <br><br>
    <a href='subscriptions'>Текущие подписки</a>
    """
    return index_page


@route('/category/<index>')
def categories(index):
    data = requests.get('http://igis.ru/online?tip={}'.format(index))
    links = []
    if data.ok:
        soup = BeautifulSoup(data.text, 'html.parser')
        for link in soup.find_all('a'):
            href = link.attrs.get('href')
            if href and 'obj='in href:
                links.append((href[5:], link.b.text))
        cat_page = """
        <a href='{{back}}'> Назад</a><br><br>

        <ul>
        % for item in name:
            <li><a href='/hospital/{{item[0]}}'> {{item[1]}}</a></li>
        % end
        </ul>
        """
        back = request.get_header('Referer')
        return template(cat_page, name=links, back=back)
    else:
        abort("!!!")


@route('/hospital/<index>')
def hospital(index):
    data = requests.get(
        'http://igis.ru/online?obj={}&page=zapdoc'.format(index))
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
                doc = all_doctors.setdefault(category, {})
                doc[c.b.text] = (index, '0')
            if 'Всего номерков' in str(c):
                doc = all_doctors.setdefault(category, {})
                doc[c.b.text] = (c.find_all('a')[1].attrs['href'], c.find_all('a')[1].u.text)
        hosp_page = """
        <a href='{{back}}'> Назад</a><br><br>

        <ul>
        % for item in name:
            <li>{{item}}</li>
                <ul>
                % for doc in name[item]:
                    % if name[item][doc][1] == '0':
                    <li><form action='/subscribe' method="post">
                    {{doc}}
                     <input type="hidden" name="doctor" value="{{doc}}">
                     <input type="hidden" name="hospital" value="{{name[item][doc][0]}}">
                    <input type="submit" value="Подписаться">
                    </form></li>
                    % else:
                    <li><a href='http://igis.ru/online{{name[item][doc][0]}}'>{{doc}}</a> {{name[item][doc][1]}}</li>
                    % end
                % end
                </ul>

        % end
        </ul>
        """
        back = request.get_header('Referer')
        return template(hosp_page, name=all_doctors, back=back)
    else:
        abort("!!!")


@route('/subscriptions')
def subscriptions():
    try:
        with open(FILENAME) as f:
            subs = json.load(f)
    except IOError:
        subs = {}
    return template('<b>Подписки {{name}}</b>!', name=subs)


@route('/subscribe', method='POST')
def subscribe():
    try:
        with open(FILENAME) as f:
            subs = json.load(f)
    except IOError:
        subs = {}
    import pdb; pdb.set_trace()  # XXX BREAKPOINT
    doctor = request.forms.doctor
    hospital = request.forms.get('hospital')
    current = subs.setdefault(hospital, [])
    if doctor not in current:
        current.append(doctor)
    with open(FILENAME, 'w') as f:
        json.dump(subs, f)
    return template('<b>Подписка оформлена {{name}}</b>!', name=doctor)


@route('/unsubscribe', method='POST')
def unsubscribe():
    name = 1
    return template('<b>Hello {{name}}</b>!', name=name)


def main():
    run(host='localhost', port=8000, reloader=True)
    # run(server='gunicorn', host='0.0.0.0', port=8000)


if __name__ == "__main__":
    main()
