from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import aiosqlite

DB_PATH = "database.db"
BUSINESS_COLLECT_COOLDOWN = timedelta(hours=24)

BUSINESSES_CATALOG: Dict[str, Dict] = {
    "grand_espresso": {
        "name": 'Комиссионный дом "Второй Шанс"',
        "price": 1_000_000,
        "base_income": 275_000,
        "income_min": 250_000,
        "income_max": 300_000,
    },
    "golden_croissant": {
        "name": 'Бистро "На Ходу"',
        "price": 3_000_000,
        "base_income": 400_000,
        "income_min": 300_000,
        "income_max": 500_000,
    },
    "fashion_house": {
        "name": 'Бутик "Северный Лоск"',
        "price": 6_000_000,
        "base_income": 550_000,
        "income_min": 500_000,
        "income_max": 600_000,
    },
    "gourmania": {
        "name": 'Ресторан "Лунный Берег"',
        "price": 13_000_000,
        "base_income": 1_500_000,
        "income_min": 1_000_000,
        "income_max": 2_000_000,
    },
    "global_market": {
        "name": 'Маркет "Круглые Сутки"',
        "price": 20_000_000,
        "base_income": 2_500_000,
        "income_min": 2_000_000,
        "income_max": 3_000_000,
    },
    "fuel_giant": {
        "name": 'Сеть АЗС "Импульс Ойл"',
        "price": 75_000_000,
        "base_income": 9_500_000,
        "income_min": 8_000_000,
        "income_max": 11_000_000,
    },
    "neboskreb": {
        "name": 'Девелоперская группа "Монолит Вектор"',
        "price": 200_000_000,
        "base_income": 22_500_000,
        "income_min": 20_000_000,
        "income_max": 25_000_000,
    },
    "imax_empire": {
        "name": 'Клуб развлечений "Золотая Фишка"',
        "price": 300_000_000,
        "base_income": 37_500_000,
        "income_min": 35_000_000,
        "income_max": 40_000_000,
    },
    "worldwide_holdings": {
        "name": 'Инвестхолдинг "Союз Капитал"',
        "price": 500_000_000,
        "base_income": 77_500_000,
        "income_min": 70_000_000,
        "income_max": 85_000_000,
    },
    "powercore": {
        "name": 'Биобанк "Helix Nova"',
        "price": 650_000_000,
        "base_income": 95_000_000,
        "income_min": 90_000_000,
        "income_max": 100_000_000,
    },
    "cybersoft": {
        "name": 'Верфь "Ocean Matrix"',
        "price": 750_000_000,
        "base_income": 120_000_000,
        "income_min": 110_000_000,
        "income_max": 130_000_000,
    },
    "neotech": {
        "name": 'Аэрокосмический концерн "Orion Dynamics"',
        "price": 1_000_000_000,
        "base_income": 165_000_000,
        "income_min": 150_000_000,
        "income_max": 180_000_000,
    },
}

PURCHASEABLE_BUSINESS_KEYS = [
    "grand_espresso",
    "golden_croissant",
    "fashion_house",
    "gourmania",
    "global_market",
    "fuel_giant",
    "neboskreb",
    "imax_empire",
    "worldwide_holdings",
    "powercore",
    "cybersoft",
    "neotech",
]

# Совместимость со старыми филиалами в базе данных.
BUSINESSES_CATALOG["premium_detailing"] = dict(BUSINESSES_CATALOG["golden_croissant"])
BUSINESSES_CATALOG["agro_empire"] = dict(BUSINESSES_CATALOG["global_market"])
BUSINESSES_CATALOG["iron_world"] = dict(BUSINESSES_CATALOG["global_market"])
BUSINESSES_CATALOG["empire_realty"] = dict(BUSINESSES_CATALOG["neboskreb"])
BUSINESSES_CATALOG["megadrive"] = dict(BUSINESSES_CATALOG["fuel_giant"])
BUSINESSES_CATALOG["royal_beauty"] = dict(BUSINESSES_CATALOG["fashion_house"])
BUSINESSES_CATALOG["golden_trust"] = dict(BUSINESSES_CATALOG["grand_espresso"])
BUSINESSES_CATALOG["diamond_crown"] = dict(BUSINESSES_CATALOG["gourmania"])

UPGRADE_BONUSES = {0: 0.0, 1: 0.10, 2: 0.25, 3: 0.50}


def get_upgrade_cost_for_business(business_meta: Dict, new_level: int) -> int:
    base_price = int(business_meta.get("price", 0) or 0)
    level_multipliers = {
        1: 0.05,
        2: 0.10,
        3: 0.20,
    }
    multiplier = level_multipliers.get(int(new_level), 0.20)
    return max(100_000, int(base_price * multiplier))


async def add_business(user_id: int, business_key: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COALESCE(MAX(branch_no), 0) FROM businesses WHERE user_id = ? AND business_key = ?",
            (user_id, business_key),
        )
        next_branch = int((await cur.fetchone())[0]) + 1
        await db.execute(
            "INSERT INTO businesses (user_id, business_key, branch_no) VALUES (?, ?, ?)",
            (user_id, business_key, next_branch),
        )
        await db.commit()
        return next_branch


async def get_user_businesses(user_id: int) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, business_key, branch_no, upgrade_level, products, branch_balance, talisman_active, last_collected_at "
            "FROM businesses WHERE user_id = ? ORDER BY business_key, branch_no",
            (user_id,),
        )
        rows = [dict(r) for r in await cur.fetchall()]
    for row in rows:
        row["meta"] = BUSINESSES_CATALOG.get(
            row["business_key"],
            {"name": row["business_key"], "base_income": 0, "price": 0},
        )
    return rows


