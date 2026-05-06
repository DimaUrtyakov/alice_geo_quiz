from flask import Flask, request, jsonify
import json
import random

app = Flask(__name__)

# ---------- Данные ----------
with open('data.json', 'r', encoding='utf-8') as f:
    GEO_DATA = json.load(f)

# Хранилище сессий (в реальном проекте лучше БД)
user_sessions = {}


# ---------- Карты ----------
def get_map_url(lat, lon, zoom):
    # Без apikey, как в старом коде – спутниковый слой работал
    url = f"https://static-maps.yandex.ru/1.x/?ll={lon},{lat}&z={zoom}&l=sat&pt={lon},{lat},pm2rdm"
    return url


# ---------- Сессии ----------
def get_session(user_id):
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            'difficulty': None,
            'asked_ids': [],
            'current_question': None,
            'correct': 0,
            'wrong': 0,
            'max_questions': 5,
            'game_over': False
        }
    return user_sessions[user_id]


def reset_session(session):
    session['difficulty'] = None
    session['asked_ids'] = []
    session['current_question'] = None
    session['correct'] = 0
    session['wrong'] = 0
    session['game_over'] = False


# ---------- Логика игры ----------
def get_next_question(session):
    diff = session['difficulty']
    available = [q for q in GEO_DATA if q['difficulty'] == diff and q['id'] not in session['asked_ids']]
    if not available:
        return None
    question = random.choice(available)
    session['asked_ids'].append(question['id'])
    session['current_question'] = question
    return question


def check_answer(user_answer, correct_name):
    """Улучшенная проверка ответа"""
    user_answer = user_answer.lower().strip()
    correct_name = correct_name.lower().strip()

    # Прямое совпадение
    if user_answer == correct_name:
        return True

    # Проверка содержит ли ответ пользователя правильное название
    if correct_name in user_answer or user_answer in correct_name:
        return True

    # Убираем слово "это" в начале ответа
    if user_answer.startswith("это "):
        user_answer = user_answer[4:]
        if user_answer == correct_name or correct_name in user_answer:
            return True

    return False


