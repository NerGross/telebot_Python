import random
import nltk

from config import BOT_CONFIG
import settings

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC

import telebot
from telebot import types

# создаем словарик  вопрос -ответ
X_texts = []  # реплики
y = []  # их классы

for intent, intent_data in BOT_CONFIG['intents'].items():
    for example in intent_data['examples']:
        X_texts.append(example)
        y.append(intent)

vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 4))
X = vectorizer.fit_transform(X_texts)
clf = LinearSVC().fit(X, y)


# функция поиска интента по полученной фразе
def get_intent(question):
    question_vector = vectorizer.transform([question])
    intent = clf.predict(question_vector)[0]

    examples = BOT_CONFIG['intents'][intent]['examples']
    for example in examples:
        dist = nltk.edit_distance(question, example)
        dist_percentage = dist / len(example)
        if dist_percentage < 0.4:
            return intent


# функция поиска готового ответа по по файлу:
def get_answer_by_intent(intent):
    if intent in BOT_CONFIG['intents']:
        phrases = BOT_CONFIG['intents'][intent]['responses']
        return random.choice(phrases)


# правило фильтрации принимающей фразы
def filter_text(text):
    text = text.lower()  # переводим в нижний регистр весь текст
    text = [c for c in text if
            c in 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя- ']  # фильтрует символы входящие в последовательность
    text = ''.join(text)
    return text


with open('dialogues.txt', encoding='utf-8') as f:
    content = f.read()
dialogues = [dialogue_line.split('\n') for dialogue_line in content.split('\n\n')]

questions = set()
qa_dataset = []  # [[q, a], ...]

for replicas in dialogues:
    if len(replicas) < 2:
        continue

    question, answer = replicas[:2]
    question = filter_text(question[2:])
    answer = answer[2:]

    if question and question not in questions:
        questions.add(question)
        qa_dataset.append([question, answer])

qa_by_word_dataset = {}  # {'word': [[q, a], ...]}

for question, answer in qa_dataset:
    words = question.split(' ')
    for word in words:
        if word not in qa_by_word_dataset:
            qa_by_word_dataset[word] = []
        qa_by_word_dataset[word].append((question, answer))

qa_by_word_dataset_filtered = {word: qa_list
                               for word, qa_list in qa_by_word_dataset.items()
                               if len(qa_list) < 1000}


def generate_answer_by_text(text):
    text = filter_text(text)
    words = text.split(' ')
    qa = []
    for word in words:
        if word in qa_by_word_dataset_filtered:
            qa += qa_by_word_dataset_filtered[word]
    qa = list(set(qa))[:1000]

    results = []
    for question, answer in qa:
        dist = nltk.edit_distance(question, text)
        dist_percentage = dist / len(question)
        results.append([dist_percentage, question, answer])

    if results:
        dist_percentage, question, answer = min(results, key=lambda pair: pair[0])
        if dist_percentage < 0.3:
            return answer


# выбираем рандомную фразу заглушку из списка
def get_failure_phrase():
    phrases = BOT_CONFIG['failure_phrases']
    return random.choice(phrases)


stats = [0, 0, 0]


# Метод выбора ответа
def my_bot(question):
    # NLU
    intent = get_intent(question)

    # Получение ответа 3 спосабами:

    # Варивнт 1 (пришел intent) - ищем по файлу готовый ответ:
    if intent:

        answer = get_answer_by_intent(intent)
        if answer:
            stats[0] += 1
            print(stats, "файл")
            return answer

    # Генеруем подходящий по контексту ответ
    answer = generate_answer_by_text(question)
    if answer:
        stats[1] += 1
        print(stats, "ИИ")
        return answer

    # Используем заглушку
    stats[2] += 1
    answer = get_failure_phrase()
    print(stats, "Зашлушка")
    return answer


# APU с zabbix


def main():
    # TeleBot
    bot = telebot.TeleBot('1441728092:AAHUshkHijpEYYRPv88P4lULLQdIB_BxeIQ')

    # Обработчик события '/start'
    @bot.message_handler(commands=['start'])
    def send_welcome(message):

        # обычная клавиатура на меню /start
        main_menu = types.ReplyKeyboardMarkup(resize_keyboard=True)
        item1 = types.KeyboardButton("Настройка ТВ")
        item2 = types.KeyboardButton("Не работает ТВ")
        item3 = types.KeyboardButton("Отправить жалобу")
        main_menu.add(item1, item2, item3)

        bot.send_message(message.chat.id, "Добро пожаловать, {0.first_name}!\nЯ - <b>{1.first_name}</b>, "
                                          "бот созданный чтобы помогать.".format(message.from_user, bot.get_me()),
                         parse_mode='html', reply_markup=main_menu)

    # обработчик всех событий
    @bot.message_handler(func=lambda message: True)
    def send_message(message):

        # клавиатура на сообщение (InLine)
        if message.chat.type == 'private':
            if message.text == 'Настройка ТВ':
                tv_menu = types.InlineKeyboardMarkup(row_width=2)
                item1 = types.InlineKeyboardButton("Samsung standart", callback_data='Samsung standart')
                item2 = types.InlineKeyboardButton("Samsung smart", callback_data='Samsung smart')
                item3 = types.InlineKeyboardButton("LG", callback_data='LG')
                tv_menu.add(item1, item2, item3)
                bot.send_message(message.chat.id, "Укажите модель ТВ", reply_markup=tv_menu)
            elif message.text == "Не работает ТВ":
                bot.send_message(message.chat.id, "Оставьте свои контактные данный, Мы с Вами свяжемся")
            elif message.text == "Отправить жалобу":
                bot.send_message(message.chat.id,
                                 "Нам важно Ваше мнение, оставьте Вашу жалобу, Я передам ее кому следует :) ")
            else:
                bot.send_message(message.chat.id, my_bot(message.text))

    # Обработка нажатия на кнопку InLine клавиатуры
    @bot.callback_query_handler(func=lambda call: True)
    def callback_inline(call):
        try:
            if call.message:
                if call.data == 'Samsung standart':
                    bot.send_message(call.message.chat.id, settings.SamsungStandart)
                elif call.data == 'Samsung smart':
                    bot.send_message(call.message.chat.id, settings.SamsungSmart)
                elif call.data == 'LG':
                    bot.send_message(call.message.chat.id, settings.LG)

                # удаление inline клавиатуры
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text='Найдено следующяя инструкция:', reply_markup=None)

                # показ уведомления
                bot.answer_callback_query(callback_query_id=call.id, show_alert=False,
                                          text="Выполнено, милорд!!!")

        except Exception as e:
            print(repr(e))

    bot.polling()


if __name__ == '__main__':
    main()
