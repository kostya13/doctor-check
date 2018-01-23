from distutils.core import setup

setup(name='doctor-check',
      version='1.0',
      description='Поиск свободных номеров в igis',
      author='Konstantin Ilyashenko',
      author_email='kx13@ya.ru',
      packages=['doctor_check'],
      install_requires=['bs4', 'requests', 'bottle', 'gunicorn'],
      entry_points={
          'console_scripts': [
              'doctor-check=doctor_check.watch:main',
              'doctor-server=doctor_check.server:main']})
