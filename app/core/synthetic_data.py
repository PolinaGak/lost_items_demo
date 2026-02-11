import asyncio
import random
from datetime import datetime, timedelta
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import (
    User, Line, Station, TransferPoint,
    FoundItem, LostItem, Match
)
from app.services.embedding import get_embedding
from app.services.matcher import find_similar_items

# ============================================================================
# ДАННЫЕ ЛИНИЙ
# ============================================================================

LINES_DATA = [
    {"id": 1, "name": "Сокольническая", "color": "Красный", "number": 1},
    {"id": 2, "name": "Замоскворецкая", "color": "Зелёный", "number": 2},
    {"id": 3, "name": "Арбатско-Покровская", "color": "Синий", "number": 3},
    {"id": 4, "name": "Филевская", "color": "Голубой", "number": 4},
    {"id": 5, "name": "Кольцевая", "color": "Коричневый", "number": 5},
    {"id": 6, "name": "Калужско-Рижская", "color": "Оранжевый", "number": 6},
    {"id": 7, "name": "Таганско-Краснопресненская", "color": "Фиолетовый", "number": 7},
    {"id": 8, "name": "Калининская", "color": "Жёлтый", "number": 8},
    {"id": 9, "name": "Серпуховско-Тимирязевская", "color": "Серый", "number": 9},
    {"id": 10, "name": "Люблинско-Дмитровская", "color": "Салатовый", "number": 10},
    {"id": 11, "name": "Большая кольцевая", "color": "Изумрудный", "number": 11},
    {"id": 12, "name": "Бутовская", "color": "Светло-серый", "number": 12},
    {"id": 14, "name": "Московское центральное кольцо (МЦК)", "color": "Белый с красным", "number": 14},
]

# ============================================================================
# ДАННЫЕ СТАНЦИЙ (РАСШИРЕННЫЕ)
# ============================================================================

