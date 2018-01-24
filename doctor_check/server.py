from bottle import route, run, template, abort, request
import requests
from bs4 import BeautifulSoup
import json
from collections import OrderedDict


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
        <a href='/'> Назад</a><br><br>

        <ul>
        % for item in name:
            <li><a href='/hospital/{{item[0]}}'> {{item[1]}}</a></li>
        % end
        </ul>
        """
        return template(cat_page, name=links)
    else:
        abort(400, "Какая-то ошибка")


@route('/hospital/<index>')
def hospital(index):
    data = requests.get(
        'http://igis.ru/online?obj={}&page=zapdoc'.format(index))
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
                doc[c.b.text] = (c.find_all('a')[1].attrs['href'], c.find_all('a')[1].u.text)
                doc_id = c.a.attrs['href'].split('=')[3]
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
                    <li><a href='http://igis.ru/online{{docs[item][doc][0]}}'>{{doc}}</a> {{docs[item][doc][1]}}</li>
                    % end
                % end
                </ul>

        % end
        </ul>
        """
        back = request.get_header('Referer')
        return template(hosp_page, docs=all_doctors, back=back, name=name)
    else:
        abort(400, "!!!")


@route('/subscriptions')
def subscriptions():
    try:
        with open(FILENAME) as f:
            subs = json.load(f)
    except IOError:
        subs = {}
    except json.decoder.JSONDecodeError:
        abort(400, "Ошибка чтения файла")
    doctor = request.forms.doctor
    doc_id = request.forms.doc_id
    hospital = request.forms.get('hospital')
    sub_page = """
    <a href='{{back}}'> Назад</a><br><br>

    <ul>
    % for item in name:
        % if len(name[item]):
        <li>{{item}}</li>
            <ul>
            % for doc in name[item]:
                <li><form action='/unsubscribe' method="post">
                {{doc[0]}}
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
    back = request.get_header('Referer')
    return template(sub_page, name=subs, back=back)


@route('/subscribe', method='POST')
def subscribe():
    try:
        with open(FILENAME) as f:
            subs = json.load(f)
    except IOError:
        subs = {}
    except json.decoder.JSONDecodeError:
        abort(400, "Ошибка чтения файла")

    doctor = request.forms.doctor
    doc_id = request.forms.doc_id
    hospital = request.forms.hospital
    current = subs.setdefault(hospital, [])
    if doc_id not in [c[1] for c in current]:
        current.append([doctor, doc_id])
    with open(FILENAME, 'w') as f:
        json.dump(subs, f, ensure_ascii=False)
    subs_page = """
    <b>Подписка оформлена {{name}}</b>!
    <br>
    <a href='/'>Назад</a>
    """
    return template(subs_page, name=doctor)

@route('/unsubscribe', method='POST')
def unsubscribe():
    try:
        with open(FILENAME) as f:
            subs = json.load(f)
    except IOError:
        subs = {}
    if not subs:
        return template("Нет подписок")
    doctor = request.forms.doctor
    hospital = request.forms.hospital
    doc_id = request.forms.doc_id
    current = [d for d in subs.setdefault(hospital, []) if d[1] != doc_id]
    subs[hospital] = current
    with open(FILENAME, 'w') as f:
        json.dump(subs, f, ensure_ascii=False)
    unsubs_page = """
    <b>Подписка удалена {{name}}</b>!
    <br>
    <a href='/'>Назад</a>
    """
    return template(unsubs_page, name=doctor)


def main():
    run(host='localhost', port=8000, reloader=True)
    # run(server='gunicorn', host='0.0.0.0', port=8000)


if __name__ == "__main__":
    main()
