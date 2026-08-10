from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExcursionData:
	id: str
	title: str
	short_title: str
	time: str
	price: str
	description: str
	included: tuple[str, ...]
	image_path: str | None
	booking_callback_data: str
	is_active: bool = True
	not_included: tuple[str, ...] | None = None
	what_to_bring: tuple[str, ...] | None = None
	restrictions: tuple[str, ...] | None = None
	departure_point: str | None = None
	audience: tuple[str, ...] = ()
	interests: tuple[str, ...] = ()
	formats: tuple[str, ...] = ()


NIGHT_CRUISE = ExcursionData(
	id="emperor_cruise",
	title="🌙 Ночной круиз по заливу Нячанга",
	short_title="🌙 Ночной круиз",
	time="16:30–20:00",
	price="2 450 000 ₫ с человека",
	description=(
		"Вечерний круиз на Emperor Cruises с закатом, ужином, живой музыкой и напитками."
	),
	included=(
		"трансфер из отеля и обратно;",
		"коктейли и лёгкие закуски;",
		"ужин из морепродуктов;",
		"напитки без ограничения;",
		"живая музыка;",
		"сопровождение менеджера.",
	),
	image_path="src/bot/assets/images/night_cruise.png",
	booking_callback_data="booking:emperor_cruise",
	not_included=None,
	what_to_bring=None,
	restrictions=None,
	departure_point=None,
	audience=("Пара", "Компания"),
	interests=("Вечерняя программа",),
	formats=("Спокойный отдых",),
)

ASIA_MIX_ISLANDS = ExcursionData(
	id="asia_mix_islands",
	title="🏝️ Asia Mix Islands",
	short_title="🏝️ Asia Mix Islands",
	time="Расписание уточняется при бронировании",
	price="1 564 000 ₫ с человека",
	description="Авторская экскурсия Asia Mix по трём островам Нячанга со снорклингом.",
	included=(
		"маршрут по трём островам;",
		"снорклинг;",
		"сопровождение по программе.",
	),
	image_path="src/bot/assets/images/asia_mix_islands.png",
	booking_callback_data="booking:asia_mix_islands",
	interests=("Острова и пляжи",),
	formats=("Спокойный отдых",),
)

DALAT_VIP = ExcursionData(
	id="dalat_vip",
	title="🏔️ Далат VIP",
	short_title="🏔️ Далат VIP",
	time="Однодневная экскурсия",
	price="1 722 000 ₫ с человека",
	description="Комфортная экскурсия в Далат по природным и культурным достопримечательностям горного курорта.",
	included=(
		"горный перевал и живописное озеро;",
		"канатная дорога к водопаду;",
		"пагода Линь Фуок и железнодорожный вокзал;",
		"стеклянный мост и Crazy House;",
		"обед и дегустация чая, артишока и кофе.",
	),
	image_path="src/bot/assets/images/dalat_vip.png",
	booking_callback_data="booking:dalat_vip",
	interests=("Природа и горы",),
	formats=("VIP / комфорт",),
)

NORTHERN_ISLANDS = ExcursionData(
	id="northern_islands",
	title="🚤 Северные острова",
	short_title="🚤 Северные острова",
	time="Однодневная экскурсия",
	price="954 000 ₫ с человека",
	description="Морская прогулка по северным островам с посещением парков Орхидей и Обезьян.",
	included=(
		"остров Орхидей;",
		"остров Обезьян;",
		"обед в формате шведского стола.",
	),
	image_path="src/bot/assets/images/northern_islands.png",
	booking_callback_data="booking:northern_islands",
	interests=("Острова и пляжи",),
	formats=("Спокойный отдых",),
)

VINWONDERS = ExcursionData(
	id="vinwonders",
	title="🎡 VinWonders",
	short_title="🎡 VinWonders",
	time="В течение дня",
	price="Взрослый — 1 050 000 ₫; ребёнок 100–139 см и гость 60+ — 800 000 ₫",
	description="Стандартный входной билет в парк развлечений VinWonders Nha Trang.",
	included=(
		"стандартный входной билет в VinWonders.",
	),
	image_path="src/bot/assets/images/vinwonders.png",
	booking_callback_data="booking:vinwonders",
	interests=("Развлечения",),
	formats=("Яркие впечатления",),
)

DIVING = ExcursionData(
	id="diving",
	title="🤿 Дайвинг и снорклинг",
	short_title="🤿 Дайвинг и снорклинг",
	time="Расписание уточняется при бронировании",
	price="Дайвинг — 2 385 000 ₫; снорклинг — 1 193 000 ₫",
	description="Морская программа для знакомства с подводным миром Нячанга: дайвинг или снорклинг на выбор.",
	included=(
		"два погружения для программы дайвинга;",
		"снорклинг для выбранной программы;",
		"обед.",
	),
	image_path="src/bot/assets/images/diving_snorkeling.png",
	booking_callback_data="booking:diving",
	interests=("Дайвинг и снорклинг",),
	formats=("Активный отдых",),
)

ALL_EXCURSIONS: tuple[ExcursionData, ...] = (
	NIGHT_CRUISE,
	ASIA_MIX_ISLANDS,
	DALAT_VIP,
	NORTHERN_ISLANDS,
	VINWONDERS,
	DIVING,
)

EXCURSIONS_BY_ID: dict[str, ExcursionData] = {excursion.id: excursion for excursion in ALL_EXCURSIONS}