STATIONS_DATA = [
    # Сокольническая линия (1)
    {"name": "Сокольники", "line_id": 1, "order": 1},
    {"name": "Красные Ворота", "line_id": 1, "order": 2},
    {"name": "Чистые пруды", "line_id": 1, "order": 3},
    {"name": "Лубянка", "line_id": 1, "order": 4},
    {"name": "Охотный ряд", "line_id": 1, "order": 5},
    {"name": "Библиотека им. Ленина", "line_id": 1, "order": 6},
    {"name": "Кропоткинская", "line_id": 1, "order": 7},
    {"name": "Парк культуры", "line_id": 1, "order": 8},
    {"name": "Фрунзенская", "line_id": 1, "order": 9},
    {"name": "Спортивная", "line_id": 1, "order": 10},
    {"name": "Воробьёвы горы", "line_id": 1, "order": 11},
    {"name": "Университет", "line_id": 1, "order": 12},
    {"name": "Проспект Вернадского", "line_id": 1, "order": 13},
    {"name": "Юго-Западная", "line_id": 1, "order": 14},
    {"name": "Тропарёво", "line_id": 1, "order": 15},
    {"name": "Саларьево", "line_id": 1, "order": 16},
    {"name": "Филатов луг", "line_id": 1, "order": 17},
    {"name": "Прокшино", "line_id": 1, "order": 18},
    {"name": "Ольховая", "line_id": 1, "order": 19},
    {"name": "Коммунарка", "line_id": 1, "order": 20},

    # Замоскворецкая линия (2)
    {"name": "Речной вокзал", "line_id": 2, "order": 1},
    {"name": "Водный стадион", "line_id": 2, "order": 2},
    {"name": "Войковская", "line_id": 2, "order": 3},
    {"name": "Сокол", "line_id": 2, "order": 4},
    {"name": "Аэропорт", "line_id": 2, "order": 5},
    {"name": "Динамо", "line_id": 2, "order": 6},
    {"name": "Белорусская", "line_id": 2, "order": 7},
    {"name": "Маяковская", "line_id": 2, "order": 8},
    {"name": "Тверская", "line_id": 2, "order": 9},
    {"name": "Театральная", "line_id": 2, "order": 10},
    {"name": "Новокузнецкая", "line_id": 2, "order": 11},
    {"name": "Павелецкая", "line_id": 2, "order": 12},
    {"name": "Автозаводская", "line_id": 2, "order": 13},
    {"name": "Технопарк", "line_id": 2, "order": 14},
    {"name": "Коломенская", "line_id": 2, "order": 15},
    {"name": "Каширская", "line_id": 2, "order": 16},
    {"name": "Кантемировская", "line_id": 2, "order": 17},
    {"name": "Царицыно", "line_id": 2, "order": 18},
    {"name": "Орехово", "line_id": 2, "order": 19},

    # Арбатско-Покровская линия (3)
    {"name": "Щёлковская", "line_id": 3, "order": 1},
    {"name": "Первомайская", "line_id": 3, "order": 2},
    {"name": "Измайловская", "line_id": 3, "order": 3},
    {"name": "Партизанская", "line_id": 3, "order": 4},
    {"name": "Семёновская", "line_id": 3, "order": 5},
    {"name": "Электрозаводская", "line_id": 3, "order": 6},
    {"name": "Бауманская", "line_id": 3, "order": 7},
    {"name": "Курская", "line_id": 3, "order": 8},
    {"name": "Площадь Революции", "line_id": 3, "order": 9},
    {"name": "Арбатская", "line_id": 3, "order": 10},
    {"name": "Смоленская", "line_id": 3, "order": 11},
    {"name": "Киевская", "line_id": 3, "order": 12},
    {"name": "Парк Победы", "line_id": 3, "order": 13},
    {"name": "Славянский бульвар", "line_id": 3, "order": 14},
    {"name": "Кунцевская", "line_id": 3, "order": 15},
    {"name": "Молодёжная", "line_id": 3, "order": 16},
    {"name": "Крылатское", "line_id": 3, "order": 17},
    {"name": "Строгино", "line_id": 3, "order": 18},

    # Кольцевая линия (5)
    {"name": "Киевская", "line_id": 5, "order": 1},
    {"name": "Краснопресненская", "line_id": 5, "order": 2},
    {"name": "Белорусская", "line_id": 5, "order": 3},
    {"name": "Новослободская", "line_id": 5, "order": 4},
    {"name": "Проспект Мира", "line_id": 5, "order": 5},
    {"name": "Комсомольская", "line_id": 5, "order": 6},
    {"name": "Курская", "line_id": 5, "order": 7},
    {"name": "Таганская", "line_id": 5, "order": 8},
    {"name": "Павелецкая", "line_id": 5, "order": 9},
    {"name": "Добрынинская", "line_id": 5, "order": 10},
    {"name": "Октябрьская", "line_id": 5, "order": 11},
    {"name": "Парк культуры", "line_id": 5, "order": 12},

    # Калужско-Рижская линия (6)
    {"name": "Медведково", "line_id": 6, "order": 1},
    {"name": "Бабушкинская", "line_id": 6, "order": 2},
    {"name": "Свиблово", "line_id": 6, "order": 3},
    {"name": "Ботанический сад", "line_id": 6, "order": 4},
    {"name": "ВДНХ", "line_id": 6, "order": 5},
    {"name": "Алексеевская", "line_id": 6, "order": 6},
    {"name": "Рижская", "line_id": 6, "order": 7},
    {"name": "Проспект Мира", "line_id": 6, "order": 8},
    {"name": "Сухаревская", "line_id": 6, "order": 9},
    {"name": "Тургеневская", "line_id": 6, "order": 10},
    {"name": "Китай-город", "line_id": 6, "order": 11},
    {"name": "Третьяковская", "line_id": 6, "order": 12},
    {"name": "Октябрьская", "line_id": 6, "order": 13},

    # Таганско-Краснопресненская линия (7)
    {"name": "Планерная", "line_id": 7, "order": 1},
    {"name": "Сходненская", "line_id": 7, "order": 2},
    {"name": "Тушинская", "line_id": 7, "order": 3},
    {"name": "Щукинская", "line_id": 7, "order": 4},
    {"name": "Октябрьское поле", "line_id": 7, "order": 5},
    {"name": "Полежаевская", "line_id": 7, "order": 6},
    {"name": "Беговая", "line_id": 7, "order": 7},
    {"name": "Улица 1905 года", "line_id": 7, "order": 8},
    {"name": "Баррикадная", "line_id": 7, "order": 9},
    {"name": "Пушкинская", "line_id": 7, "order": 10},
    {"name": "Кузнецкий мост", "line_id": 7, "order": 11},
    {"name": "Китай-город", "line_id": 7, "order": 12},
    {"name": "Таганская", "line_id": 7, "order": 13},
    {"name": "Пролетарская", "line_id": 7, "order": 14},

    # Серпуховско-Тимирязевская линия (9)
    {"name": "Алтуфьево", "line_id": 9, "order": 1},
    {"name": "Бибирево", "line_id": 9, "order": 2},
    {"name": "Отрадное", "line_id": 9, "order": 3},
    {"name": "Владыкино", "line_id": 9, "order": 4},
    {"name": "Петровско-Разумовская", "line_id": 9, "order": 5},
    {"name": "Тимирязевская", "line_id": 9, "order": 6},
    {"name": "Дмитровская", "line_id": 9, "order": 7},
    {"name": "Савёловская", "line_id": 9, "order": 8},
    {"name": "Менделеевская", "line_id": 9, "order": 9},
    {"name": "Цветной бульвар", "line_id": 9, "order": 10},
    {"name": "Чеховская", "line_id": 9, "order": 11},
    {"name": "Боровицкая", "line_id": 9, "order": 12},
    {"name": "Полянка", "line_id": 9, "order": 13},
    {"name": "Серпуховская", "line_id": 9, "order": 14},
    {"name": "Тульская", "line_id": 9, "order": 15},
]