# ---------- Вебхук Алисы ----------
@app.route('/post', methods=['POST'])
def webhook():
    req = request.json

    if not req or 'session' not in req:
        return jsonify({
            "response": {
                "text": "Произошла ошибка. Попробуйте перезапустить навык.",
                "end_session": True
            },
            "version": "1.0"
        })

    user_id = req['session']['user_id']
    command = req['request'].get('command', '').lower().strip()
    session = get_session(user_id)
    response_text = ""
    end_session = False
    buttons = []  # по умолчанию кнопок нет

    print(
        f"DEBUG: user_id={user_id}, command='{command}', difficulty={session['difficulty']}, game_over={session.get('game_over')}")

    # Если игра окончена
    if session.get('game_over'):
        if 'да' in command or 'хочу' in command or 'сыгр' in command or 'ещё' in command:
            reset_session(session)
            response_text = "Отлично! Выберите сложность: лёгкая, средняя или сложная."
            buttons = [
                {"title": "Лёгкая", "hide": True},
                {"title": "Средняя", "hide": True},
                {"title": "Сложная", "hide": True}
            ]
        else:
            response_text = "Скажите 'да' или нажмите кнопку, чтобы сыграть снова."
            buttons = [
                {"title": "Да, хочу ещё", "hide": True},
                {"title": "Нет, спасибо", "hide": True}
            ]
            end_session = False  # не завершаем сессию, ждём ответа
        return jsonify({
            "response": {
                "text": response_text,
                "end_session": end_session,
                "buttons": buttons
            },
            "session": req['session'],
            "version": req['version']
        })

    # Команда "стоп"
    if 'стоп' in command or 'хватит' in command or 'законч' in command:
        total = session['correct'] + session['wrong']
        if total > 0:
            percent = (session['correct'] / total) * 100
            if percent == 100:
                grade = "Отлично! Вы настоящий знаток географии!"
            elif percent >= 60:
                grade = "Хороший результат!"
            else:
                grade = "Попробуйте ещё раз, чтобы улучшить результат."
            response_text = f"Игра завершена. Правильных ответов: {session['correct']} из {total}. {grade} Хотите сыграть ещё?"
        else:
            response_text = "Игра завершена. Вы не ответили ни на один вопрос. Хотите попробовать снова?"
        session['game_over'] = True
        session['current_question'] = None
        buttons = [
            {"title": "Да", "hide": True},
            {"title": "Нет", "hide": True}
        ]
        return jsonify({
            "response": {
                "text": response_text,
                "end_session": False,
                "buttons": buttons
            },
            "session": req['session'],
            "version": req['version']
        })

    # Приветствие / помощь
    if not command or 'помощь' in command or 'что ты умеешь' in command:
        if session['difficulty'] is None:
            response_text = "Привет! Я географический тест. Я показываю спутниковые снимки, а вы угадываете, что это за объект. Вас ждёт 5 вопросов. Назовите сложность: лёгкая, средняя или сложная."
            buttons = [
                {"title": "Лёгкая", "hide": True},
                {"title": "Средняя", "hide": True},
                {"title": "Сложная", "hide": True}
            ]
        else:
            response_text = "Вы уже играете. Продолжайте отвечать или скажите 'стоп' для завершения."
        return jsonify({
            "response": {
                "text": response_text,
                "end_session": end_session,
                "buttons": buttons
            },
            "session": req['session'],
            "version": req['version']
        })

    # Выбор сложности
    if session['difficulty'] is None:
        print(f"DEBUG: Проверяем сложность в команде: '{command}'")
        if 'лёгк' in command or 'легк' in command:
            session['difficulty'] = 'easy'
            print("DEBUG: Установлена сложность easy")
        elif 'средн' in command:
            session['difficulty'] = 'medium'
            print("DEBUG: Установлена сложность medium")
        elif 'сложн' in command:
            session['difficulty'] = 'hard'
            print("DEBUG: Установлена сложность hard")
        else:
            response_text = "Не поняла. Выберите сложность: лёгкая, средняя или сложная."
            buttons = [
                {"title": "Лёгкая", "hide": True},
                {"title": "Средняя", "hide": True},
                {"title": "Сложная", "hide": True}
            ]
            return jsonify({
                "response": {"text": response_text, "end_session": False, "buttons": buttons},
                "session": req['session'],
                "version": req['version']
            })

        # Начинаем игру: задаём первый вопрос
        q = get_next_question(session)
        if q is None:
            response_text = "К сожалению, вопросы этой сложности закончились. Выберите другую сложность."
            session['difficulty'] = None
            buttons = [
                {"title": "Лёгкая", "hide": True},
                {"title": "Средняя", "hide": True},
                {"title": "Сложная", "hide": True}
            ]
        else:
            map_url = get_map_url(q['lat'], q['lon'], q['zoom'])
            diff_text = "лёгкой" if session['difficulty'] == 'easy' else "средней" if session[
                                                                                          'difficulty'] == 'medium' else "сложной"
            response_text = f"Вы выбрали {diff_text} сложность. {q['hint']}\n\nСпутниковый снимок: {map_url}\n\nЧто это за объект?"
            buttons = [
                {"title": "Подсказка", "hide": True},
                {"title": "Сдаюсь", "hide": True}
            ]
        return jsonify({
            "response": {"text": response_text, "end_session": False, "buttons": buttons},
            "session": req['session'],
            "version": req['version']
        })

    # Обработка подсказки и "Сдаюсь" внутри игрового процесса
    if session['current_question'] is not None:
        # Если запрошена подсказка
        if "подсказка" in command:
            hint = session['current_question']['hint']
            response_text = f"Вот подсказка: {hint} Так что же это?"
            buttons = [{"title": "Сдаюсь", "hide": True}]
            return jsonify({
                "response": {"text": response_text, "end_session": False, "buttons": buttons},
                "session": req['session'],
                "version": req['version']
            })

        # Если сдаётся
        if "сдаюсь" in command:
            session['wrong'] += 1
            feedback = f"Жаль. Это {session['current_question']['name']}. "
            total = session['correct'] + session['wrong']
            if total >= session['max_questions']:
                percent = (session['correct'] / session['max_questions']) * 100
                if percent == 100:
                    grade = "Это великолепный результат!"
                elif percent >= 60:
                    grade = "Хороший результат!"
                else:
                    grade = "Потренируйтесь ещё!"
                response_text = feedback + f"Тест завершён! Правильных ответов: {session['correct']} из {session['max_questions']}. {grade} Хотите сыграть ещё?"
                session['game_over'] = True
                session['current_question'] = None
                buttons = [
                    {"title": "Да", "hide": True},
                    {"title": "Нет", "hide": True}
                ]
            else:
                next_q = get_next_question(session)
                if next_q is None:
                    response_text = feedback + "Вопросы этой сложности закончились. " \
                                               f"Правильных ответов: {session['correct']} из {total}. Хотите сыграть ещё?"
                    session['game_over'] = True
                    session['current_question'] = None
                    buttons = [
                        {"title": "Да", "hide": True},
                        {"title": "Нет", "hide": True}
                    ]
                else:
                    map_url = get_map_url(next_q['lat'], next_q['lon'], next_q['zoom'])
                    progress = f"Вопрос {total + 1} из {session['max_questions']}"
                    response_text = feedback + f"{progress}\n{next_q['hint']}\n\nСпутниковый снимок: {map_url}\n\nВаш ответ?"
                    buttons = [
                        {"title": "Подсказка", "hide": True},
                        {"title": "Сдаюсь", "hide": True}
                    ]
            return jsonify({
                "response": {"text": response_text, "end_session": False, "buttons": buttons},
                "session": req['session'],
                "version": req['version']
            })

        # Обычная проверка ответа
        right_answer = session['current_question']['name']
        if check_answer(command, right_answer):
            session['correct'] += 1
            feedback = "✅ Правильно! "
        else:
            session['wrong'] += 1
            feedback = f"❌ Неправильно. Это {session['current_question']['name']}. "

        total = session['correct'] + session['wrong']
        if total >= session['max_questions']:
            percent = (session['correct'] / session['max_questions']) * 100
            if percent == 100:
                grade = "Это великолепный результат!"
            elif percent >= 60:
                grade = "Хороший результат!"
            else:
                grade = "Потренируйтесь ещё!"
            response_text = feedback + f"Тест завершён! Правильных ответов: {session['correct']} из {session['max_questions']}. {grade} Хотите сыграть ещё?"
            session['game_over'] = True
            session['current_question'] = None
            buttons = [
                {"title": "Да", "hide": True},
                {"title": "Нет", "hide": True}
            ]
        else:
            next_q = get_next_question(session)
            if next_q is None:
                response_text = feedback + "Вопросы этой сложности закончились. " \
                                           f"Правильных ответов: {session['correct']} из {total}. Хотите сыграть ещё?"
                session['game_over'] = True
                session['current_question'] = None
                buttons = [
                    {"title": "Да", "hide": True},
                    {"title": "Нет", "hide": True}
                ]
            else:
                map_url = get_map_url(next_q['lat'], next_q['lon'], next_q['zoom'])
                progress = f"Вопрос {total + 1} из {session['max_questions']}"
                response_text = feedback + f"{progress}\n{next_q['hint']}\n\nСпутниковый снимок: {map_url}\n\nВаш ответ?"
                buttons = [
                    {"title": "Подсказка", "hide": True},
                    {"title": "Сдаюсь", "hide": True}
                ]
        return jsonify({
            "response": {"text": response_text, "end_session": False, "buttons": buttons},
            "session": req['session'],
            "version": req['version']
        })
    else:
        response_text = "Кажется, произошла путаница. Давайте начнём заново. Назовите сложность: лёгкая, средняя или сложная."
        reset_session(session)
        buttons = [
            {"title": "Лёгкая", "hide": True},
            {"title": "Средняя", "hide": True},
            {"title": "Сложная", "hide": True}
        ]
        return jsonify({
            "response": {"text": response_text, "end_session": False, "buttons": buttons},
            "session": req['session'],
            "version": req['version']
        })


if __name__ == '__main__':
    app.run(debug=True, port=5000)