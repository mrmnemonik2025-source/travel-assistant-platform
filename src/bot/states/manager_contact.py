from aiogram.fsm.state import State, StatesGroup


class ManagerContactStates(StatesGroup):
	waiting_for_manager_message = State()