# ============================================================================
# ДАННЫЕ ПЕРЕСАДОЧНЫХ УЗЛОВ
# ============================================================================

TRANSFERS_DATA = [
    # Китай-город (6 ↔ 7)
    {"name1": "Китай-город", "line1": 6, "name2": "Китай-город", "line2": 7,
     "type": "cross-platform", "time": 2},

    # Третьяковская (6 ↔ 8)
    {"name1": "Третьяковская", "line1": 6, "name2": "Третьяковская", "line2": 8,
     "type": "underground", "time": 3},

    # Парк культуры (1 ↔ 5)
    {"name1": "Парк культуры", "line1": 1, "name2": "Парк культуры", "line2": 5,
     "type": "underground", "time": 2},

    # Библиотека им. Ленина / Арбатская / Боровицкая / Александровский сад
    {"name1": "Библиотека им. Ленина", "line1": 1, "name2": "Арбатская", "line2": 3,
     "type": "underground", "time": 5},
    {"name1": "Библиотека им. Ленина", "line1": 1, "name2": "Боровицкая", "line2": 9,
     "type": "underground", "time": 4},

    # Белорусская (2 ↔ 5)
    {"name1": "Белорусская", "line1": 2, "name2": "Белорусская", "line2": 5,
     "type": "underground", "time": 2},

    # Курская (3 ↔ 5)
    {"name1": "Курская", "line1": 3, "name2": "Курская", "line2": 5,
     "type": "underground", "time": 3},

    # Таганская / Марксистская (5 ↔ 7 ↔ 8)
    {"name1": "Таганская", "line1": 5, "name2": "Таганская", "line2": 7,
     "type": "underground", "time": 3},
    {"name1": "Таганская", "line1": 5, "name2": "Марксистская", "line2": 8,
     "type": "underground", "time": 4},

    # Проспект Мира (5 ↔ 6)
    {"name1": "Проспект Мира", "line1": 5, "name2": "Проспект Мира", "line2": 6,
     "type": "underground", "time": 2},

    # Комсомольская (5 ↔ 1)
    {"name1": "Комсомольская", "line1": 5, "name2": "Комсомольская", "line2": 1,
     "type": "underground", "time": 2},

    # Павелецкая (2 ↔ 5)
    {"name1": "Павелецкая", "line1": 2, "name2": "Павелецкая", "line2": 5,
     "type": "underground", "time": 3},

    # Добрынинская / Серпуховская (5 ↔ 9)
    {"name1": "Добрынинская", "line1": 5, "name2": "Серпуховская", "line2": 9,
     "type": "underground", "time": 3},

    # Октябрьская (5 ↔ 6)
    {"name1": "Октябрьская", "line1": 5, "name2": "Октябрьская", "line2": 6,
     "type": "underground", "time": 2},

    # Полежаевская / Хорошёвская (7 ↔ 11)
    {"name1": "Полежаевская", "line1": 7, "name2": "Хорошёвская", "line2": 11,
     "type": "underground", "time": 2},
]