async def get_all_business_branch_counts() -> Dict[str, int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT user_id, COUNT(*) FROM businesses GROUP BY user_id"
        )
        rows = await cur.fetchall()
    return {str(int(user_id)): int(count) for user_id, count in rows}


async def get_business_by_id(user_id: int, business_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, business_key, branch_no, upgrade_level, products, branch_balance, talisman_active, last_collected_at "
            "FROM businesses WHERE user_id = ? AND id = ?",
            (user_id, business_id),
        )
        row = await cur.fetchone()
    if not row:
        return None
    item = dict(row)
    item["meta"] = BUSINESSES_CATALOG.get(
        item["business_key"],
        {"name": item["business_key"], "base_income": 0, "price": 0},
    )
    return item


def get_business_collect_ready_at(business: Dict) -> Optional[datetime]:
    raw_value = business.get("last_collected_at")
    if not raw_value:
        return None
    try:
        return datetime.fromisoformat(str(raw_value)) + BUSINESS_COLLECT_COOLDOWN
    except (TypeError, ValueError):
        return None


def get_business_collect_seconds_left(business: Dict) -> int:
    ready_at = get_business_collect_ready_at(business)
    if ready_at is None:
        return 0
    return max(0, int((ready_at - datetime.now()).total_seconds()))


async def delete_business_branch(user_id: int, business_id: int) -> Tuple[bool, Optional[Dict]]:
    business = await get_business_by_id(user_id, business_id)
    if not business:
        return False, None
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM businesses WHERE id = ? AND user_id = ?",
            (business_id, user_id),
        )
        await db.commit()
    return True, business


async def delete_business_group(user_id: int, business_key: str) -> Tuple[int, Optional[Dict]]:
    businesses = await get_user_businesses(user_id)
    target_branches = [biz for biz in businesses if biz["business_key"] == business_key]
    if not target_branches:
        return 0, None
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM businesses WHERE user_id = ? AND business_key = ?",
            (user_id, business_key),
        )
        await db.commit()
    return len(target_branches), target_branches[0]


async def upgrade_business(user_id: int, business_id: int) -> Tuple[bool, str, int]:
    business = await get_business_by_id(user_id, business_id)
    if not business:
        return False, "Филиал не найден.", 0
    level = int(business["upgrade_level"])
    if level >= 3:
        return False, "Филиал уже на максимальном уровне.", 0
    new_level = level + 1
    cost = get_upgrade_cost_for_business(business["meta"], new_level)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE businesses SET upgrade_level = ? WHERE id = ? AND user_id = ?",
            (new_level, business_id, user_id),
        )
        await db.commit()
    return True, f"Улучшение до уровня {new_level} применено.", cost


async def refill_products(user_id: int, business_id: int, amount: int, max_products: int = 100) -> Tuple[bool, str, int]:
    business = await get_business_by_id(user_id, business_id)
    if not business:
        return False, "Филиал не найден.", 0
    current = int(business["products"])
    if current >= max_products:
        return False, "Продукты уже заполнены.", 0
    add_amount = max(1, min(amount, max_products - current))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE businesses SET products = products + ? WHERE id = ? AND user_id = ?",
            (add_amount, business_id, user_id),
        )
        await db.commit()
    return True, f"Пополнено на {add_amount} ед.", add_amount


async def collect_income(user_id: int, business_id: int) -> Tuple[bool, str, int]:
    business = await get_business_by_id(user_id, business_id)
    if not business:
        return False, "Филиал не найден.", 0
    seconds_left = get_business_collect_seconds_left(business)
    if seconds_left > 0:
        hours = seconds_left // 3600
        minutes = (seconds_left % 3600) // 60
        return False, f"Сбор будет доступен через {hours}ч. {minutes}м.", 0
    products_to_spend = 5
    current_products = int(business["products"])
    if current_products < products_to_spend:
        return False, f"Недостаточно продуктов. Для сбора нужно минимум {products_to_spend}.", 0
    base_income = int(business["meta"]["base_income"])
    upgrade_bonus = UPGRADE_BONUSES.get(int(business["upgrade_level"]), 0.0)
    talisman_bonus = 5.0 if int(business["talisman_active"]) else 0.0
    final_income = int(base_income * (1 + upgrade_bonus + talisman_bonus))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE businesses SET products = products - ?, branch_balance = branch_balance + ?, last_collected_at = ? "
            "WHERE id = ? AND user_id = ?",
            (products_to_spend, final_income, datetime.now().isoformat(), business_id, user_id),
        )
        await db.commit()
    return True, f"Доход собран. Списано продуктов: {products_to_spend}.", final_income


async def activate_business_talisman(user_id: int, business_id: int) -> Tuple[bool, str]:
    business = await get_business_by_id(user_id, business_id)
    if not business:
        return False, "Филиал не найден."
    if int(business.get("talisman_active", 0)) == 1:
        return False, f'Талисман уже активирован на филиал #{business["branch_no"]}.'
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE businesses SET talisman_active = 1 WHERE id = ? AND user_id = ?",
            (business_id, user_id),
        )
        await db.commit()
    return True, f'Талисман активирован на филиал #{business["branch_no"]}.'


async def has_active_business_talisman(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM businesses WHERE user_id = ? AND talisman_active = 1 LIMIT 1",
            (user_id,),
        )
        row = await cur.fetchone()
    return bool(row)
