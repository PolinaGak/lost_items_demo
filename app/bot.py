import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from sqlalchemy import select

from app.core.config import config
from app.database import AsyncSessionLocal, init_db, close_db
from app.models import User, Line, Station, LostItem, Match
from app.services.embedding import get_embedding
from app.services.matcher import find_similar_items
from app.services.station_service import StationService, build_search_query

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


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
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Line).order_by(Line.id))
        lines = result.scalars().all()
    buttons = []
    for line in lines:
        if line.id in [1, 2, 3, 5, 6, 7, 9, 11]:
            buttons.append([
                InlineKeyboardButton(
                    text=f"{line.color} {line.name}",
                    callback_data=f"line_{line.id}"
                )
            ])
    buttons.append([InlineKeyboardButton(text="Поиск по названию", callback_data="station_search")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def get_stations_keyboard(line_id: int, page: int = 0) -> InlineKeyboardMarkup:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Station)
            .where(Station.line_id == line_id)
            .order_by(Station.order_number)
        )
        stations = result.scalars().all()
    per_page = 8
    total_pages = (len(stations) + per_page - 1) // per_page
    start = page * per_page
    end = start + per_page
    page_stations = stations[start:end]
    buttons = []
    for station in page_stations:
        buttons.append([
            InlineKeyboardButton(
                text=station.name,
                callback_data=f"station_{station.id}"
            )
        ])
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
    await init_db()
    logger.info("Bot started")


@dp.shutdown()
async def on_shutdown():
    logger.info("Stopping bot...")
    await close_db()
    await bot.session.close()
    logger.info("Bot stopped")


