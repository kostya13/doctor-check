#!/usr/bin/env python3
from doctor_check.services import Telegram
import requests
telegram = Telegram()
res = requests.get(telegram.api_url + 'setWebhook?url=https://doctor.kx13.ru:443/telegram')
print(res)
