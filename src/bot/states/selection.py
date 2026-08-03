from aiogram.fsm.state import State, StatesGroup


class SelectionStates(StatesGroup):
	waiting_for_audience = State()
	waiting_for_interest = State()
	waiting_for_format = State()
