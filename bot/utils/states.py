from aiogram.fsm.state import StatesGroup, State


class LoadDataForm(StatesGroup):
    waiting_for_choice = State()  # Ожидание выбора способа ввода
    waiting_for_file = State()  # Ожидание файла
    waiting_for_title = State()  # Ожидание заголовка (ручной ввод)
    waiting_for_text = State()  # Ожидание текста (ручной ввод)
    waiting_for_confirmation = (
        State()
    )  # Ожидание подтверждения при случайной отправке файла


class AddTopicForm(StatesGroup):
    waiting_for_method = State()  # Ожидание выбора способа ввода (ручной/файл)
    waiting_for_title = State()  # Ожидание заголовка
    waiting_for_content = State()  # Ожидание содержимого (ручной ввод)
    waiting_for_file = State()  # Ожидание файла
    waiting_for_confirmation = State()  # Ожидание подтверждения
    waiting_for_title_edit = State()  # Ожидание редактирования заголовка
