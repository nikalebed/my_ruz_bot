from datetime import datetime

import requests


def get_student(name):
    url = 'https://ruz.hse.ru/api/search'
    payload = {'term': name, 'type': 'student'}
    r = requests.get(url, params=payload)
    return r.json()


def get_group(name):
    url = 'https://ruz.hse.ru/api/search'
    payload = {'term': name, 'type': 'type'}
    r = requests.get(url, params=payload)
    return r.json()


def get_schedule(id, date):
    url = 'https://ruz.hse.ru/api/schedule/student/' + id.decode("utf-8")
    payload = {'start': date,
               'finish': date, 'lng': 1}
    r = requests.get(url, params=payload)
    print(r.url)
    return r.content.decode('utf-8')
