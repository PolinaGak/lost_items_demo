import asyncio
import logging
from datetime import datetime, timedelta, date
import httpx
from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from app.core.config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

API_BASE_URL = config.API_BASE_URL.rstrip("/")

async def api_post(endpoint: str, json_data: dict, token: str = None):
    headers = {"Authorization": token} if token else {}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{API_BASE_URL}{endpoint}", json=json_data, headers=headers, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"API post error: {str(e)}")
            raise ValueError(str(e))

async def api_get(endpoint: str, params: dict = None, token: str = None):
    headers = {"Authorization": token} if token else {}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{API_BASE_URL}{endpoint}", params=params, headers=headers, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"API get error: {str(e)}")
            raise ValueError(str(e))

class LostItemForm(StatesGroup):
    description = State()
    date = State()
    line = State()
    station = State()
    confirm = State()

def get_date_keyboard() -> InlineKeyboardMarkup:
    today = datetime.now().date()
    buttons = [
        [InlineKeyboardButton(text="Сегодня", callback_data=f"date_{today.strftime('%d%m%Y')}")],
        [InlineKeyboardButton(text="Вчера", callback_data=f"date_{(today - timedelta(days=1)).strftime('%d%m%Y')}")],
        [InlineKeyboardButton(text="Позавчера", callback_data=f"date_{(today - timedelta(days=2)).strftime('%d%m%Y')}")],
        [InlineKeyboardButton(text="На этой неделе", callback_data="date_thisweek")],
        [InlineKeyboardButton(text="Ввести вручную", callback_data="date_manual")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_thisweek_keyboard() -> InlineKeyboardMarkup:
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    buttons = []
    for i in range(7):
        day = monday + timedelta(days=i)
        if day <= today:
            buttons.append([
                InlineKeyboardButton(
                    text=day.strftime("%d.%m (%a)"),
                    callback_data=f"date_{day.strftime('%d%m%Y')}"
                )
            ])
    buttons.append([InlineKeyboardButton(text="Назад", callback_data="date_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def get_lines_keyboard() -> InlineKeyboardMarkup:
    try:
        lines = await api_get("/lines")
    except ValueError:
        return InlineKeyboardMarkup(inline_keyboard=[])
    buttons = [[InlineKeyboardButton(
                    text=f"{line['color']} {line['name']}",
                    callback_data=f"line_{line['id']}"
                )] for line in lines]
    buttons.append([InlineKeyboardButton(text="Поиск по названию", callback_data="station_search")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def get_stations_keyboard(line_id: int, page: int = 0) -> InlineKeyboardMarkup:
    try:
        stations_resp = await api_get("/stations", {"line_id": line_id, "page": page, "per_page": 8})
    except ValueError:
        return InlineKeyboardMarkup(inline_keyboard=[])
    stations = stations_resp.get("stations", [])
    total_pages = stations_resp.get("total_pages", 1)
    buttons = [[InlineKeyboardButton(
                text=station["name"],
                callback_data=f"station_{station['id']}"
            )] for station in stations]
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="<", callback_data=f"line_{line_id}_page_{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="ignore"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text=">", callback_data=f"line_{line_id}_page_{page + 1}"))
    if nav_buttons:
        buttons.append(nav_buttons)
    buttons.append([InlineKeyboardButton(text="К линиям", callback_data="back_to_lines")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@dp.startup()
async def on_startup():
    logger.info("Starting bot...")

@dp.shutdown()
async def on_shutdown():
    await bot.session.close()
    logger.info("Bot stopped")

def get_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="/lost - Сообщить о потере")],
        [KeyboardButton(text="/my - Мои заявки")],
        [KeyboardButton(text="/help - Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=False)

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    user_id = None
    token = None
    try:
        user_resp = await api_get(f"/users/by-telegram/{telegram_id}")
        user_id = user_resp["id"]
        token = user_resp["token"]
    except ValueError as e:
        if "404" in str(e):
            try:
                user_resp = await api_post("/users", {"telegram_id": telegram_id})
                user_id = user_resp["id"]
                token = user_resp["token"]
            except ValueError as e:
                logger.error(str(e))
                await message.answer("Ошибка создания пользователя. Попробуйте позже.", reply_markup=get_main_keyboard())
                return
        else:
            logger.error(str(e))
            await message.answer("Ошибка связи с сервером. Попробуйте позже.", reply_markup=get_main_keyboard())
            return
    await state.update_data(user_id=user_id, token=token)
    await message.answer(
        "Здравствуйте! Этот бот помогает найти потерянные вещи в метро.\n"
        "Вы можете сообщить о потере, посмотреть статус своих заявок и получить информацию.",
        reply_markup=get_main_keyboard()
    )

@dp.callback_query(lambda c: c.data == "start_lost")
async def start_lost(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await cmd_lost(callback.message, state)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "start_my")
async def start_my(callback: CallbackQuery):
    await callback.message.delete()
    await cmd_my(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "start_help")
async def start_help(callback: CallbackQuery):
    await callback.message.delete()
    await cmd_help(callback.message)
    await callback.answer()

@dp.message(Command("lost"))
async def cmd_lost(message: Message, state: FSMContext):
    data = await state.get_data()
    if not data.get('token'):
        telegram_id = message.from_user.id
        try:
            user_resp = await api_get(f"/users/by-telegram/{telegram_id}")
            await state.update_data(user_id=user_resp["id"], token=user_resp["token"])
        except ValueError as e:
            if "404" in str(e):
                try:
                    user_resp = await api_post("/users", {"telegram_id": telegram_id})
                    await state.update_data(user_id=user_resp["id"], token=user_resp["token"])
                except ValueError as e:
                    logger.error(str(e))
                    await message.answer("Ошибка создания пользователя. Попробуйте позже.", reply_markup=get_main_keyboard())
                    return
            else:
                logger.error(str(e))
                await message.answer("Ошибка связи с сервером. Попробуйте позже.", reply_markup=get_main_keyboard())
                return
    await state.set_state(LostItemForm.description)
    await message.answer(
        "Опишите потерянную вещь как можно подробнее.\n"
        "Например: чёрный зонт-трость с деревянной ручкой\n"
        "/cancel - отменить",
        reply_markup=get_main_keyboard()
    )

@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=get_main_keyboard())

@dp.message(LostItemForm.description)
async def process_description(message: Message, state: FSMContext):
    if len(message.text) < 10:
        await message.answer("Пожалуйста, опишите вещь подробнее (минимум 10 символов)")
        return
    await state.update_data(description=message.text)
    await state.set_state(LostItemForm.date)
    await message.answer("Когда вы потеряли вещь?", reply_markup=get_date_keyboard())

@dp.callback_query(LostItemForm.date)
async def process_date_callback(callback: CallbackQuery, state: FSMContext):
    data = callback.data
    if data == "date_manual":
        await callback.message.edit_text(
            "Введите дату вручную в формате ДД.ММ.ГГГГ\n"
            "Например: 15.01.2026"
        )
        await callback.answer()
        return
    if data == "date_thisweek":
        await callback.message.edit_text(
            "Выберите день:",
            reply_markup=get_thisweek_keyboard()
        )
        await callback.answer()
        return
    if data == "date_back":
        await callback.message.edit_text(
            "Когда вы потеряли вещь?",
            reply_markup=get_date_keyboard()
        )
        await callback.answer()
        return
    if data.startswith("date_"):
        date_str = data.replace("date_", "")
        try:
            loss_date = datetime.strptime(date_str, "%d%m%Y").date()
            await validate_and_set_date(callback.message, state, loss_date)
            await callback.message.delete()
        except ValueError as e:
            logger.error(f"Date parse error: {str(e)}")
            await callback.answer("Ошибка формата даты", show_alert=True)
        await callback.answer()

@dp.message(LostItemForm.date)
async def process_date_manual(message: Message, state: FSMContext):
    input_text = message.text.strip()
    try:
        loss_date = datetime.strptime(input_text, "%d.%m.%Y").date()
        await validate_and_set_date(message, state, loss_date)
    except ValueError:
        await message.answer("Неверный формат даты. Используйте ДД.ММ.ГГГГ, например 15.01.2026. Попробуйте заново.")

async def validate_and_set_date(message: Message, state: FSMContext, loss_date: date):
    today = datetime.now().date()
    if loss_date > today:
        await message.answer("Дата потери не может быть в будущем. Попробуйте ввести дату заново.")
        return
    delta_days = (today - loss_date).days
    if delta_days > 30:
        await message.answer(f"Вы потеряли вещь {delta_days} дней назад. Шанс найти низкий, но мы попробуем.")
    await state.update_data(loss_date=loss_date)
    await state.set_state(LostItemForm.line)
    keyboard = await get_lines_keyboard()
    if not keyboard.inline_keyboard:
        await message.answer("Ошибка загрузки линий метро. Попробуйте позже.")
        await state.clear()
        return
    await message.answer("Выберите линию метро, на которой потеряли вещь:", reply_markup=keyboard)

@dp.callback_query(LostItemForm.line)
async def process_line_selection(callback: CallbackQuery, state: FSMContext):
    data = callback.data
    if data == "back_to_lines":
        keyboard = await get_lines_keyboard()
        await callback.message.edit_text("Выберите линию метро:", reply_markup=keyboard)
        await callback.answer()
        return
    if data == "station_search":
        await callback.message.edit_text("Введите название станции (хотя бы 3 символа):")
        await state.set_state(LostItemForm.station)
        await callback.answer()
        return
    if data.startswith("line_"):
        parts = data.split("_")
        line_id = int(parts[1])
        page = int(parts[3]) if len(parts) > 3 and parts[2] == "page" else 0
        keyboard = await get_stations_keyboard(line_id, page)
        await callback.message.edit_text("Выберите станцию:", reply_markup=keyboard)
        await callback.answer()
        return
    if data.startswith("station_"):
        station_id = int(data.split("_")[1])
        await finish_station_selection(callback.message, state, station_id)
        await callback.message.delete()
        await callback.answer()

@dp.message(LostItemForm.station)
async def process_station_search(message: Message, state: FSMContext):
    query = message.text.strip()
    if len(query) < 3:
        await message.answer("Введите минимум 3 символа")
        return
    try:
        stations = await api_get("/stations/search", {"query": query, "limit": 10})
    except ValueError:
        await message.answer("Ошибка поиска станций. Попробуйте позже.")
        return
    if not stations:
        await message.answer("Станции с таким названием не найдены. Попробуйте ещё раз или /cancel")
        return
    buttons = [[InlineKeyboardButton(
                text=f"{station['name']} ({station.get('line_name', '')})",
                callback_data=f"station_{station['id']}"
            )] for station in stations]
    buttons.append([InlineKeyboardButton(text="К линиям", callback_data="back_to_lines")])
    await message.answer(
        "Найденные станции:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

async def finish_station_selection(message: Message, state: FSMContext, station_id: int):
    try:
        station = await api_get(f"/stations/{station_id}")
    except ValueError:
        await message.answer("Ошибка получения информации о станции. Попробуйте позже.")
        return
    await state.update_data(station_id=station_id, station_name=station["name"])
    data = await state.get_data()
    description = data.get('description')
    loss_date = data.get('loss_date')
    await message.answer(
        f"Проверьте данные:\n\n"
        f"Описание: {description}\n"
        f"Дата потери: {loss_date.strftime('%d.%m.%Y') if loss_date else '—'}\n"
        f"Станция: {station['name']}\n\n"
        f"Всё верно?",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Да"), KeyboardButton(text="Нет, заново")]],
            resize_keyboard=True
        )
    )
    await state.set_state(LostItemForm.confirm)

def get_after_claim_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Новая заявка", callback_data="new_claim")],
        [InlineKeyboardButton(text="Мои заявки", callback_data="my_claims")],
        [InlineKeyboardButton(text="Помощь", callback_data="help")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@dp.message(LostItemForm.confirm)
async def process_confirm(message: Message, state: FSMContext):
    if message.text.lower() in ["нет, заново", "нет"]:
        await state.clear()
        await message.answer("Заявка отменена.", reply_markup=ReplyKeyboardRemove())
        await message.answer("Что хотите сделать дальше?", reply_markup=get_main_keyboard())
        return
    if message.text.lower() != "да":
        await message.answer("Пожалуйста, выберите Да или Нет")
        return
    data = await state.get_data()
    token = data.get('token')
    if not token:
        telegram_id = message.from_user.id
        try:
            user_resp = await api_get(f"/users/by-telegram/{telegram_id}")
            token = user_resp["token"]
            await state.update_data(token=token, user_id=user_resp["id"])
        except ValueError as e:
            if "404" in str(e):
                try:
                    user_resp = await api_post("/users", {"telegram_id": telegram_id})
                    token = user_resp["token"]
                    await state.update_data(user_id=user_resp["id"], token=token)
                except ValueError as e:
                    logger.error(str(e))
                    await message.answer("Ошибка создания пользователя. Попробуйте позже.")
                    await state.clear()
                    return
            else:
                logger.error(str(e))
                await message.answer("Ошибка связи с сервером. Попробуйте позже.")
                await state.clear()
                return
    logger.info(f"DEBUG: token перед отправкой = {token}")
    payload = {
        "user_id": data.get('user_id'),
        "description": data['description'],
        "loss_date": data['loss_date'].isoformat(),
        "station_id": data['station_id']
    }
    try:
        result = await api_post("/lost-items", payload, token=token)
        await message.answer(result['message'], reply_markup=ReplyKeyboardRemove())
    except ValueError as e:
        logger.error(str(e))
        await message.answer("Ошибка обработки заявки. Попробуйте позже.")
    await message.answer("Что хотите сделать дальше?", reply_markup=get_main_keyboard())
    await state.clear()

@dp.message(Command("my"))
async def cmd_my(message: Message):
    telegram_id = message.from_user.id
    try:
        user_resp = await api_get(f"/users/by-telegram/{telegram_id}")
        user_id = user_resp["id"]
        token = user_resp["token"]
    except ValueError as e:
        if "404" in str(e):
            try:
                user_resp = await api_post("/users", {"telegram_id": telegram_id})
                user_id = user_resp["id"]
                token = user_resp["token"]
            except ValueError as e:
                logger.error(str(e))
                await message.answer("Ошибка создания пользователя. Попробуйте позже.", reply_markup=get_main_keyboard())
                return
        else:
            logger.error(str(e))
            await message.answer("Ошибка получения пользователя. Попробуйте позже.", reply_markup=get_main_keyboard())
            return
    try:
        items = await api_get(f"/lost-items/{user_id}", token=token)
    except ValueError as e:
        logger.error(str(e))
        await message.answer("Ошибка получения заявок. Попробуйте позже.", reply_markup=get_main_keyboard())
        return
    if not items:
        await message.answer("У вас пока нет заявок", reply_markup=get_main_keyboard())
        return
    response = "Ваши последние заявки:\n\n"
    status_display = {
        'pending': 'Ожидает проверки',
        'matched': 'Найдены совпадения',
        'notified': 'Уведомление отправлено',
        'closed': 'Заявка закрыта'
    }
    for item in items[:5]:
        try:
            loss_date = datetime.fromisoformat(item['loss_date']).strftime('%d.%m.%Y')
        except:
            loss_date = item['loss_date']
        status_text = status_display.get(item['status'], item['status'])
        response += (
            f"• {item['description'][:50]}...\n"
            f" Дата потери: {loss_date}\n"
            f" Станция: {item.get('station_name', 'неизвестно')}\n"
            f" Статус: {status_text}\n\n"
        )
    await message.answer(response, reply_markup=get_main_keyboard())
    await message.answer("Что хотите сделать дальше?", reply_markup=get_main_keyboard())

@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Доступные команды:\n\n"
        "/start - начать работу\n"
        "/lost - сообщить о потере\n"
        "/my - мои заявки\n"
        "/help - помощь\n"
        "/cancel - отменить текущее действие\n\n"
        "Если вы нашли вещь, сдайте её сотруднику метро.",
        reply_markup=get_main_keyboard()
    )

@dp.callback_query(lambda c: c.data == "new_claim")
async def callback_new_claim(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await cmd_lost(callback.message, state)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "my_claims")
async def callback_my_claims(callback: CallbackQuery):
    await callback.message.delete()
    await cmd_my(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "help")
async def callback_help(callback: CallbackQuery):
    await callback.message.delete()
    await cmd_help(callback.message)
    await callback.answer()

@dp.message()
async def handle_unknown(message: Message):
    await message.answer(
        "Я не понимаю эту команду.\n"
        "Используйте /help для списка команд.",
        reply_markup=get_main_keyboard()
    )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())