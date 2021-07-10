"""
Для тестирования и запусков на рабочей машине
можно использоват этот скрипт
"""
from wsgiref.util import setup_testing_defaults
from wsgiref.simple_server import make_server
from doctor import application

with make_server('', 8000, application) as httpd:
    print("Serving on port 8000...")
    httpd.serve_forever()