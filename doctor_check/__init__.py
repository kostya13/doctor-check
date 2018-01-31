import os
import json
import codecs

__version__ = '1.0'

EMAILCONFIG = 'email.json'
SUBSCRIPTIONS = 'subscriptions.json'
AUTH_FILE = 'auth.json'
LOCK_FILE = '/tmp/subscriptions.lock'
TELEGRAM_FILE = 'telegram.json'


def load_file(filename):
    try:
        with open(filename) as f:
            content = json.load(f)
    except (IOError, ValueError):
        content = {}
    return content


def save_file(filename, content):
    with codecs.open(filename, 'w', encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, encoding='utf-8', indent=2)
