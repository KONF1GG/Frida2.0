from aiogram.fsm.state import StatesGroup, State

class LoadDataForm(StatesGroup):
    waiting_for_choice = State()    # Ожидание выбора способа ввода
    waiting_for_file = State()      # Ожидание файла
    waiting_for_title = State()     # Ожидание заголовка (ручной ввод)
    waiting_for_text = State()      # Ожидание текста (ручной ввод)
    waiting_for_confirmation = State()  # Ожидание подтверждения при случайной отправке файла