import requests
import json

# Исходные данные
data = [
    {"number": 7080871846, "value": 2},
    {"number": 189666990, "value": 1},
    {"number": 1642439716, "value": 1},
    {"number": 842399990, "value": 3},
    {"number": 437374127, "value": 2},
    {"number": 1675100793, "value": 1},
    {"number": 5223925938, "value": 1},
    {"number": 196270354, "value": 1},
    {"number": 898037520, "value": 8},
    {"number": 1759428633, "value": 4},
    {"number": 495344223, "value": 23},
    {"number": 122480034, "value": 8},
    {"number": 5239840088, "value": 12},
    {"number": 7033361038, "value": 6},
    {"number": 1016643763, "value": 2},
    {"number": 985831712, "value": 2},
    {"number": 1068661128, "value": 14},
    {"number": 600723869, "value": 9},
    {"number": 981782965, "value": 2},
    {"number": 88500528, "value": 9},
    {"number": 954682008, "value": 1},
    {"number": 1172065781, "value": 16},
    {"number": 1379624757, "value": 5},
    {"number": 7619082369, "value": 6},
    {"number": 298421462, "value": 7},
    {"number": 929871579, "value": 2},
    {"number": 7378608374, "value": 13},
    {"number": 311362872, "value": 23},
    {"number": 303455267, "value": 2},
    {"number": 375359345, "value": 5},
    {"number": 166469013, "value": 1},
    {"number": 5775629716, "value": 1},
    {"number": 1058693270, "value": 1},
]

result = []

for item in data:
    telegram_id = item["number"]
    url = f"http://server1c.freedom1.ru/UNF_CRM_WS/hs/Grafana/anydata?query=emploeyy&telegramId={telegram_id}"

    try:
        response = requests.get(url)
        name = response.json().get(
            "fio", "Неизвестно"
        )  # Предполагаем, что API возвращает JSON с полем "name"
    except:
        name = "Ошибка запроса"

    result.append(
        {"telegramId": telegram_id, "queryCount": item["value"], "name": name}
    )

# Сохраняем результат
with open("employees.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print("Готово! Данные сохранены в employees.json")