# ============================================================================
# ДАННЫЕ НАЙДЕННЫХ ВЕЩЕЙ
# ============================================================================

FOUND_ITEMS_DATA = [
    {"description": "Беспроводные наушники в белом кейсе, на кейсе царапина, внутри левый наушник"},
    {"description": "Блок питания USB-C на 65 ватт, белый, от ноутбука Xiaomi"},
    {"description": "Флешка Kingston синего цвета, 32 гигабайта, на корпусе царапины"},
    {"description": "Внешний аккумулятор Xiaomi, белый, два порта USB"},
    {"description": "Apple Watch Series 6, чёрный ремешок, стекло треснуто"},
    {"description": "Чёрный автоматический зонт, ручка деревянная, в сложенном виде 90 см"},
    {"description": "Шапка синего цвета, с помпоном, размер 56-58"},
    {"description": "Перчатки чёрные, кожаные, размер M, подкладка шерстяная"},
    {"description": "Чёрная бейсболка с вышивкой 'Московский метрополитен'"},
    {"description": "Шарф серый, кашемировый, длина 180 см"},
    {"description": "Тканевая сумка бежевого цвета, с длинными ручками, внутри карман"},
    {"description": "Очки в чёрной оправе, диоптрии -2.5, в красном футляре"},
    {"description": "Паспорт гражданина РФ, серия 4510 номер 123456, на имя Иванов Иван Иванович"},
    {"description": "Студенческий билет МГУ, синяя обложка, факультет ВМК"},
    {"description": "В/У категория B, на имя Петрова Алексея Сергеевича"},
    {"description": "Карта Т-Банк, чёрная, платёжная система Мир"},
    {"description": "Связка из трёх ключей, брелок в виде метро, силиконовый"},
    {"description": "Кошелёк коричневый, кожаный, внутри 500 рублей и скидочные карты"},
    {"description": "Детский зонт-автомат, розовый, с рисунком 'Единорог'"},
    {"description": "Мягкая игрушка заяц, белый, 30 см, с голубым бантом"},
    {"description": "Термос стальной, 500 мл, крышка-чашка, синий"},
    {"description": "Книга 'Мастер и Маргарита', издательство АСТ, в мягкой обложке"},
    {"description": "iPad 9 поколения, серый космос, в чёрном чехле-книжке"},
]

# ============================================================================
# ДАННЫЕ ПОТЕРЯННЫХ ВЕЩЕЙ (ЗАЯВКИ)
# ============================================================================

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
    {"description": "Потерял планшет айпад в сером чехле"},
    {"description": "Оставила термос синий в вагоне"},
]


# ============================================================================
# ФУНКЦИИ ЗАПОЛНЕНИЯ
# ============================================================================

async def create_lines(session: AsyncSession):
    """Создание справочника линий."""
    print("Создаю линии метро...")

    for line_data in LINES_DATA:
        line = Line(**line_data)
        session.add(line)

    await session.commit()
    print(f"Создано {len(LINES_DATA)} линий")


async def create_stations(session: AsyncSession):
    """Создание справочника станций."""
    print("Создаю станции метро...")

    station_map = {}

    for station_data in STATIONS_DATA:
        station = Station(
            name=station_data["name"],
            line_id=station_data["line_id"],
            order_number=station_data["order"]
        )
        session.add(station)
        await session.flush()
        station_map[(station_data["name"], station_data["line_id"])] = station.id

    await session.commit()
    print(f"Создано {len(STATIONS_DATA)} станций")

    return station_map


