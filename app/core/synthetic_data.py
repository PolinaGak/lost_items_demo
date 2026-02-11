import asyncio
import random
from datetime import datetime, timedelta
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import User, Station, FoundItem, LostItem, Match
from app.services.embedding import get_embedding

METRO_STATIONS = [
    {"name": "Сокольники", "line_id": 1},
    {"name": "Красные Ворота", "line_id": 1},
    {"name": "Чистые пруды", "line_id": 1},
    {"name": "Лубянка", "line_id": 1},
    {"name": "Охотный ряд", "line_id": 1},
    {"name": "Библиотека им. Ленина", "line_id": 1},
    {"name": "Кропоткинская", "line_id": 1},
    {"name": "Парк культуры", "line_id": 1},
    {"name": "Фрунзенская", "line_id": 1},
    {"name": "Спортивная", "line_id": 1},
    {"name": "Воробьёвы горы", "line_id": 1},
    {"name": "Университет", "line_id": 1},
    {"name": "Проспект Вернадского", "line_id": 1},
    {"name": "Юго-Западная", "line_id": 1},
    {"name": "Тропарёво", "line_id": 1},
    {"name": "Саларьево", "line_id": 1},

    {"name": "Автозаводская", "line_id": 2},
    {"name": "Павелецкая", "line_id": 2},
    {"name": "Новокузнецкая", "line_id": 2},
    {"name": "Театральная", "line_id": 2},
    {"name": "Тверская", "line_id": 2},
    {"name": "Маяковская", "line_id": 2},
    {"name": "Белорусская", "line_id": 2},
    {"name": "Динамо", "line_id": 2},
    {"name": "Аэропорт", "line_id": 2},
    {"name": "Сокол", "line_id": 2},
    {"name": "Войковская", "line_id": 2},
    {"name": "Водный стадион", "line_id": 2},
    {"name": "Речной вокзал", "line_id": 2},

    {"name": "Щёлковская", "line_id": 3},
    {"name": "Первомайская", "line_id": 3},
    {"name": "Измайловская", "line_id": 3},
    {"name": "Партизанская", "line_id": 3},
    {"name": "Семёновская", "line_id": 3},
    {"name": "Электрозаводская", "line_id": 3},
    {"name": "Бауманская", "line_id": 3},
    {"name": "Курская", "line_id": 3},
    {"name": "Площадь Революции", "line_id": 3},
    {"name": "Арбатская", "line_id": 3},
    {"name": "Смоленская", "line_id": 3},
    {"name": "Киевская", "line_id": 3},
    {"name": "Парк Победы", "line_id": 3},
    {"name": "Славянский бульвар", "line_id": 3},
    {"name": "Кунцевская", "line_id": 3},
    {"name": "Молодёжная", "line_id": 3},
    {"name": "Крылатское", "line_id": 3},
    {"name": "Строгино", "line_id": 3},
]


FOUND_ITEMS_DATA = [
    {"title": "Наушники Apple AirPods Pro",
     "description": "Беспроводные наушники в белом кейсе, на кейсе царапина, внутри левый наушник"},
    {"title": "Зарядное устройство 65W", "description": "Блок питания USB-C на 65 ватт, белый, от ноутбука Xiaomi"},
    {"title": "USB-флешка 32GB", "description": "Флешка Kingston синего цвета, 32 гигабайта, на корпусе царапины"},
    {"title": "Powerbank 10000 mAh", "description": "Внешний аккумулятор Xiaomi, белый, два порта USB"},
    {"title": "Смарт-часы", "description": "Apple Watch Series 6, чёрный ремешок, стекло треснуто"},

    {"title": "Чёрный зонт-трость",
     "description": "Чёрный автоматический зонт, ручка деревянная, в сложенном виде 90 см"},
    {"title": "Синяя вязаная шапка", "description": "Шапка синего цвета, с помпоном, размер 56-58"},
    {"title": "Кожаные перчатки", "description": "Перчатки чёрные, кожаные, размер M, подкладка шерстяная"},
    {"title": "Бейсболка 'Метро'", "description": "Чёрная бейсболка с вышивкой 'Московский метрополитен'"},
    {"title": "Кашне", "description": "Шарф серый, кашемировый, длина 180 см"},
    {"title": "Бежевый шоппер", "description": "Тканевая сумка бежевого цвета, с длинными ручками, внутри карман"},
    {"title": "Очки для зрения", "description": "Очки в чёрной оправе, диоптрии -2.5, в красном футляре"},
    {"title": "Солнцезащитные очки", "description": "Очки Ray-Ban Aviator, золотая оправа, серые стёкла"},

    {"title": "Паспорт РФ",
     "description": "Паспорт гражданина РФ, серия 4510 номер 123456, на имя Иванов Иван Иванович"},
    {"title": "Студенческий билет", "description": "Студенческий билет МГУ, синяя обложка, факультет ВМК"},
    {"title": "Водительское удостоверение", "description": "В/У категория B, на имя Петрова Алексея Сергеевича"},
    {"title": "Банковская карта", "description": "Карта Т-Банк, чёрная, платёжная система Мир"},

    {"title": "Ключи", "description": "Связка из трёх ключей, брелок в виде метро, силиконовый"},
    {"title": "Кошелёк", "description": "Кошелёк коричневый, кожаный, внутри 500 рублей и скидочные карты"},
    {"title": "Зонт детский", "description": "Детский зонт-автомат, розовый, с рисунком 'Единорог'"},
    {"title": "Игрушка", "description": "Мягкая игрушка заяц, белый, 30 см, с голубым бантом"},
    {"title": "Термос", "description": "Термос стальной, 500 мл, крышка-чашка, синий"},
    {"title": "Книга", "description": "Книга 'Мастер и Маргарита', издательство АСТ, в мягкой обложке"},
    {"title": "Планшет", "description": "iPad 9 поколения, серый космос, в чёрном чехле-книжке"},
    {"title": "Ручка", "description": "Паркер, серебристая, гравировка на колпачке"},
    {"title": "Ежедневник", "description": "Ежедневник в твёрдом переплёте, коричневый, 2026 год"},
]



