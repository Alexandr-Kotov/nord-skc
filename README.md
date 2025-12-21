# NORD SKC

Desktop SCADA/СКЦ для агрегатов SERVA + JEREH.

## Запуск
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Настройка
Все подключения и параметры — в `config.yaml`.
Оператор IP не видит: выбирает агрегат по плитке (№ флота, госномер).

## Драйверы
- JEREH (Siemens S7): python-snap7
- SERVA: TCP 6565 + строка/CSV (по дампам)