def get_start_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Сообщить о потере", callback_data="start_lost")],
        [InlineKeyboardButton(text="Мои заявки", callback_data="start_my")],
        [InlineKeyboardButton(text="Помощь", callback_data="start_help")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                telegram_id=telegram_id,
                token=f"tg_{telegram_id}_{datetime.now().timestamp()}"
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            logger.info(f"Created new user: id={user.id}, telegram_id={user.telegram_id}")
        await state.update_data(user_id=user.id)
    await message.answer(
        "Здравствуйте! Этот бот помогает найти потерянные вещи в метро.\n"
        "Вы можете сообщить о потере, посмотреть статус своих заявок и получить информацию.",
        reply_markup=get_start_keyboard()
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
    await state.set_state(LostItemForm.description)
    await message.answer(
        "Опишите потерянную вещь как можно подробнее.\n"
        "Например: чёрный зонт-трость с деревянной ручкой",
        reply_markup=ReplyKeyboardRemove()
    )


@dp.message(LostItemForm.description)
async def process_description(message: Message, state: FSMContext):
    if len(message.text) < 10:
        await message.answer("Пожалуйста, опишите вещь подробнее (минимум 10 символов)")
        return
    await state.update_data(description=message.text)
    await state.set_state(LostItemForm.date)
    await message.answer(
        "Когда вы потеряли вещь?",
        reply_markup=get_date_keyboard()
    )


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
        except ValueError:
            await callback.answer("Ошибка формата даты", show_alert=True)
    await callback.answer()


@dp.message(LostItemForm.date)
async def process_date_manual(message: Message, state: FSMContext):
    try:
        loss_date = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
        await validate_and_set_date(message, state, loss_date)
    except ValueError:
        await message.answer("Неверный формат даты. Используйте ДД.ММ.ГГГГ")


async def validate_and_set_date(message: Message, state: FSMContext, loss_date: datetime.date):
    today = datetime.now().date()
    if loss_date > today:
        await message.answer("Дата потери не может быть в будущем")
        return
    if (today - loss_date).days > 30:
        await message.answer("Вы потеряли вещь больше месяца назад. Мы попробуем найти, но шанс невелик.")
    await state.update_data(loss_date=loss_date)
    await state.set_state(LostItemForm.line)
    keyboard = await get_lines_keyboard()
    await message.answer(
        "Выберите линию метро, на которой потеряли вещь:",
        reply_markup=keyboard
    )


@dp.callback_query(LostItemForm.line)
async def process_line_selection(callback: CallbackQuery, state: FSMContext):
    data = callback.data
    if data == "back_to_lines":
        keyboard = await get_lines_keyboard()
        await callback.message.edit_text(
            "Выберите линию метро:",
            reply_markup=keyboard
        )
        await callback.answer()
        return
    if data == "station_search":
        await callback.message.edit_text(
            "Введите название станции (хотя бы 3 символа):"
        )
        await state.set_state(LostItemForm.station)
        await callback.answer()
        return
    if data.startswith("line_"):
        parts = data.split("_")
        line_id = int(parts[1])
        page = int(parts[3]) if len(parts) > 3 and parts[2] == "page" else 0
        keyboard = await get_stations_keyboard(line_id, page)
        await callback.message.edit_text(
            "Выберите станцию:",
            reply_markup=keyboard
        )
        await callback.answer()
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
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Station)
            .where(Station.name.ilike(f"%{query}%"))
            .order_by(Station.name)
            .limit(10)
        )
        stations = result.scalars().all()
    if not stations:
        await message.answer("Станции с таким названием не найдены. Попробуйте ещё раз или /cancel")
        return
    buttons = []
    for station in stations:
        async with AsyncSessionLocal() as session:
            line = await session.get(Line, station.line_id)
            line_name = line.name if line else ""
        buttons.append([
            InlineKeyboardButton(
                text=f"{station.name} ({line_name})",
                callback_data=f"station_{station.id}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="К линиям", callback_data="back_to_lines")])
    await message.answer(
        "Найденные станции:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


async def finish_station_selection(message: Message, state: FSMContext, station_id: int):
    async with AsyncSessionLocal() as session:
        station = await session.get(Station, station_id)
        line = await session.get(Line, station.line_id)
        station_name = f"{station.name} ({line.color} линия)" if line else station.name
    await state.update_data(station_id=station_id, station_name=station_name)
    data = await state.get_data()
    description = data.get('description')
    loss_date = data.get('loss_date')
    await message.answer(
        f"Проверьте данные:\n\n"
        f"Описание: {description}\n"
        f"Дата потери: {loss_date.strftime('%d.%m.%Y')}\n"
        f"Станция: {station_name}\n\n"
        f"Всё верно?",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Да"), KeyboardButton(text="Нет, заново")]
            ],
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
        await message.answer(
            "Заявка отменена.",
            reply_markup=ReplyKeyboardRemove()
        )
        await message.answer(
            "Что хотите сделать дальше?",
            reply_markup=get_after_claim_keyboard()
        )
        return
    if message.text.lower() not in ["да", "да"]:
        await message.answer("Пожалуйста, выберите Да или Нет")
        return
    data = await state.get_data()
    user_id = data.get('user_id')
    async with AsyncSessionLocal() as session:
        embedding = await get_embedding(data['description'])
        lost_item = LostItem(
            user_id=user_id,
            description=data['description'],
            embedding=embedding,
            loss_date=data['loss_date'],
            station_id=data['station_id'],
            status='pending'
        )
        session.add(lost_item)
        await session.commit()
        similar_items = await find_similar_items(
            session=session,
            query_embedding=embedding,
            station_id=data['station_id'],
            loss_date=data['loss_date'],
            limit=5,
            similarity_threshold=0.65,
            days_delta=3
        )
        if similar_items:
            lost_item.status = 'matched'
            for found_item, similarity in similar_items[:3]:
                match = Match(
                    lost_item_id=lost_item.id,
                    found_item_id=found_item.id,
                    similarity=similarity,
                    status='pending'
                )
                session.add(match)
            await session.commit()
            response = "Мы нашли похожие вещи!\n\n"
            for i, (found_item, similarity) in enumerate(similar_items[:3], 1):
                station = await session.get(Station, found_item.station_id)
                line = await session.get(Line, station.line_id) if station else None
                station_str = f"{station.name} ({line.color})" if station and line else "неизвестно"
                response += (
                    f"{i}. {found_item.description}\n"
                    f"   Найдена: {station_str}\n"
                    f"   Дата находки: {found_item.found_date.strftime('%d.%m.%Y')}\n"
                    f"   Совпадение: {similarity:.1%}\n\n"
                )
            response += "Свяжитесь с сотрудниками метро на указанной станции."
        else:
            response = (
                "Пока не нашли похожих вещей.\n\n"
                "Мы сохранили вашу заявку и будем проверять новые находки.\n"
                "Вам придёт уведомление, когда появится подходящая вещь."
            )
        await message.answer(response, reply_markup=ReplyKeyboardRemove())
        await message.answer(
            "Что хотите сделать дальше?",
            reply_markup=get_after_claim_keyboard()
        )
    await state.clear()


@dp.message(Command("my"))
async def cmd_my(message: Message):
    telegram_id = message.from_user.id
    async with AsyncSessionLocal() as session:
        user = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user.scalar_one_or_none()
        if not user:
            await message.answer("У вас пока нет заявок")
            return
        lost_items = await session.execute(
            select(LostItem)
            .where(LostItem.user_id == user.id)
            .order_by(LostItem.created_at.desc())
            .limit(5)
        )
        lost_items = lost_items.scalars().all()
        if not lost_items:
            await message.answer("У вас пока нет заявок")
            return
        response = "Ваши последние заявки:\n\n"
        status_display = {
            'pending': 'Ожидает проверки',
            'matched': 'Найдены совпадения',
            'notified': 'Уведомление отправлено',
            'closed': 'Заявка закрыта'
        }
        for item in lost_items:
            station = await session.get(Station, item.station_id)
            station_str = station.name if station else "неизвестно"
            status_text = status_display.get(item.status, item.status)
            response += (
                f"• {item.description[:50]}...\n"
                f"  Дата потери: {item.loss_date.strftime('%d.%m.%Y')}\n"
                f"  Станция: {station_str}\n"
                f"  Статус: {status_text}\n\n"
            )
        await message.answer(response)
        await message.answer(
            "Что хотите сделать дальше?",
            reply_markup=get_after_claim_keyboard()
        )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Доступные команды:\n\n"
        "/start - начать работу\n"
        "/lost - сообщить о потере\n"
        "/my - мои заявки\n"
        "/help - помощь\n\n"
        "Если вы нашли вещь, сдайте её сотруднику метро."
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
        "Используйте /help для списка команд."
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())