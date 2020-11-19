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
     ul li {{ margin-top: 20px;}}
     a.main {{margin-left: 40px;
              font-size: large}}
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


signup_page = html.format("""
<table>
    <tr>
        <td><img src="waiter.png"></td>
        <td><h1>Придумайте себе имя и пароль</h1></td>
    </tr>
</table>
{{message}}
<form enctype="multipart/form-data" action="/signup" method="post">
    Имя: <input name="name" type="text" /><br>
    Пароль:          <input name="password1" type="password" /><br>
    Повторте пароль: <input name="password2" type="password" /><br>
    <input value="Зарегистрироваться" type="submit" />
</form>
""")

login_page = html.format("""
<table>
    <tr>
        <td><img src="waiter.png"></td>
        <td><h1>Номеркождун ждет входа</h1></td>
    </tr>
</table>
{{message}}
<form action="/login" method="post">
    Имя: <input name="name" type="text" />
    Пароль: <input name="password" type="password" />
    <input name="referer" value="{{referer}}" type="hidden" />
    <input value="Логин" type="submit" />
</form>
<a href="/">На главную</a>
""")

not_autorized_page = html.format("""
Неверный логин или пароль.
Пройдите авторизацию снова <a href="/login?{{referer}}">Авторизация</a>
<br><br>
<a href="/">Главная</a>
""")

unregistered_index_page = html.format("""
<table>
    <tr>
        <td><img src="waiter.png"></td>
        <td><h1>Добро пожаловать на сайт номеркождуна.</h1></td>
    </tr>
</table>
Если у вас есть учетная запись <a href="/login">войдите в систему</a>
<br>
Если нет учетной записи, <a href="/signup">зарегиструйтеcь</a>
""")

registered_index_page = html.format("""
<table>
    <tr>
        <td><img src="waiter.png"></td>
        <td><h1>Номеркождун: {{username}}</h1></td>
    </tr>
</table>
<a href='category/1' class='main'>Взрослые больницы</a><br>
<a href='category/2' class='main'>Детские больницы</a><br>
<a href='category/3' class='main'>Стоматологии</a><br>
<a href='category/4' class='main'>Диспансеры и спецучереждения</a>
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
                    <input type="hidden" name="hosp_id" value="{{item[1][0]}}">
                    <input type="hidden" name="category" value="{{category}}">
                    <select name="autouser">
                        <option value="">-----</option>
                        % for user in autousers:
                        <option value="{{user}}">{{user}}</option>
                        % end
                    <input type="submit" value="Посмотреть существующие записи">
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
<br>
  % for line in info:
    {{line}}<br>
  % end
<a href={{igispage}}>Страница больницы на igis</a>
<br>
<a href='/category/{{category}}'>Назад</a>
<br>
<a href='/'>На главную</a>
""")