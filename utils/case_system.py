import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import aiosqlite

from utils.inventory import add_item
from utils.business import add_business, BUSINESSES_CATALOG

DB_PATH = "database.db"

CASE_DEFS = {
    "daily": {"name": "Ежедневный кейс", "money_cost": 0, "banana_cost": 0, "daily": True},
    "homeless": {"name": "Кейс Бомжа", "money_cost": 500000, "banana_cost": 0, "daily": False},
    "standard": {"name": "Стандартный кейс", "money_cost": 2000000, "banana_cost": 0, "daily": False},
    "special": {"name": "Особый кейс", "money_cost": 0, "banana_cost": 2000, "daily": False},
}

CASE_CHANCES_TEXT = """Шансы выпадения по кейсам:

1. Ежедневный кейс
- Игровая валюта (10.000-100.000$) — 80%
- VIP на 1 день — 10%
- Редкий предмет (+10% к доходу /приз) — 10%

2. Кейс Бомжа
- Игровая валюта (50.000-400.000$) — 70%
- Случайный бизнес из всех бизнесов бота — 15%
  Чем дешевле бизнес, тем выше шанс. В этом кейсе сильный уклон в дешёвые бизнесы.
- VIP на 7 дней — 10%
- Редкий предмет (+10% к доходу /приз) — 4%
- Эпический предмет (+25% к доходу /приз) — 1%

3. Стандартный кейс
- Игровая валюта (300.000-4.000.000$) — 60%
- Случайный бизнес из всех бизнесов бота — 20%
  Чем дешевле бизнес, тем выше шанс. В этом кейсе шанс на дорогие бизнесы выше, чем в Кейсе Бомжа.
- VIP на 30 дней — 12%
- Редкий предмет (+10% к доходу /приз) — 3%
- Эпический предмет (+25% к доходу /приз) — 3%
- Легендарный предмет (+50% к доходу /приз) — 1%
- Талисман "Золотой Телец" (+500% к доходу бизнеса) — 1%

4. Особый кейс
- Игровая валюта (10.000.000-300.000.000$) — 40%
- Случайный бизнес из всех бизнесов бота — 25%
  Чем дешевле бизнес, тем выше шанс, но в этом кейсе дорогие бизнесы выпадают заметно чаще, чем в остальных платных кейсах.
- VIP на 90 дней — 13%
- Редкий предмет (+10% к доходу /приз) — 4%
- Эпический предмет (+25% к доходу /приз) — 6%
- Легендарный предмет (+50% к доходу /приз) — 6%
- Талисман "Золотой Телец" (+500% к доходу бизнеса) — 6%"""


def _business_reward_text(business_key: str) -> str:
    business_meta = BUSINESSES_CATALOG.get(business_key, {})
    return str(business_meta.get("name", business_key))


def _pick_weighted_business(case_type: str) -> Dict:
    available_keys = list(BUSINESSES_CATALOG.keys())
    case_bias = {
        "homeless": 2.4,
        "standard": 1.6,
        "special": 1.15,
    }
    bias = case_bias.get(case_type, 1.6)

    weights = []
    for key in available_keys:
        price = max(1, int(BUSINESSES_CATALOG.get(key, {}).get("price", 1) or 1))
        normalized_price = price / 1_000_000
        weight = int(1_000_000 / (normalized_price ** bias))
        weights.append(max(1, weight))

    selected_key = random.choices(available_keys, weights=weights, k=1)[0]
    return {"type": "business", "business_key": selected_key, "text": _business_reward_text(selected_key)}


