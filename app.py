import logging
from flask import Flask, request, jsonify

app = Flask(__name__)

# Настройка логирования для отладки
logging.basicConfig(level=logging.INFO)


@app.route('/', methods=['POST'])
def main():
    # Получаем запрос от Алисы
    payload = request.json

    # Формируем ответ
    response = {
        'version': payload['version'],
        'session': payload['session'],
        'response': {
            'end_session': False,
            'text': 'Привет! Я готов к географической викторине. Начнем?'
        }
    }
    return jsonify(response)


if __name__ == '__main__':
    app.run()