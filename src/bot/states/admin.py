from aiogram.fsm.state import State, StatesGroup


class AdminSearchStates(StatesGroup):
	waiting_for_query = State()


class AdminExcursionEditStates(StatesGroup):
	waiting_for_value = State()
	waiting_for_photo = State()