def _pick_case_reward(case_type: str) -> Dict:
    roll = random.random() * 100

    if case_type == "daily":
        if roll < 80:
            return {"type": "money", "amount": random.randint(10000, 100000), "text": "Игровая валюта"}
        if roll < 90:
            return {"type": "vip_days", "days": 1, "text": "VIP на 1 день"}
        return {"type": "item", "item_type": "prize_bonus", "name": "Редкий предмет (+10% к доходу /приз)", "value": 10}

    if case_type == "homeless":
        if roll < 70:
            return {"type": "money", "amount": random.randint(50000, 400000), "text": "Игровая валюта"}
        if roll < 85:
            return _pick_weighted_business(case_type)
        if roll < 95:
            return {"type": "vip_days", "days": 7, "text": "VIP на 7 дней"}
        if roll < 99:
            return {"type": "item", "item_type": "prize_bonus", "name": "Редкий предмет (+10% к доходу /приз)", "value": 10}
        return {"type": "item", "item_type": "prize_bonus", "name": "Эпический предмет (+25% к доходу /приз)", "value": 25}

    if case_type == "standard":
        if roll < 60:
            return {"type": "money", "amount": random.randint(300000, 4000000), "text": "Игровая валюта"}
        if roll < 80:
            return _pick_weighted_business(case_type)
        if roll < 92:
            return {"type": "vip_days", "days": 30, "text": "VIP на 30 дней"}
        if roll < 95:
            return {"type": "item", "item_type": "prize_bonus", "name": "Редкий предмет (+10% к доходу /приз)", "value": 10}
        if roll < 98:
            return {"type": "item", "item_type": "prize_bonus", "name": "Эпический предмет (+25% к доходу /приз)", "value": 25}
        if roll < 99:
            return {"type": "item", "item_type": "prize_bonus", "name": "Легендарный предмет (+50% к доходу /приз)", "value": 50}
        return {"type": "item", "item_type": "business_talisman", "name": 'Талисман "Золотой Телец" (+500% к доходу бизнеса)', "value": 500}

    if roll < 40:
        return {"type": "money", "amount": random.randint(10000000, 300000000), "text": "Игровая валюта"}
    if roll < 65:
        return _pick_weighted_business(case_type)
    if roll < 78:
        return {"type": "vip_days", "days": 90, "text": "VIP на 90 дней"}
    if roll < 82:
        return {"type": "item", "item_type": "prize_bonus", "name": "Редкий предмет (+10% к доходу /приз)", "value": 10}
    if roll < 88:
        return {"type": "item", "item_type": "prize_bonus", "name": "Эпический предмет (+25% к доходу /приз)", "value": 25}
    if roll < 94:
        return {"type": "item", "item_type": "prize_bonus", "name": "Легендарный предмет (+50% к доходу /приз)", "value": 50}
    return {"type": "item", "item_type": "business_talisman", "name": 'Талисман "Золотой Телец" (+500% к доходу бизнеса)', "value": 500}


async def get_daily_remaining(user_id: int) -> Optional[timedelta]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT created_at FROM cases_log WHERE user_id = ? AND case_type = 'daily' ORDER BY id DESC LIMIT 1",
            (user_id,),
        )
        row = await cur.fetchone()
    if not row:
        return None
    last = datetime.fromisoformat(str(row[0]).replace(" ", "T"))
    next_time = last + timedelta(days=1)
    now = datetime.now()
    if now >= next_time:
        return None
    return next_time - now


async def log_case_open(user_id: int, case_type: str, reward_type: str, reward_value: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO cases_log (user_id, case_type, reward_type, reward_value) VALUES (?, ?, ?, ?)",
            (user_id, case_type, reward_type, reward_value),
        )
        await db.commit()


async def add_user_case(user_id: int, case_type: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO user_cases (user_id, case_type) VALUES (?, ?)",
            (user_id, case_type),
        )
        await db.commit()
        return int(cur.lastrowid)


async def get_user_cases(user_id: int) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, case_type, created_at FROM user_cases WHERE user_id = ? ORDER BY id",
            (user_id,),
        )
        rows = [dict(row) for row in await cur.fetchall()]
    for row in rows:
        row["meta"] = CASE_DEFS.get(row["case_type"], {"name": row["case_type"]})
    return rows


async def get_opened_cases_count(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM cases_log WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return int(row[0]) if row else 0


async def get_user_case_by_id(user_id: int, case_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, case_type, created_at FROM user_cases WHERE user_id = ? AND id = ?",
            (user_id, case_id),
        )
        row = await cur.fetchone()
    if not row:
        return None
    result = dict(row)
    result["meta"] = CASE_DEFS.get(result["case_type"], {"name": result["case_type"]})
    return result


async def remove_user_case(user_id: int, case_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM user_cases WHERE user_id = ? AND id = ?", (user_id, case_id))
        await db.commit()


async def open_case(case_type: str, user_id: int) -> Tuple[Dict, str]:
    reward = _pick_case_reward(case_type)
    message = ""
    if reward["type"] == "item":
        await add_item(user_id, reward["item_type"], reward["name"], reward["value"])
        message = reward["name"]
    elif reward["type"] == "business":
        await add_business(user_id, reward["business_key"])
        message = reward["text"]
    elif reward["type"] == "money":
        message = f'{reward["amount"]:,}$'.replace(",", ".")
    elif reward["type"] == "vip_days":
        message = reward["text"]
    await log_case_open(user_id, case_type, reward["type"], message)
    return reward, message
