#!/usr/bin/env python3
from doctor_check.tokens import VIBER_TOKEN, VIBER_NAME
from viberbot import Api
from viberbot.api.bot_configuration import BotConfiguration

bot_configuration = BotConfiguration(
	name=VIBER_NAME,
	avatar='',
	auth_token=VIBER_TOKEN
)
viber = Api(bot_configuration)
res = viber.set_webhook('https://doctor.kx13.ru:443/viber')
print(res)