async def create_transfers(session: AsyncSession, station_map):
    """Создание пересадочных узлов."""
    print("Создаю пересадочные узлы...")

    transfers_created = 0

    for transfer_data in TRANSFERS_DATA:
        station_id_1 = station_map.get((transfer_data["name1"], transfer_data["line1"]))
        station_id_2 = station_map.get((transfer_data["name2"], transfer_data["line2"]))

        if station_id_1 and station_id_2:
            # Проверяем, нет ли уже такой пересадки
            existing = await session.execute(
                select(TransferPoint).where(
                    TransferPoint.station_id_1 == station_id_1,
                    TransferPoint.station_id_2 == station_id_2
                )
            )

            if not existing.scalar_one_or_none():
                transfer = TransferPoint(
                    station_id_1=station_id_1,
                    station_id_2=station_id_2,
                    line_id_1=transfer_data["line1"],
                    line_id_2=transfer_data["line2"],
                    transfer_type=transfer_data["type"],
                    transfer_time_minutes=transfer_data["time"],
                    distance_meters=random.choice([200, 300, 400, 500]),
                    is_wheelchair_accessible=random.choice([True, False])
                )
                session.add(transfer)
                transfers_created += 1

    await session.commit()
    print(f"Создано {transfers_created} пересадочных узлов")


async def create_found_items(session: AsyncSession, station_ids):
    """Создание найденных вещей."""
    print("Создаю найденные вещи...")

    today = datetime.now().date()

    for item_data in FOUND_ITEMS_DATA:
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
    """Создание тестового пользователя."""
    print("Создаю тестового пользователя...")

    user = User(
        telegram_id=123456789,
        token="test_user_token_123456"
    )
    session.add(user)
    await session.commit()

    print(f"Создан пользователь с ID: {user.id}, telegram_id: {user.telegram_id}")
    return user


async def create_lost_items(session: AsyncSession, user, station_ids):
    """Создание потерянных вещей (заявок)."""
    print("Создаю заявки на потерянные вещи...")

    today = datetime.now().date()
    statuses = ["pending", "matched", "notified", "closed"]
    weights = [0.4, 0.3, 0.2, 0.1]

    lost_items = []

    for item_data in LOST_ITEMS_DATA:
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


async def create_matches(session: AsyncSession, lost_items, found_items):
    """Создание сопоставлений между потерянными и найденными вещами."""
    print("Создаю сопоставления...")

    matches_created = 0

    for lost_item in lost_items:
        if lost_item.status not in ["matched", "notified", "closed"]:
            continue

        similar = await find_similar_items(
            session,
            lost_item.embedding,
            limit=1,
            similarity_threshold=0.7
        )

        if similar:
            found_item, similarity = similar[0]

            existing = await session.execute(
                select(Match).where(
                    Match.lost_item_id == lost_item.id,
                    Match.found_item_id == found_item.id
                )
            )

            if not existing.scalar_one_or_none():
                match = Match(
                    lost_item_id=lost_item.id,
                    found_item_id=found_item.id,
                    similarity=similarity,
                    status="sent" if lost_item.status == "notified" else "pending"
                )

                if lost_item.status == "notified":
                    match.notified_at = datetime.now() - timedelta(hours=random.randint(1, 48))

                if lost_item.status == "closed":
                    match.status = "accepted"
                    match.notified_at = datetime.now() - timedelta(days=random.randint(1, 7))
                    match.responded_at = match.notified_at + timedelta(hours=random.randint(1, 24))

                session.add(match)
                matches_created += 1

    await session.commit()
    print(f"Создано {matches_created} сопоставлений")


# ============================================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================================

async def generate_synthetic_data():
    """Основная функция наполнения БД синтетическими данными."""
    print("\n" + "=" * 60)
    print("НАЧАЛО ЗАГРУЗКИ СИНТЕТИЧЕСКИХ ДАННЫХ")
    print("=" * 60 + "\n")

    async with AsyncSessionLocal() as session:
        # Проверяем, есть ли уже данные
        result = await session.execute(select(Line).limit(1))
        if result.scalar_one_or_none():
            print("База данных уже содержит данные. Пропускаем...")
            return

        # 1. Линии
        await create_lines(session)

        # 2. Станции
        station_map = await create_stations(session)
        station_ids = list(station_map.values())

        # 3. Пересадки
        await create_transfers(session, station_map)

        # 4. Найденные вещи
        found_items = await create_found_items(session, station_ids)

        # 5. Тестовый пользователь
        user = await create_test_user(session)

        # 6. Потерянные вещи
        lost_items = await create_lost_items(session, user, station_ids)

        # 7. Сопоставления
        await create_matches(session, lost_items, found_items)

    print("\n" + "=" * 60)
    print("ЗАГРУЗКА СИНТЕТИЧЕСКИХ ДАННЫХ ЗАВЕРШЕНА")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(generate_synthetic_data())