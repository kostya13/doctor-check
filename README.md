# doctor-check

Скрипт для просмотра свободных номерков к врачу.
И сканер для ожидания новых номерков на сайте igis.ru

Работает на python 3.6

Сервис уведомления о свободной записи к врачу "Номеркождун"
Сайт https://doctor.kx13.ru

# Развертывание приложение на сайте justhost

В панели Directadmin подраздел "Дополнительные опции" пункт "Setup Python App"
Должно быть установлено хоть одно приложение.
Если приложение будет в корневом домене, то можно настроить прямо там.
Если сервис будет в домене третьего уровня, например "doctor.kx13.ru", 
то дополнительную настройку надо проводить вручную

Необходимо будет отредактировать .htaccess для нужного домена.
Например содержимое файла:
./domains/kx13.ru/public_html/doctor/.htaccess

```buildoutcfg
PassengerAppRoot "/home/u63341pyl/doctor"
PassengerBaseURI "/"
PassengerPython "/home/u63341pyl/virtualenv/kx13/3.7/bin/python3.7"
# DO NOT REMOVE. CLOUDLINUX PASSENGER CONFIGURATION END
# DO NOT REMOVE OR MODIFY. CLOUDLINUX ENV VARS CONFIGURATION BEGIN
<IfModule Litespeed>
</IfModule>
```
Путь `PassengerPython` должно указывать на виртуальное окружение,
которое было настроено в разделе "Setup Python App".

## Перезагрузка сайта после внесения изменений

в каталоге `~/doctor/tmp` находится файл `restart.txt` необходимо изменить его
содержимое на любые даные. Система заметит, что файл изменился
и перезагрузит сайт.

# Разработка и тестирование сервиса

Для тестов и разработки надо запускать скрипт `wsgiserver.py`

# Инструкция для пользователей

* Передать администратору логин и пароль
* В мессенджере Telegram или Viber подписаться на бота igismedbot
* Отправить боту сообщение в котором будет только ваш логин
* Получить уведомление от бота, что вы зарегистрированы
* Зайти на сайт со своми реквизитами
* Выбрать больницу и врача и нажать кнопку "Подписаться"
* Когда у врача появится доступные номерки вам придет уведомление

## Возможности для премиум аккаунтов

Если вы передали администратору так же Имя, Фамилию, полис пациента, то данный сервис может
автоматически записать пациента к врачу, как только появится свободный номерок.
Или можно подписываться на врача прямо с сайта.

# Как добавить нового пользователя

При регистрации необходимо предоставить логин для уведомлений.
Логин и пароль пользователя заносятся в файл auth.json
После этого пользователь может зарегистрировать свой мессенджер в системе.
Для подключиться к боту igismedbot и отправить ему свой логин. 
Поддерживаются Telegram и Viber
Если пользватель уже зарегистрирован, то если отправить команду /pass бот пришлет пароль пользователя

Если необходима автозапись список лиц с номером полиса в формате:
Фамилия Имя номер-полиса
должен быть занесен в раздел "auth" пользователя в файле auth.json

# Настройка мессенджеров

Для того, чтобы настроить вебхуки для мессенджеров, сначала в файле tokens.py надо внести
правильные токены для мессенджеров.
Далее в фаилах *botsetup.py прописать правиьлный путь до вебхука.
И запустить эти файлы.