LOST_ITEMS_DATA = [
    {"description": "Потерял белые наушники эйрподс, кейс белый, наушник левый не работает"},
    {"description": "Оставила в вагоне синюю вязаную шапку с пушистым помпоном"},
    {"description": "Забыл зарядку от макбука, белый куб, провод type-c"},
    {"description": "Выпал паспорт из сумки, Иванов Иван, серия 4510"},
    {"description": "Утерян кошелёк коричневый кожаный, внутри карты магнит"},
    {"description": "Потерял зонт чёрный автоматический, ручка деревянная"},
    {"description": "Оставила сумку тканевую бежевую в переходе"},
    {"description": "Забыл очки в чёрной оправе, в футляре красном"},
    {"description": "Потерял ключи, связка три штуки, брелок метро"},
    {"description": "Утеряна банковская карта Т-Банк чёрная"},
    {"description": "Оставил книгу Булгаков в мягкой обложке"},
    {"description": "Потерял повербанк белый сяоми, 10000"},
]


async def create_stations(session: AsyncSession):
    """Создание справочника станций."""
    print("Создаю станции метро...")

    for station_data in METRO_STATIONS:
        station = Station(
            name=station_data["name"],
            line_id=station_data["line_id"]
        )
        session.add(station)

    await session.commit()
    print(f"Создано {len(METRO_STATIONS)} станций")

    result = await session.execute(select(Station))
    stations = result.scalars().all()
    return stations


async def create_found_items(session: AsyncSession, stations):
    """Создание найденных вещей."""
    print("\nСоздаю найденные вещи...")

    today = datetime.now().date()
    station_ids = [s.id for s in stations]

    for i, item_data in enumerate(FOUND_ITEMS_DATA, 1):
        days_ago = random.randint(0, 30)
        found_date = today - timedelta(days=days_ago)

        station_id = random.choice(station_ids)

        embedding = await get_embedding(item_data["description"])

        item = FoundItem(
            description=item_data["description"],
            embedding=embedding,
            found_date=found_date,
            station_id=station_id,
            source="metro"
        )
        session.add(item)

    await session.commit()
    print(f"Создано {len(FOUND_ITEMS_DATA)} найденных вещей")

    result = await session.execute(select(FoundItem))
    return result.scalars().all()


async def create_test_user(session: AsyncSession):
    print("\nСоздаю тестового пользователя...")

    user = User(
        token="test_user_token_123456"
    )
    session.add(user)
    await session.commit()

    print(f"Создан пользователь с ID: {user.id}, токен: {user.token}")
    return user


async def create_lost_items(session: AsyncSession, user, stations):
    """Создание потерянных вещей (заявок)."""
    print("\nСоздаю заявки на потерянные вещи...")

    today = datetime.now().date()
    station_ids = [s.id for s in stations]

    statuses = ["pending", "matched", "notified", "closed"]
    weights = [0.4, 0.3, 0.2, 0.1]

    lost_items = []

    for i, item_data in enumerate(LOST_ITEMS_DATA, 1):
        days_ago = random.randint(0, 14)
        loss_date = today - timedelta(days=days_ago)

        station_id = random.choice(station_ids)

        status = random.choices(statuses, weights=weights)[0]

        embedding = await get_embedding(item_data["description"])

        item = LostItem(
            user_id=user.id,
            description=item_data["description"],
            embedding=embedding,
            loss_date=loss_date,
            station_id=station_id,
            status=status,
            is_found=(status != "pending"),
            is_taken=(status == "closed")
        )
        session.add(item)
        lost_items.append(item)

    await session.commit()
    print(f"Создано {len(LOST_ITEMS_DATA)} заявок")

    return lost_items


async def generate_synthetic_data():
    print("\n" + "=" * 50)
    print("НАЧАЛО ЗАГРУЗКИ СИНТЕТИЧЕСКИХ ДАННЫХ")
    print("=" * 50 + "\n")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Station).limit(1))
        if result.scalar_one_or_none():
            print("База данных уже содержит данные. Пропускаем...")
            return

        stations = await create_stations(session)

        found_items = await create_found_items(session, stations)

        user = await create_test_user(session)

        lost_items = await create_lost_items(session, user, stations)

    print("\n" + "=" * 50)
    print("ЗАГРУЗКА СИНТЕТИЧЕСКИХ ДАННЫХ ЗАВЕРШЕНА")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    """Для ручного запуска: python -m app.core.synthetic_data"""
    asyncio.run(generate_synthetic_data())