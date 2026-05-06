import os, re
import json
import time
import urllib
from typing import Optional
from datetime import datetime, timedelta
from obnova.mutelog import mutelogs_command

import random
import asyncio
import yaml
import pymysql.cursors
import logging
import aiohttp
import aiosqlite

from vkbottle.bot import Bot, Message, rules
from vkbottle import Keyboard, Callback, KeyboardButtonColor, Text, GroupEventType, GroupTypes, User
import sqlite3
import sys
import inspect

import pytz
from utils.db import init_economy_schema
from utils.case_system import (
    CASE_CHANCES_TEXT,
    CASE_DEFS,
    add_user_case,
    get_daily_remaining,
    get_opened_cases_count,
    get_user_case_by_id,
    get_user_cases,
    open_case,
    remove_user_case,
)
from utils.business import (
    BUSINESSES_CATALOG,
    PURCHASEABLE_BUSINESS_KEYS,
    UPGRADE_BONUSES,
    get_upgrade_cost_for_business,
    activate_business_talisman,
    add_business,
    collect_income,
    delete_business_branch,
    delete_business_group,
    get_all_business_branch_counts,
    get_business_by_id,
    get_business_collect_ready_at,
    get_business_collect_seconds_left,
    get_user_businesses,
    refill_products,
    upgrade_business,
)
from utils.sqlite_utils import DB_WRITE_LOCK, connect_sqlite
from utils.inventory import (
    apply_item_effect,
    get_inventory,
    get_item_by_id,
    get_prize_bonus_percent,
    remove_item,
    take_item_by_id,
)

# Сколько на страницу
MAX_LOGS=20
MAX_LOGS=20

# настройка отсылки сообщений в ЛС
p_message = 'Бот не принимает личные сообщения. Обратитесь к https://vk.com/makswwy'

with open("config.json", "r") as js:
    open_file = json.load(js)

config = open_file

# конфиг.жс

bot = Bot(token=open_file['bot-token'])
chatsbansgame = config['banschats']
groupid = config['group_id']
tchat = config['testers_chats']
bansids = config['form_not']

class Console:
    @staticmethod
    def log(*args):
        print(*args)

console = Console()
    
# ====== CONFIG / FILES ======
CONFIG_FILE = "config.json"
ROLES_FILE = "roles.json"
BANS_FILE = "bansoffer.json"
BANS_COMMANDS_FILE = "banscommands.json"
CASE_PURCHASE_IMAGES = {
    "daily": "photo_2026-04-29_10-34-30.jpg",
    "homeless": "photo_2026-04-29_08-27-38.jpg",
    "standard": "photo_2026-04-29_10-34-30.jpg",
    "special": "photo_2026-04-29_08-57-48.jpg",
}
CASE_REWARD_IMAGES = {
    "daily": "photo_2026-04-29_10-37-25.jpg",
    "homeless": "photo_2026-04-29_08-27-38.jpg",
    "standard": "photo_2026-04-29_10-34-30.jpg",
    "special": "photo_2026-04-29_08-57-48.jpg",
}

# ---------------- Работа с файлом ----------------
def load_banscommands():
    try:
        with open(BANS_COMMANDS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_banscommands(bans):
    with open(BANS_COMMANDS_FILE, "w", encoding="utf-8") as f:
        json.dump(bans, f, ensure_ascii=False, indent=4)

# ---------------- Проверка бана ----------------
def check_ban(user_id: int):
    bans = load_banscommands()
    return str(user_id) in bans

def load_bans():
    try:
        with open(BANS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_bans(bans):
    with open(BANS_FILE, "w", encoding="utf-8") as f:
        json.dump(bans, f, indent=4, ensure_ascii=False)

def is_banned(user_id: int):
    bans = load_bans()
    for ban in bans:
        if ban["user_id"] == user_id:
            return ban
    return None

# универсальная функция синхронизации
def sync_balances():
    global balances
    balances = load_data(BALANCES_FILE)
    return balances
        
# ---------------- COMMANDS LIST ----------------
cmds_users = [
    "Команда1\n",
    "Команда2\n"
]

cmds_moders = [
    "Команда 1\n",
    "Команда 2\n"
]

cmds_srmoders = [
    "SRMOD1\n",
    "SRMOD2\n"
]

cmds_admins = [
    "ADMIN1\n",
    "ADMIN2\n"
]

cmds_sradmins = [
    "SRADMIN1\n",
    "SRADMIN2\n"
]

cmds_owner = [
    "OWNER1\n"
]

cmds_sa = [
    "SA1\n",
    "SA2\n"
]

cmds_zsa = [
    "ZSA1\n",
    "ZSA2\n"
]

# ================== CONFIG ==================
CONFIG_FILE = "config.json"
BALANCES_FILE = "balances.json"
DUELS_FILE = "duels.json"
GIVEAWAYS_FILE = "giveaways.json"
PRIZES_FILE = "prizes.json"
DONATES_FILE = "donates.json"
PROMO_FILE = "promo.json"
SUBS_FILE = "subs.json"
TOP_VISIBILITY_FILE = "top_visibility.json"
BANANA_OFFERS_FILE = "banana_offers.json"
BOT_GROUP_URL = "https://vk.com/bananamanager"
    
MUTELIST_PER_PAGE = 20

def has_mute_access_sync(user_id: int, chat_id: int) -> bool:
    """Синхронная проверка прав: staff(userId,chatId) in (admin,owner,sr.administrator)
       или managers(userId).rang in (sa,zsa)"""
    global connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT rang FROM staff WHERE userId=%s AND chatId=%s", (user_id, chat_id))
            r = cursor.fetchone()
            if r and r.get("rang") in ("admin", "owner", "sr.administrator"):
                return True

            cursor.execute("SELECT rang FROM managers WHERE userId=%s", (user_id,))
            r2 = cursor.fetchone()
            if r2 and str(r2.get("rang")).lower() in ("sa", "zsa"):
                return True

        return False
    except Exception as e:
        print("MySQL error in has_mute_access_sync:", e)
        return False

# --- Вспомогательная функция: формат страниц ---
def make_page(chats: list, page: int, per_page: int = 40) -> str:
    start = (page - 1) * per_page
    end = start + per_page
    sliced = chats[start:end]
    if not sliced:
        return "Нет чатов на этой странице."
    return "\n".join(
        [f"{i+1}. {c['chatId']} | {c['title']}" for i, c in enumerate(sliced, start=start)]
    )   
    
def get_owner_chats(user_id: int):
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT chatId, title FROM chats WHERE owner=%s ORDER BY id", (user_id,))
                return cursor.fetchall()
    except Exception as e:
        print("MySQL error in get_owner_chats:", e)
        return []

def get_mutes_sync(chat_id: int, per_page: int, offset: int):
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT userId, moder, term, reason FROM mutes WHERE chatId=%s ORDER BY id LIMIT %s OFFSET %s",
                    (chat_id, per_page, offset)
                )
                return cursor.fetchall()
    except Exception as e:
        print("MySQL error in get_mutes:", e)
        return []      
    
def load_data(file):
    if os.path.exists(file):
        try:
            with open(file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_data(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Создаём пустые JSON, если их нет
for f in [BALANCES_FILE, DUELS_FILE, GIVEAWAYS_FILE, PRIZES_FILE, DONATES_FILE, PROMO_FILE, SUBS_FILE, TOP_VISIBILITY_FILE, BANANA_OFFERS_FILE]:
    if not os.path.exists(f):
        with open(f, "w", encoding="utf-8") as fp:
            json.dump({}, fp)

# Загружаем конфиг
if not os.path.exists(CONFIG_FILE):
    raise FileNotFoundError("Не найден config.json! Вставь туда bot_token, admin_id и group_id")

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)

# ================== STORAGE ==================
balances = load_data(BALANCES_FILE)
duels = load_data(DUELS_FILE)
giveaways = load_data(GIVEAWAYS_FILE)
prizes = load_data(PRIZES_FILE)
donates = load_data(DONATES_FILE)
promo = load_data(PROMO_FILE)
banana_offers = load_data(BANANA_OFFERS_FILE)

for uid in list(balances.keys()):
    if "bananas" not in balances[uid]:
        balances[uid]["bananas"] = 0
    if "business_income_today" not in balances[uid]:
        balances[uid]["business_income_today"] = 0
save_data(BALANCES_FILE, balances)

# ================== UTILS ==================
def format_number(n: int) -> str:
    return f"{n:,}".replace(",", ".")

def get_balance(user_id: int):
    uid = str(user_id)
    if uid not in balances:
        balances[uid] = {
            "wallet": 0,
            "bank": 0,
            "won": 0,
            "lost": 0,
            "won_total": 0,
            "lost_total": 0,
            "received_total": 0,
            "sent_total": 0,
            "bananas": 0,
            "business_income_today": 0,
            "vip_until": None,
            "donated": 0
        }
    if "bananas" not in balances[uid]:
        balances[uid]["bananas"] = 0
    if "business_income_today" not in balances[uid]:
        balances[uid]["business_income_today"] = 0
    return balances[uid]


def parse_giveaway_duration(raw_value: str) -> int:
    value = str(raw_value).strip().lower()
    match = re.fullmatch(r"(\d+)([smhd]?)", value)
    if not match:
        raise ValueError("invalid duration")
    amount = int(match.group(1))
    suffix = match.group(2) or "m"
    multipliers = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
    }
    seconds = amount * multipliers[suffix]
    if seconds <= 0:
        raise ValueError("duration must be positive")
    return seconds


TECH_ROLE_NAMES = {
    1: "Младший Технический Специалист",
    2: "Технический Специалист",
    3: "Старший Технический Специалист",
    4: "Куратор Технических Специалистов",
    5: "Заместитель Главного Технического Специалиста",
    6: "Главный Технический Специалист",
}


async def is_user_subscribed_to_bot_group(user_id: int) -> bool:
    try:
        resp = await bot.api.groups.is_member(group_id=groupid, user_id=user_id)
        member = getattr(resp, "member", None)
        if member is None:
            member = bool(resp)
        return bool(member)
    except Exception as e:
        print(f"[giveaway] is_member error for {user_id}: {e}")
        return False


def _revoke_subscription_rewards(balance_data: dict, sub_info: dict) -> dict:
    reward = sub_info.get("reward", {})
    reward_money = int(reward.get("money", 70000) or 0)
    reward_vip_days = int(reward.get("vip_days", 7) or 0)

    wallet_amount = int(balance_data.get("wallet", 0))
    take_from_wallet = min(wallet_amount, reward_money)
    balance_data["wallet"] = wallet_amount - take_from_wallet

    remaining = reward_money - take_from_wallet
    if remaining > 0:
        balance_data["bank"] = max(0, int(balance_data.get("bank", 0)) - remaining)

    current_vip_until = balance_data.get("vip_until")
    previous_vip_until = sub_info.get("prev_vip_until")
    if current_vip_until and reward_vip_days > 0:
        try:
            current_dt = datetime.fromisoformat(current_vip_until)
            new_dt = current_dt - timedelta(days=reward_vip_days)
            if previous_vip_until:
                previous_dt = datetime.fromisoformat(previous_vip_until)
                if new_dt < previous_dt:
                    new_dt = previous_dt
            if previous_vip_until and new_dt <= datetime.fromisoformat(previous_vip_until):
                balance_data["vip_until"] = previous_vip_until
            elif new_dt <= datetime.now():
                balance_data["vip_until"] = previous_vip_until
            else:
                balance_data["vip_until"] = new_dt.isoformat()
        except Exception:
            balance_data["vip_until"] = previous_vip_until
    return balance_data


async def finish_giveaway(giveaway_id: str):
    global giveaways, balances
    giveaway = giveaways.get(giveaway_id)
    if not giveaway:
        return

    end_ts = int(giveaway.get("end_ts", 0) or 0)
    wait_seconds = max(0, end_ts - int(time.time()))
    if wait_seconds > 0:
        await asyncio.sleep(wait_seconds)

    giveaway = giveaways.get(giveaway_id)
    if not giveaway:
        return

    peer_id = int(giveaway["peer_id"])
    amount = int(giveaway["amount"])
    creator_id = int(giveaway["creator_id"])
    participants = [int(uid) for uid in giveaway.get("participants", [])]

    valid_participants = []
    for participant_id in participants:
        if await is_user_subscribed_to_bot_group(participant_id):
            valid_participants.append(participant_id)

    if valid_participants:
        balances = load_data(BALANCES_FILE)
        lines = []
        for index, participant_id in enumerate(valid_participants, start=1):
            bal = balances.get(str(participant_id), get_balance(participant_id))
            bal["wallet"] = bal.get("wallet", 0) + amount
            balances[str(participant_id)] = bal
            try:
                full_name = await get_user_name(participant_id, None)
            except Exception:
                full_name = str(participant_id)
            lines.append(f"{index}. [id{participant_id}|{full_name}] получил(а) {format_number(amount)}$")
        save_data(BALANCES_FILE, balances)
        _clear_balance_cache()
        result_text = (
            f"@all Раздача завершена!\n\n"
            f"Организатор: @id{creator_id}\n"
            f"Награда: {format_number(amount)}$ каждому участнику\n"
            f"Подтверждённые участники:\n" + "\n".join(lines)
        )
    else:
        result_text = (
            f"@all (Раздача завершена)\n\n"
            f"Никто не получил монеты: среди участников не осталось подписанных на сообщество бота.\n"
            f"Ссылка на сообщество: https://vk.com/club{groupid}"
        )

    try:
        await bot.api.messages.send(peer_id=peer_id, random_id=0, message=result_text)
    except Exception as e:
        print(f"[giveaway] send result error: {e}")

    giveaways.pop(giveaway_id, None)
    save_data(GIVEAWAYS_FILE, giveaways)


def _resolve_auction_ends_at(lot: dict | aiosqlite.Row | str) -> datetime | None:
    ends_at_raw = lot
    created_at_raw = None
    if isinstance(lot, (dict, aiosqlite.Row)):
        ends_at_raw = lot.get("ends_at")
        created_at_raw = lot.get("created_at")

    resolved_ends_at = None
    if ends_at_raw:
        try:
            resolved_ends_at = datetime.fromisoformat(str(ends_at_raw))
        except Exception:
            resolved_ends_at = None

    created_based_ends_at = None
    if created_at_raw:
        try:
            created_based_ends_at = datetime.fromisoformat(str(created_at_raw)) + timedelta(hours=3)
        except Exception:
            created_based_ends_at = None

    if resolved_ends_at and created_based_ends_at:
        return min(resolved_ends_at, created_based_ends_at)
    return resolved_ends_at or created_based_ends_at


def _lot_time_left_text(lot: dict | aiosqlite.Row | str) -> str:
    ends_at = _resolve_auction_ends_at(lot)
    if not ends_at:
        return "неизвестно"
    delta = ends_at - datetime.now()
    if delta.total_seconds() <= 0:
        return "завершён"
    total_minutes = max(1, int(delta.total_seconds() // 60))
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}ч {minutes}м"


async def _configure_async_db(db):
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA synchronous=NORMAL")
    await db.execute("PRAGMA busy_timeout=30000")


_cache_balances = {}
_cache_businesses = {}
log = logging.getLogger("bot")


def _clear_balance_cache():
    _cache_balances.clear()
    _cache_businesses.clear()


def _cached_user_balance(user_id: int):
    if user_id not in _cache_balances:
        _cache_balances[user_id] = get_balance(user_id)
    return _cache_balances[user_id]


def _drop_user_cache(user_id: int):
    _cache_balances.pop(user_id, None)
    _cache_businesses.pop(user_id, None)


def _persist_user_balance(user_id: int, balance_data: dict, balances_data: Optional[dict] = None):
    global balances
    if balances_data is None:
        balances_data = balances
    balances_data[str(user_id)] = balance_data
    balances[str(user_id)] = balance_data
    save_data(BALANCES_FILE, balances_data)
    _drop_user_cache(user_id)


def _daily_remaining_text(delta: Optional[timedelta]) -> str:
    if not delta:
        return "доступен"
    total_minutes = max(1, int(delta.total_seconds() // 60))
    h, m = divmod(total_minutes, 60)
    return f"{h}ч {m}м"


def _business_keys_ordered():
    return list(PURCHASEABLE_BUSINESS_KEYS)


def _business_product_cost(business_meta: dict) -> int:
    return max(1000, int(business_meta.get("base_income", 0)) // 50)


def _short_business_button_label(name: str, price: int) -> str:
    del price
    max_name_len = 36
    return name if len(name) <= max_name_len else name[: max_name_len - 1].rstrip() + "…"


def _business_emoji(business_key: str) -> str:
    emoji_map = {
        "grand_espresso": "🏚️",
        "golden_croissant": "🥐",
        "fashion_house": "👗",
        "gourmania": "🍽️",
        "global_market": "🛒",
        "fuel_giant": "⛽",
        "neboskreb": "🏗️",
        "imax_empire": "🎰",
        "worldwide_holdings": "💼",
        "powercore": "🧬",
        "cybersoft": "🚢",
        "neotech": "🚀",
    }
    return emoji_map.get(business_key, "🏢")


def _is_business_talisman(item: dict) -> bool:
    return str(item.get("item_type", "")) == "business_talisman"


def _business_income_per_collect(branch: dict) -> int:
    level = int(branch.get("upgrade_level", 0))
    base_income = int(branch.get("meta", {}).get("base_income", 0))
    talisman_bonus = 5.0 if int(branch.get("talisman_active", 0)) else 0.0
    return int(base_income * (1 + UPGRADE_BONUSES.get(level, 0.0) + talisman_bonus))


def _business_income_per_day(branch: dict) -> int:
    return _business_income_per_collect(branch)


def _business_daily_potential(branch: dict) -> int:
    return _business_income_per_collect(branch)


async def _build_talisman_business_menu(user_id: int, item_id: int, page: int = 1):
    businesses = await get_user_businesses(user_id)
    available_businesses = [biz for biz in businesses if int(biz.get("talisman_active", 0)) != 1]
    kb = Keyboard(inline=True)
    if not businesses:
        return kb, None, "У вас нет бизнесов для активации талисмана."
    if not available_businesses:
        return kb, None, "🪬 Во всех ваших филиалах уже есть активный талисман."

    per_page = 4
    total_pages = max(1, (len(available_businesses) + per_page - 1) // per_page)
    page = min(max(1, page), total_pages)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = available_businesses[start:end]

    for biz in page_items:
        kb.add(
            Callback(
                f'{_business_emoji(biz["business_key"])} Филиал #{biz["branch_no"]}',
                {"command": "apply_talisman_choose", "item_id": item_id, "business_id": int(biz["id"]), "owner_id": user_id},
            ),
            color=KeyboardButtonColor.PRIMARY,
        ).row()

    if total_pages > 1:
        if page > 1:
            kb.add(
                Callback(
                    "⬅️ Назад",
                    {"command": "apply_talisman_menu", "item_id": item_id, "page": page - 1, "owner_id": user_id},
                ),
                color=KeyboardButtonColor.SECONDARY,
            )
        if page < total_pages:
            kb.add(
                Callback(
                    "➡️ Вперед",
                    {"command": "apply_talisman_menu", "item_id": item_id, "page": page + 1, "owner_id": user_id},
                ),
                color=KeyboardButtonColor.SECONDARY,
            )
        kb.row()

    text = (
        f"🪬 Выберите филиал для активации талисмана [{page}/{total_pages}].\n"
        f"В списке показаны только филиалы без талисмана.\n"
        f"После активации выбранный филиал получит +500% к доходу."
    )
    return kb, page, text


def _item_banana_value(item: dict) -> int:
    item_type = str(item.get("item_type", "") or "").lower()
    item_name = str(item.get("item_name", "") or "").lower()
    item_value = int(item.get("item_value", 0) or 0)

    if item_type == "business_talisman" or "талисман" in item_name:
        return 250
    if item_value >= 50 or "легендар" in item_name:
        return 150
    if item_value >= 25 or "эпическ" in item_name:
        return 50
    return 25


async def finalize_expired_auctions():
    now_dt = datetime.now()
    notifications = []
    economy_logs = []
    async with DB_WRITE_LOCK:
        db = await connect_sqlite()
        try:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT id, seller_id, item_type, item_name, item_value, current_bid, highest_bidder_id, created_at, ends_at "
                "FROM auction_items",
            )
            expired = [
                dict(row)
                for row in await cur.fetchall()
                if (_resolve_auction_ends_at(dict(row)) or now_dt) <= now_dt
            ]
            if not expired:
                return 0

            balances_data = load_data(BALANCES_FILE)
            for lot in expired:
                highest_bidder_id = lot.get("highest_bidder_id")
                if highest_bidder_id:
                    await db.execute(
                        "INSERT INTO inventory (user_id, item_type, item_name, item_value) VALUES (?, ?, ?, ?)",
                        (int(highest_bidder_id), lot["item_type"], lot["item_name"], int(lot["item_value"])),
                    )
                    notifications.append(
                        (
                            int(highest_bidder_id),
                            f"🏛 Вы успешно купили на аукционе предмет «{lot['item_name']}» "
                            f"со ставкой {format_number(int(lot['current_bid']))}$.\n"
                            "🎒 Чтобы посмотреть предмет, пропишите /инв в любом чате с ботом.",
                        )
                    )
                    seller_bal = balances_data.get(str(lot["seller_id"])) or get_balance(int(lot["seller_id"]))
                    seller_bal["wallet"] = seller_bal.get("wallet", 0) + int(lot["current_bid"])
                    balances_data[str(lot["seller_id"])] = seller_bal
                    economy_logs.append(
                        (
                            int(lot["seller_id"]),
                            int(highest_bidder_id),
                            int(lot["current_bid"]),
                            f"получил(-а) {int(lot['current_bid'])}$ за продажу предмета «{lot['item_name']}» на аукционе",
                        )
                    )
                    economy_logs.append(
                        (
                            int(highest_bidder_id),
                            int(lot["seller_id"]),
                            int(lot["current_bid"]),
                            f"купил(-а) на аукционе предмет «{lot['item_name']}» за {int(lot['current_bid'])}$",
                        )
                    )
                else:
                    await db.execute(
                        "INSERT INTO inventory (user_id, item_type, item_name, item_value) VALUES (?, ?, ?, ?)",
                        (int(lot["seller_id"]), lot["item_type"], lot["item_name"], int(lot["item_value"])),
                    )
                await db.execute("DELETE FROM auction_items WHERE id = ?", (int(lot["id"]),))

            await db.commit()
        finally:
            await db.close()

    balances.update(balances_data)
    save_data(BALANCES_FILE, balances)
    _clear_balance_cache()

    for peer_id, message_text in notifications:
        try:
            await bot.api.messages.send(peer_id=peer_id, random_id=0, message=message_text)
        except Exception as notify_error:
            print(f"[AUCTION WINNER DM ERROR] {notify_error}")

    for log_user_id, log_target_id, log_amount, log_text in economy_logs:
        await log_economy(
            user_id=log_user_id,
            target_id=log_target_id,
            amount=log_amount,
            log=log_text,
        )
    return len(expired)


def format_vk_link(user_id: int, name: str) -> str:
    safe_name = str(name).replace("|", " ")
    return f"[https://vk.com/id{user_id}|{safe_name}]"


async def collect_all_business_income(user_id: int):
    businesses = await get_user_businesses(user_id)
    total_income = 0
    collected = 0
    errors = []
    for biz in businesses:
        ok, msg, amount = await collect_income(user_id, int(biz["id"]))
        if ok:
            total_income += int(amount)
            collected += 1
        else:
            errors.append(msg)
    return collected, total_income, errors


def _get_active_duel_for_chat(peer_id: int | str):
    duel = duels.get(str(peer_id))
    if isinstance(duel, dict) and duel.get("author") and duel.get("stake"):
        return duel
    return None


async def _cancel_duel_if_unanswered(peer_id: str, delay_seconds: int = 60):
    await asyncio.sleep(delay_seconds)
    duel = duels.get(peer_id)
    if not duel or duel.get("accepted"):
        return
    message_id = duel.get("message_id")
    try:
        if message_id:
            await delete_message(groupid, int(peer_id), int(message_id))
    except Exception:
        pass
    duels.pop(peer_id, None)
    save_data(DUELS_FILE, duels)


async def sync_user_business_income(user_id: int):
    businesses = await get_user_businesses(user_id)
    synced = 0
    total_income = 0
    now_iso = datetime.now().isoformat()
    with database:
        for biz in businesses:
            if get_business_collect_seconds_left(biz) > 0:
                continue
            products = int(biz.get("products", 0))
            products_to_spend = 5 if products >= 5 else 0
            daily_income = _business_income_per_day(biz)
            if products_to_spend >= 5 and daily_income > 0:
                sql.execute(
                    "UPDATE businesses SET products = products - ?, branch_balance = branch_balance + ?, last_collected_at = ? WHERE id = ?",
                    (products_to_spend, int(daily_income), now_iso, int(biz["id"])),
                )
                synced += 1
                total_income += int(daily_income)
            else:
                sql.execute(
                    "UPDATE businesses SET last_collected_at = ? WHERE id = ?",
                    (now_iso, int(biz["id"])),
                )
    return synced, total_income


def _format_business_collect_cooldown(branch: dict) -> str:
    seconds_left = get_business_collect_seconds_left(branch)
    if seconds_left <= 0:
        return "доступен сейчас"
    hours = seconds_left // 3600
    minutes = (seconds_left % 3600) // 60
    return f"через {hours}ч. {minutes}м."


async def _build_inventory_page(user_id: int, page: int = 1):
    items = await get_inventory(user_id)
    per_page = 12
    total_pages = max(1, (len(items) + per_page - 1) // per_page)
    page = min(max(1, page), total_pages)
    start = (page - 1) * per_page
    page_items = items[start:start + per_page]

    kb = Keyboard(inline=True)
    if total_pages > 1:
        if page > 1:
            kb.add(Callback("⬅️ Назад", {"command": "inventory_page", "owner_id": user_id, "page": page - 1}), color=KeyboardButtonColor.SECONDARY)
        if page < total_pages:
            kb.add(Callback("➡️ Вперед", {"command": "inventory_page", "owner_id": user_id, "page": page + 1}), color=KeyboardButtonColor.SECONDARY)

    lines = [f"🎒 Инвентарь [{page}/{total_pages}]", ""]
    for item in page_items:
        value = int(item.get("item_value", 0))
        suffix = f" | бонус: +{value}%" if value > 0 else ""
        lines.append(f"• ID {item['id']} — {item['item_name']}{suffix}")
    lines.append("")
    lines.append("♻️ Распылить: /распылить [ID предмета]")
    lines.append("✨ Применить: /применить [ID предмета]")
    return items, kb, "\n".join(lines)


async def _build_auction_page(chat_id: int, page: int = 1):
    await finalize_expired_auctions()
    async with aiosqlite.connect("database.db", timeout=30) as db:
        await _configure_async_db(db)
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, item_name, current_bid, seller_id, highest_bidder_id, created_at, ends_at "
            "FROM auction_items ORDER BY current_bid DESC, id ASC"
        )
        lots = [dict(row) for row in await cur.fetchall()]

    per_page = 8
    total_pages = max(1, (len(lots) + per_page - 1) // per_page)
    page = min(max(1, page), total_pages)
    start = (page - 1) * per_page
    page_lots = lots[start:start + per_page]

    kb = Keyboard(inline=True)
    if total_pages > 1:
        if page > 1:
            kb.add(Callback("⬅️ Назад", {"command": "auction_page", "page": page - 1}), color=KeyboardButtonColor.SECONDARY)
        if page < total_pages:
            kb.add(Callback("➡️ Вперед", {"command": "auction_page", "page": page + 1}), color=KeyboardButtonColor.SECONDARY)

    lines = [
        f"🏛 Аукцион [{page}/{total_pages}]",
        f"📦 Активных лотов: {len(lots)}",
        "",
    ]
    for index, lot in enumerate(page_lots, start=start + 1):
        try:
            seller_name = await get_user_name(int(lot["seller_id"]), chat_id)
        except Exception:
            seller_name = str(lot["seller_id"])
        leader_text = "Нет ставок"
        if lot.get("highest_bidder_id"):
            try:
                leader_name = await get_user_name(int(lot["highest_bidder_id"]), chat_id)
            except Exception:
                leader_name = str(lot["highest_bidder_id"])
            leader_text = leader_name
        lines.append(
            f"┏ Лот #{lot['id']}\n"
            f"🎁 {lot['item_name']}\n"
            f"💰 Ставка: {format_number(int(lot['current_bid']))}$\n"
            f"👤 Продавец: {seller_name}\n"
            f"🏁 Лидер: {leader_text}\n"
            f"⏳ Осталось: {_lot_time_left_text(lot)}\n"
            f"┗ Ставка: /купаук {lot['id']} [сумма]"
        )
        if index != start + len(page_lots) - 1:
            lines.append("")
    return lots, kb, "\n".join(lines)


async def withdraw_all_business_balance(user_id: int):
    businesses = await get_user_businesses(user_id)
    total = 0
    changed = 0
    for biz in businesses:
        branch_balance = int(biz.get("branch_balance", 0))
        if branch_balance > 0:
            total += branch_balance
            changed += 1
    if total <= 0:
        return 0, 0
    with database:
        for biz in businesses:
            if int(biz.get("branch_balance", 0)) > 0:
                sql.execute("UPDATE businesses SET branch_balance = 0 WHERE id = ?", (int(biz["id"]),))
    return changed, total


def clear_table_daily():
    try:
        sql.execute("DELETE FROM messages_today")
    except Exception:
        pass
    for uid in list(balances.keys()):
        if isinstance(balances[uid], dict):
            balances[uid]["business_income_today"] = 0
    save_data(BALANCES_FILE, balances)


async def build_cases_menu(user_id: int):
    bal = _cached_user_balance(user_id)
    remaining = await get_daily_remaining(user_id)
    kb = Keyboard(inline=True)
    user_cases = await get_user_cases(user_id)
    lines = [
        "🎁 Кейсы Banana Manager",
        "",
        f"📦 На складе неоткрытых кейсов: {len(user_cases)}",
        "",
    ]

    if remaining is None:
        kb.add(
            Callback("Ежедневный кейс", {"command": "open_case", "case_type": "daily", "owner_id": user_id}),
            color=KeyboardButtonColor.SECONDARY,
        ).row()
        lines.append("🆓 Ежедневный кейс — бесплатно")
    else:
        lines.append(f"⏳ Ежедневный кейс — снова доступен через {_daily_remaining_text(remaining)}")

    kb.add(
        Callback("Кейс бомжа", {"command": "buy_case", "case_type": "homeless", "owner_id": user_id}),
        color=KeyboardButtonColor.PRIMARY,
    ).row()
    lines.append(f"💸 Кейс Бомжа — {format_number(CASE_DEFS['homeless']['money_cost'])}$")

    kb.add(
        Callback("Стандартный кейс", {"command": "buy_case", "case_type": "standard", "owner_id": user_id}),
        color=KeyboardButtonColor.PRIMARY,
    ).row()
    lines.append(f"🎟 Стандартный кейс — {format_number(CASE_DEFS['standard']['money_cost'])}$")

    kb.add(
        Callback("Особый кейс", {"command": "buy_case", "case_type": "special", "owner_id": user_id}),
        color=KeyboardButtonColor.POSITIVE,
    ).row()
    lines.append(f"🍌 Особый кейс — {CASE_DEFS['special']['banana_cost']} бананов")

    kb.add(Callback("📦 Мои кейсы", {"command": "my_cases", "owner_id": user_id}), color=KeyboardButtonColor.SECONDARY)
    kb.add(Callback("🎲 Шансы", {"command": "case_chances", "owner_id": user_id}), color=KeyboardButtonColor.SECONDARY)

    return kb, "\n".join(lines)


async def answer_callback_event(event_message, text: str = "Готово"):
    try:
        await bot.api.messages.send_message_event_answer(
            event_id=event_message.object.event_id,
            peer_id=event_message.object.peer_id,
            user_id=event_message.object.user_id,
            event_data=json.dumps({"type": "show_snackbar", "text": text}),
        )
    except Exception:
        pass


def _callback_owner_allowed(payload: dict, user_id: int) -> bool:
    owner_id = int(payload.get("owner_id", 0) or 0)
    return owner_id == 0 or owner_id == user_id


async def upload_message_photo(peer_id: int, file_path: str) -> Optional[str]:
    if file_path and not os.path.isabs(file_path):
        file_path = os.path.join(os.getcwd(), file_path)
    if not file_path or not os.path.exists(file_path):
        return None
    try:
        upload = await bot.api.photos.get_messages_upload_server(peer_id=peer_id)
        upload_url = upload.upload_url if hasattr(upload, "upload_url") else upload["upload_url"]
        data = aiohttp.FormData()
        with open(file_path, "rb") as photo_file:
            data.add_field("photo", photo_file, filename=os.path.basename(file_path), content_type="image/jpeg")
            async with aiohttp.ClientSession() as session:
                async with session.post(upload_url, data=data) as resp:
                    uploaded = await resp.json()
        saved = await bot.api.photos.save_messages_photo(
            photo=uploaded["photo"],
            server=uploaded["server"],
            hash=uploaded["hash"],
        )
        if saved:
            photo = saved[0]
            return f"photo{photo.owner_id}_{photo.id}"
    except Exception as e:
        log.exception("Ошибка загрузки фото в сообщение: %s", e)
    return None

def extract_user_id(message: Message):
    # Если ответом на сообщение
    if message.reply_message:
        return message.reply_message.from_id
    elif message.fwd_messages:
        return message.fwd_messages[0].from_id

    text = message.text or ""
    m = re.search(r"\[id(\d+)\|", text)
    if m:
        return int(m.group(1))
    m = re.search(r"(?:@id|id)(\d+)", text)
    if m:
        return int(m.group(1))
    m = re.search(r"vk\.com/id(\d+)", text)
    if m:
        return int(m.group(1))
    return None

# ================== LOCALIZATION ==================
class Localization:
    def __init__(self, path: str):
        self.data = {}
        try:
            with open(path, encoding="utf-8") as f:
                self.data = yaml.safe_load(f)
        except FileNotFoundError:
            print(f"Localization file {path} not found!")

    def get(self, key: str, **kwargs) -> str:
        parts = key.split(".")
        value = self.data
        try:
            for part in parts:
                value = value[part]
        except (KeyError, TypeError):
            return f"No translation ({key})"  # <-- оставляем
        # Подставляем переменные $(var)
        def repl(match):
            var_name = match.group(1)
            return str(kwargs.get(var_name, f"$({var_name})"))
        return re.sub(r"\$\((\w+)\)", repl, value)     

# Создаём объект локализации
loc = Localization("localization.yml")

# Monkey patch метода replyLocalizedMessage для Message
async def replyLocalizedMessage(self, key: str, variables: dict = None, keyboard=None):
    text = loc.get(key, **(variables or {}))
    # Если текст вернул fallback "No translation", тоже отвечаем сообщением
    if text.startswith("No translation"):
        await self.reply(text, keyboard=keyboard)
        return
    await self.reply(text, keyboard=keyboard)

Message.replyLocalizedMessage = replyLocalizedMessage

# ====== UTILITIES ======
def extract_user_id_from_text(text: str) -> Optional[int]:
    if not text:
        return None
    m = re.search(r"\[id(\d+)\|", text)
    if m:
        return int(m.group(1))
    m = re.search(r"(?:@id|id)(\d+)", text)
    if m:
        return int(m.group(1))
    m = re.search(r"vk(?:\.com|\.ru)/id(\d+)", text)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(\d{4,})\b", text)
    if m:
        return int(m.group(1))
    return None
    
async def extract_user_id(message: Message) -> Optional[int]:
    # reply
    if getattr(message, "reply_message", None):
        return message.reply_message.from_id
    # forwarded
    if getattr(message, "fwd_messages", None):
        if len(message.fwd_messages) > 0:
            return message.fwd_messages[0].from_id
    # parse text
    text = message.text or ""
    uid = extract_user_id_from_text(text)
    if uid:
        return uid
    return None

# Проверка логики
async def get_logic(number):
    # Если number None или меньше 1 — возвращаем False
    if not number or number < 1:
        return False
    return True

# Проверка выхода/отключения чата
async def check_quit(chat_id=int):
    sql.execute(f"SELECT silence FROM chats WHERE chat_id = {chat_id}")
    fetch = sql.fetchone()
    if not fetch:
        return False
    # Передаём безопасно в get_logic
    return await get_logic(fetch[0])

async def getID(arg: str):
    arg_split = arg.split("|")

    if arg_split[0] == arg:
        try:
            # --- Проверка на vk.com, vk.me, vk.ru ---
            if any(domain in arg for domain in ["vk.com/", "vk.me/", "vk.ru/"]):
                clean_arg = (
                    arg.replace("https://", "")
                    .replace("http://", "")
                    .replace("www.", "")
                )

                for domain in ["vk.com/", "vk.me/", "vk.ru/"]:
                    if domain in clean_arg:
                        clean_arg = clean_arg.split(domain)[1]
                        break

                scr_split = await bot.api.utils.resolve_screen_name(clean_arg)
                x = json.loads(scr_split.json())
                return int(x["object_id"])
        except:
            pass

        # --- Если передан vk.com/idXXX ---
        com_split = arg.split("vk.com/id")
        try:
            if com_split[1].isnumeric():
                return com_split[1]
            else:
                return False
        except:
            # --- Если просто vk.com/username ---
            for domain in ["vk.com/", "vk.me/", "vk.ru/"]:
                if domain in arg:
                    try:
                        screen_split = arg.split(domain)
                        scr_split = await bot.api.utils.resolve_screen_name(screen_split[1])
                        ut_split = str(scr_split).split(" ")
                        obj_split = ut_split[1].split("_id=")
                        if not obj_split[1].isnumeric():
                            return False
                        return obj_split[1]
                    except:
                        return False

    try:
        id_split = arg_split[0].split("id")
        return int(id_split[1])
    except:
        return False        

async def get_registration_date(user_id=int):
    vk_link = f"http://vk.com/foaf.php?id={user_id}"
    with urllib.request.urlopen(vk_link) as response:
        vk_xml = response.read().decode("windows-1251")

    parsed_xml = re.findall(r'created dc:date="(.*)"', vk_xml)
    for item in parsed_xml:
        sp_i = item.split('+')
        str = sp_i[0]  # строка с вашей датой

        PATTERN_IN1 = "%Y-%m-%dT%H:%M:%S"  # формат вашей даты
        PATTERN_OUT1 = "%B"  # формат даты, который вам нужен на выходе

        date1 = datetime.strptime(str, PATTERN_IN1)
        cp_date1 = datetime.strftime(date1, PATTERN_OUT1)

        locales = {"November": "ноября", "October": "октября", "September": "сентября", "August": "августа",
                   "July": "июля", "June": "июня", "May": "мая", "April": "апреля", "March": "марта",
                   "February": "февраля", "January": "января", "December": "декабря"}
        m = locales.get(cp_date1)

        PATTERN_IN = "%Y-%m-%dT%H:%M:%S"  # формат вашей даты
        PATTERN_OUT = f"%d-ого {m} 20%yг"  # формат даты, который вам нужен на выходе

        date = datetime.strptime(str, PATTERN_IN)
        cp_date = datetime.strftime(date, PATTERN_OUT)

    return cp_date

async def get_string(text=[], arg=int):
    data_string = []
    for i in range(len(text)):
        if i < arg: pass
        else: data_string.append(text[i])
    return_string = " ".join(data_string)
    if return_string == "": return False
    else: return return_string

database = sqlite3.connect('database.db', timeout=30, check_same_thread=False)
sql = database.cursor()
sql.execute("PRAGMA journal_mode=WAL")
sql.execute("PRAGMA synchronous=NORMAL")
sql.execute("PRAGMA busy_timeout=30000")
database.commit()
async def check_chat(chat_id=int):
    sql.execute(f"SELECT * FROM chats WHERE chat_id = {chat_id}")
    if sql.fetchone() == None: return False
    else: return True
    
sql.execute("""
CREATE TABLE IF NOT EXISTS gbanlist (
    user_id BIGINT NOT NULL,
    moderator_id BIGINT NOT NULL,
    reason_gban TEXT NOT NULL,
    datetime_globalban TEXT NOT NULL
)
""")
database.commit()

# Таблица для списка глобальных связок
sql.execute("""
CREATE TABLE IF NOT EXISTS gsync_list (
    owner_id INTEGER,
    table_name TEXT
)
""")
database.commit()

sql.execute("""
CREATE TABLE IF NOT EXISTS promocodes (
    code TEXT PRIMARY KEY,
    type TEXT,
    value INTEGER,
    creator_id INTEGER,
    uses_left INTEGER
)
""")
database.commit()

sql.execute("""
CREATE TABLE IF NOT EXISTS promoused (
    user_id INTEGER,
    code TEXT
)
""")
database.commit()

sql.execute("""
CREATE TABLE IF NOT EXISTS tech_chat_settings (
    chat_id BIGINT PRIMARY KEY,
    enabled BIGINT DEFAULT 0
)
""")
database.commit()

sql.execute("""
CREATE TABLE IF NOT EXISTS tech_permissions (
    chat_id BIGINT,
    user_id BIGINT,
    level BIGINT,
    UNIQUE(chat_id, user_id)
)
""")
database.commit()

sql.execute("""
CREATE TABLE IF NOT EXISTS globalban (
    user_id BIGINT NOT NULL,
    moderator_id BIGINT NOT NULL,
    reason_gban TEXT NOT NULL,
    datetime_globalban TEXT NOT NULL
)
""")
database.commit()

sql.execute("""CREATE TABLE IF NOT EXISTS rules (
    chat_id INTEGER PRIMARY KEY,
    description TEXT
)""")
database.commit()

sql.execute("""CREATE TABLE IF NOT EXISTS info (
    chat_id INTEGER PRIMARY KEY,
    description TEXT
)""")
database.commit()

sql.execute("""CREATE TABLE IF NOT EXISTS antisliv (
    chat_id INTEGER PRIMARY KEY,
    mode INTEGER DEFAULT 0
)""")
database.commit()

sql.execute("""
CREATE TABLE IF NOT EXISTS blacklist (
    user_id BIGINT NOT NULL,
    moderator_id BIGINT NOT NULL,
    reason_gban TEXT NOT NULL,
    datetime_globalban TEXT NOT NULL
)
""")
database.commit()

sql.execute("""
CREATE TABLE IF NOT EXISTS protection (
    chat_id BIGINT NOT NULL PRIMARY KEY,
    mode INT NOT NULL
);
""")

database.commit()

sql.execute("""
CREATE TABLE IF NOT EXISTS mutesettings (
    chat_id BIGINT NOT NULL PRIMARY KEY,
    mode INT NOT NULL
);
""")

database.commit()

# Создание таблицы economy, если не существует
sql.execute("""
CREATE TABLE IF NOT EXISTS economy (
    user_id INTEGER,
    target_id INTEGER,
    amount INTEGER,
    log TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")
database.commit()
try:
    sql.execute("ALTER TABLE economy ADD COLUMN created_at TEXT DEFAULT CURRENT_TIMESTAMP")
    database.commit()
except Exception:
    pass

# Создание таблицы logchats, если не существует
sql.execute("""
CREATE TABLE IF NOT EXISTS logchats (
    user_id INTEGER,
    target_id INTEGER,
    role INTEGER,
    log TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")
database.commit()
try:
    sql.execute("ALTER TABLE logchats ADD COLUMN created_at TEXT DEFAULT CURRENT_TIMESTAMP")
    database.commit()
except Exception:
    pass

sql.execute("""
CREATE TABLE IF NOT EXISTS banschats (
    chat_id INTEGER PRIMARY KEY
)
""")
database.commit()

sql.execute("""
CREATE TABLE IF NOT EXISTS bugsusers (
    user_id INTEGER,
    bug TEXT,
    datetime TEXT,
    bug_counts_user INTEGER
)
""")
database.commit()

# Таблица с регистрацией серверов
sql.execute("""
CREATE TABLE IF NOT EXISTS servers_list (
    owner_id INTEGER,
    server_number TEXT,
    table_name TEXT
)
""")
database.commit()

sql.execute("""
CREATE TABLE IF NOT EXISTS server_links(
    server_id INTEGER,
    chat_id INTEGER,
    chat_title TEXT
)
""")
database.commit()

sql.execute("""
CREATE TABLE IF NOT EXISTS gamesettings (
    chat_id BIGINT NOT NULL PRIMARY KEY,
    mode INT NOT NULL
);
""")

database.commit()

sql.execute("""
CREATE TABLE IF NOT EXISTS photosettings (
    chat_id BIGINT NOT NULL PRIMARY KEY,
    mode INT NOT NULL
);
""")

database.commit()

try:
    # Проверяем, есть ли старая таблица с неправильными колонками
    sql.execute("PRAGMA table_info(ban_words)")
    columns = [col[1] for col in sql.fetchall()]

    # Если нужных колонок нет — пересоздаём таблицу
    if "word" not in columns or "creator_id" not in columns or "time" not in columns:
        print("[INIT] Пересоздание таблицы ban_words...")
        sql.execute("DROP TABLE IF EXISTS ban_words")
        sql.execute("""
        CREATE TABLE IF NOT EXISTS ban_words (
            word TEXT NOT NULL,
            creator_id INTEGER NOT NULL,
            time TEXT NOT NULL
        )
        """)
        database.commit()
        print("[INIT] Таблица ban_words успешно пересоздана.")
except Exception as e:
    print(f"[INIT] Ошибка при проверке таблицы ban_words: {e}")    

async def new_chat(chat_id: int, peer_id: int, owner_id: int, chat_type: str = "def"):
    # Проверяем, какие колонки реально есть
    sql.execute("PRAGMA table_info(chats)")
    columns = [col[1] for col in sql.fetchall()]

    # Формируем список колонок и значений для INSERT
    insert_columns = ["chat_id", "peer_id", "owner_id"]
    insert_values = [chat_id, peer_id, owner_id]

    if "welcome_msg" in columns:
        insert_columns.append("welcome_msg")
        insert_values.append("Добро пожаловать, уважаемый %i пользователь!")

    if "type" in columns:
        insert_columns.append("type")
        insert_values.append(chat_type)

    sql.execute(f"INSERT INTO chats ({', '.join(insert_columns)}) VALUES ({', '.join(['?']*len(insert_values))})", insert_values)

    # Создаём остальные таблицы для чата
    sql.execute(f"CREATE TABLE IF NOT EXISTS permissions_{chat_id} (user_id BIGINT, level BIGINT);")
    sql.execute(f"CREATE TABLE IF NOT EXISTS nicks_{chat_id} (user_id BIGINT, nick TEXT);")
    sql.execute(f"CREATE TABLE IF NOT EXISTS banwords_{chat_id} (banword TEXT);")
    sql.execute(f"CREATE TABLE IF NOT EXISTS warns_{chat_id} (user_id BIGINT, count BIGINT, moder BIGINT, reason TEXT, date BIGINT, date_string TEXT);")
    sql.execute(f"CREATE TABLE IF NOT EXISTS mutes_{chat_id} (user_id BIGINT, moder TEXT, reason TEXT, date BIGINT, date_string TEXT, time BIGINT);")
    sql.execute(f"CREATE TABLE IF NOT EXISTS mutelogs_{chat_id} (user_id BIGINT, moder_id BIGINT, reason TEXT, date BIGINT, date_string TEXT, mute_time BIGINT, status TEXT);")
    sql.execute(f"CREATE TABLE IF NOT EXISTS bans_{chat_id} (user_id BIGINT, moder BIGINT, reason TEXT, date BIGINT, date_string TEXT);")
    sql.execute(f"CREATE TABLE IF NOT EXISTS messages_{chat_id} (user_id BIGINT, date BIGINT, date_string TEXT, message_id BIGINT, cmid BIGINT);")
    sql.execute(f"CREATE TABLE IF NOT EXISTS warnhistory_{chat_id} (user_id BIGINT, count BIGINT, moder BIGINT, reason TEXT, date BIGINT, date_string TEXT);")
    sql.execute(f"CREATE TABLE IF NOT EXISTS punishments_{chat_id} (user_id BIGINT, date TEXT);")

    database.commit()
      
async def get_role(user_id: int, chat_id: int) -> int:
    """Возвращает числовой уровень роли пользователя. Чем выше число, тем выше роль.
    0  - обычный пользователь
    1  - модератор
    2  - старший модератор
    3  - админ
    4  - старший админ
    5  - зам. спецадмина
    6  - спецадмин
    7  - владелец чата
    8+ - глобальные роли (ЗР=8,ОЗР=9,СР=10,РБ=11)
    """
    try:
        sql.execute(f"SELECT level FROM global_managers WHERE user_id = {user_id}")
        fetch = sql.fetchone()
        if fetch:
            if fetch[0] == 2: return 8  # ЗР
            if fetch[0] == 4: return 9 # ОЗР
            if fetch[0] == 6: return 10 # СР
            if fetch[0] == 7: return 11 # РБ

        # Локальные роли
        sql.execute(f"SELECT owner_id FROM chats WHERE chat_id = {chat_id}")
        chat_owner = sql.fetchone()
        if chat_owner and chat_owner[0] == user_id:
            return 7

        sql.execute(f"SELECT level FROM permissions_{chat_id} WHERE user_id = {user_id}")
        fetch = sql.fetchone()
        if fetch:
            return fetch[0]
        
    except Exception as e:
        print(f"Ошибка при получении роли для user_id={user_id}, chat_id={chat_id}: {e}")
    
    return 0  # роль по умолчанию


async def is_tech_chat(chat_id: int) -> bool:
    sql.execute("SELECT enabled FROM tech_chat_settings WHERE chat_id = ?", (chat_id,))
    row = sql.fetchone()
    return bool(row and int(row[0]) == 1)


async def set_tech_chat(chat_id: int, enabled: int = 1):
    sql.execute(
        "INSERT INTO tech_chat_settings (chat_id, enabled) VALUES (?, ?) "
        "ON CONFLICT(chat_id) DO UPDATE SET enabled = excluded.enabled",
        (chat_id, int(enabled)),
    )
    database.commit()


async def get_tech_role(user_id: int, chat_id: int) -> int:
    sql.execute("SELECT level FROM tech_permissions WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
    row = sql.fetchone()
    return int(row[0]) if row else 0


async def set_tech_role(user_id: int, chat_id: int, level: int):
    if int(level) <= 0:
        sql.execute("DELETE FROM tech_permissions WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
    else:
        sql.execute(
            "INSERT INTO tech_permissions (chat_id, user_id, level) VALUES (?, ?, ?) "
            "ON CONFLICT(chat_id, user_id) DO UPDATE SET level = excluded.level",
            (chat_id, user_id, int(level)),
        )
    database.commit()


async def get_tech_staff(chat_id: int):
    sql.execute("SELECT user_id, level FROM tech_permissions WHERE chat_id = ? ORDER BY level DESC, user_id ASC", (chat_id,))
    rows = sql.fetchall()
    result = {level: [] for level in TECH_ROLE_NAMES.keys()}
    for user_id, level in rows:
        if int(level) in result:
            result[int(level)].append(format_vk_link(user_id, await get_user_name(user_id, chat_id)))
    return result


async def check_target_permission(initiator_id: int, target_id: int, chat_id: int) -> bool:
    """Проверяет, может ли инициатор применить команду к цели.
    
    Возвращает True, если роль инициатора строго выше роли цели.
    Возвращает False, если роли равны или роль цели выше.
    """
    initiator_role = await get_role(initiator_id, chat_id)
    target_role = await get_role(target_id, chat_id)
    
    return initiator_role > target_role

async def get_warns(user_id=int, chat_id=int):
    sql.execute(f"SELECT count FROM warns_{chat_id} WHERE user_id = {user_id}")
    fetch = sql.fetchone()
    if fetch == None: return 0
    else: return fetch[0]

def paginate_list(items, page, per_page=20):
    page = max(1, int(page or 1))
    start = (page - 1) * per_page
    end = start + per_page
    return items[start:end], (len(items) + per_page - 1) // per_page

def make_nav_keyboard(base_cmd, page, chat_context_id):
    kb = Keyboard(inline=True)
    prev_payload = {"command": f"{base_cmd}minus", "page": 1, "chatId": chat_context_id}
    next_payload = {"command": f"{base_cmd}plus", "page": 1, "chatId": chat_context_id}
    kb.add(Callback("⏪", prev_payload), color=KeyboardButtonColor.NEGATIVE)
    kb.add(Callback("⏩", next_payload), color=KeyboardButtonColor.POSITIVE)
    return kb

# === Проверка, к какой связке принадлежит чат ===
async def get_gsync_chats(chat_id):
    sql.execute("SELECT owner_id, table_name FROM gsync_list")
    gsyncs = sql.fetchall()

    for owner_id, table_name in gsyncs:
        try:
            sql.execute(f"SELECT chat_id FROM {table_name} WHERE chat_id = ?", (chat_id,))
            if sql.fetchone():
                sql.execute(f"SELECT chat_id FROM {table_name}")
                chats = sql.fetchall()
                return [c[0] for c in chats]
        except:
            continue
    return None

# === Получение связки по чату (для info) ===
async def get_gsync_table(chat_id):
    sql.execute("SELECT owner_id, table_name FROM gsync_list")
    gsyncs = sql.fetchall()

    for owner_id, table_name in gsyncs:
        try:
            sql.execute(f"SELECT chat_id FROM {table_name} WHERE chat_id = ?", (chat_id,))
            if sql.fetchone():
                return {"owner": owner_id, "table": table_name}
        except:
            continue
    return None    

async def get_user_name(user_id: int, chat_id: int | None = None) -> str:
    # Сначала проверяем ник в базе, только если chat_id задан
    if chat_id is not None:
        try:
            sql.execute(f"SELECT nick FROM nicks_{chat_id} WHERE user_id = ?", (user_id,))
            fetch = sql.fetchone()
            if fetch and fetch[0]:
                return fetch[0]
        except:
            pass  # На случай, если таблицы нет

    # Если ника нет или chat_id не задан, пытаемся получить имя и фамилию через API
    try:
        info = await bot.api.users.get(user_ids=user_id)
        if info and len(info) > 0:
            return f"{info[0].first_name} {info[0].last_name}"
    except:
        pass

    # Если ничего не получилось, возвращаем ID
    return str(user_id)
    
# Функция очистки варнов
async def clear_all_warns(chat_id: int) -> int:
    # Проверяем, есть ли записи
    sql.execute(f"SELECT DISTINCT user_id FROM warns_{chat_id}")
    users = sql.fetchall()

    if not users:
        return 0  # ничего нет

    count = len(users)

    # Удаляем все варны
    sql.execute(f"DELETE FROM warns_{chat_id}")
    database.commit()

    return count


async def messageslist(user_id=None, chat_id=None):
    if user_id is not None and chat_id is not None:
        sql.execute("SELECT * FROM messages_today WHERE user_id = ? AND chat_id = ?", (user_id, chat_id))
    elif user_id is not None:
        sql.execute("SELECT * FROM messages_today WHERE user_id = ?", (user_id,))
    elif chat_id is not None:
        sql.execute("SELECT * FROM messages_today WHERE chat_id = ?", (chat_id,))
    else:
        sql.execute("SELECT * FROM messages_today")

    fetch = sql.fetchall()
    messages = []
    for _row in fetch:
        messages.append("None")

    return messages
    
async def is_nick(user_id=int, chat_id=int):
    sql.execute(f"SELECT nick FROM nicks_{chat_id} WHERE user_id = {user_id}")
    if sql.fetchone() == None: return False
    else: return True

async def setnick(user_id=int, chat_id=int, nick=str):
    sql.execute(f"SELECT nick FROM nicks_{chat_id} WHERE user_id = {user_id}")
    if sql.fetchone() == None:
        sql.execute(f"INSERT INTO nicks_{chat_id} VALUES (?, ?)", (user_id, nick))
        database.commit()
    else:
        sql.execute(f"UPDATE nicks_{chat_id} SET nick = ? WHERE user_id = ?", (nick, user_id))
        database.commit()

async def rnick(user_id=int, chat_id=int):
    sql.execute(f"DELETE FROM nicks_{chat_id} WHERE user_id = {user_id}")
    database.commit()

async def get_acc(chat_id=int, nick=str):
    normalized_nick = str(nick or "").strip().lower()
    sql.execute(
        f"SELECT user_id FROM nicks_{chat_id} WHERE LOWER(TRIM(nick)) = ?",
        (normalized_nick,),
    )
    fetch = sql.fetchone()
    if fetch == None: return False
    else: return fetch[0]

async def get_nick(user_id=int, chat_id=int):
    sql.execute(f"SELECT nick FROM nicks_{chat_id} WHERE user_id = {user_id}")
    fetch = sql.fetchone()
    if fetch == None: return False
    else: return fetch[0]


def _sqlite_write_sync(query: str, params: tuple):
    conn = sqlite3.connect("database.db", timeout=30, check_same_thread=False)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.execute(query, params)
        conn.commit()
    finally:
        conn.close()


async def _sqlite_write_with_retry(query: str, params: tuple, retries: int = 6, delay: float = 0.25):
    last_error = None
    for attempt in range(retries):
        try:
            await asyncio.to_thread(_sqlite_write_sync, query, params)
            return
        except sqlite3.OperationalError as e:
            last_error = e
            if "locked" not in str(e).lower() or attempt == retries - 1:
                raise
            await asyncio.sleep(delay * (attempt + 1))
    if last_error:
        raise last_error

async def log_economy(user_id=None, target_id=None, amount=None, log=None):
    try:
        await _sqlite_write_with_retry(
            "INSERT INTO economy (user_id, target_id, amount, log, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, target_id, amount, log, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        print(f"[ECONOMY LOG] {user_id} -> {target_id} | {amount} | {log}")
    except Exception as e:
        print(f"[ECONOMY LOG ERROR] {e}")       
        
async def chats_log(user_id=None, target_id=None, role=None, log=None):
    try:
        await _sqlite_write_with_retry(
            "INSERT INTO logchats (user_id, target_id, role, log, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, target_id, role, log, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        print(f"[CHATS LOG] {user_id} -> {target_id} | {role} | {log}")
    except Exception as e:
        print(f"[CHATS LOG ERROR] {e}")                     

async def nlist(chat_id: int, page: int):
    sql.execute(f"SELECT * FROM nicks_{chat_id}")
    fetch = sql.fetchall()
    if not fetch:
        return []

    nicks = []
    gi = 0
    with open("config.json", "r") as json_file:
        open_file = json.load(json_file)
    max_nicks = open_file.get('nicks_max', 20)

    start = (page - 1) * max_nicks
    end = page * max_nicks

    for i in fetch:
        if gi < start:
            gi += 1
            continue
        if gi >= end:
            break

        info = await bot.api.users.get(user_ids=i[0])
        if info and len(info) > 0:
            name = f"{info[0].first_name} {info[0].last_name}"
        else:
            name = "Ошибка"

        nicks.append(f"{gi+1}. @id{i[0]} ({name}) -- {i[1]}")
        gi += 1

    return nicks 

async def nonick(chat_id=int, page=int):
    sql.execute(f"SELECT * FROM nicks_{chat_id}")
    fetch = sql.fetchall()
    nicks = []
    for i in fetch:
        nicks.append(i[0])

    gi = 0
    nonick = []
    with open("config.json", "r") as json_file:
        open_file = json.load(json_file)
    max_nonick = open_file['nonick_max']
    users = await bot.api.messages.get_conversation_members(peer_id=2000000000+chat_id)
    users = json.loads(users.json())
    for i in users["profiles"]:
        if not i['id'] in nicks:
            gi = gi + 1
            if page*max_nonick >= gi and page*max_nonick-max_nonick < gi:
                nonick.append(f"{gi}) @id{i['id']} ({i['first_name']} {i['last_name']})")

    return nonick

async def warn(chat_id=int, user_id=int, moder=int, reason=str):
    actualy_warns = await get_warns(user_id, chat_id)
    date = time.time()
    cd = str(datetime.now()).split('.')
    date_string = cd[0]
    sql.execute(f"INSERT INTO warnhistory_{chat_id} VALUES (?, {actualy_warns+1}, ?, ?, {date}, '{date_string}')",(user_id, moder, reason))
    database.commit()
    if actualy_warns < 1:
        sql.execute(f"INSERT INTO warns_{chat_id} VALUES (?, 1, ?, ?, {date}, '{date_string}')", (user_id, moder, reason))
        database.commit()
        return 1
    else:
        sql.execute(f"UPDATE warns_{chat_id} SET user_id = ?, count = ?, moder = ?, reason = ?, date = {date}, date_string = '{date_string}' WHERE user_id = {user_id}", (user_id, actualy_warns+1, moder, reason))
        database.commit()
        return actualy_warns+1

async def clear_warns(chat_id=int, user_id=int):
    sql.execute(f"DELETE FROM warns_{chat_id} WHERE user_id = {user_id}")
    database.commit()

async def unwarn(chat_id=int, user_id=int):
    warns = await get_warns(user_id, chat_id)
    if warns < 2: await clear_warns(chat_id, user_id)
    else:
        sql.execute(f"UPDATE warns_{chat_id} SET count = {warns-1} WHERE user_id = {user_id}")
        database.commit()

    return warns-1

async def gwarn(user_id=int, chat_id=int):
    sql.execute(f"SELECT * FROM warns_{chat_id} WHERE user_id = {user_id}")
    fetch = sql.fetchone()
    if fetch == None: return False
    else:
        return {
            'count': fetch[1],
            'moder': fetch[2],
            'reason': fetch[3],
            'time': fetch[5]
        }

async def warnhistory(user_id=int, chat_id=int):
    sql.execute(f"SELECT * FROM warnhistory_{chat_id} WHERE user_id = {user_id}")
    fetch = sql.fetchall()
    warnhistory_mass = []
    gi = 0
    if fetch == None: return False
    else:
        for i in fetch:
            gi = gi + 1
            warnhistory_mass.append(f"{gi}) @id{i[2]} (Модератор) | {i[3]} | {i[5]}")

    return warnhistory_mass

async def warnlist(chat_id=int):
    sql.execute(f"SELECT * FROM warns_{chat_id}")
    fetch = sql.fetchall()
    warns = []
    gi = 0
    for i in fetch:
        gi = gi + 1
        warns.append(f"{gi}) @id{i[0]} (Пользователь) | {i[3]} | @id{i[2]} (Модератор) | {i[1]}/3 | {i[5]}")

    if fetch == None: return False
    return warns

async def staff(chat_id: int):
    # ==== Локальные права из чата ====
    sql.execute(f"SELECT * FROM permissions_{chat_id}")
    fetch = sql.fetchall()
    moders = []
    stmoders = []
    admins = []
    stadmins = []
    zamspecadm = []
    specadm = []
    testers = []

    if fetch:
        for i in fetch:
            level = i[1]
            user_id = i[0]
            if level == 1: moders.append(format_vk_link(user_id, await get_user_name(user_id, chat_id)))
            elif level == 2: stmoders.append(format_vk_link(user_id, await get_user_name(user_id, chat_id)))
            elif level == 3: admins.append(format_vk_link(user_id, await get_user_name(user_id, chat_id)))
            elif level == 4: stadmins.append(format_vk_link(user_id, await get_user_name(user_id, chat_id)))
            elif level == 5: zamspecadm.append(format_vk_link(user_id, await get_user_name(user_id, chat_id)))
            elif level == 6: specadm.append(format_vk_link(user_id, await get_user_name(user_id, chat_id)))
            elif level == 12: testers.append(format_vk_link(user_id, await get_user_name(user_id, chat_id)))

    # ==== Глобальные права ====
    sql.execute("SELECT user_id, level FROM global_managers WHERE level IN (2,3,4,5,6,7)")
    global_fetch = sql.fetchall()
    zamruk = []
    oszamruk = []
    ruk = []
    dev = []
    zamglt = []
    glt = []

    for user_id, level in global_fetch:
        if level == 2: zamruk.append(format_vk_link(user_id, await get_user_name(user_id, None)))
        elif level == 4: oszamruk.append(format_vk_link(user_id, await get_user_name(user_id, None)))
        elif level == 6: ruk.append(format_vk_link(user_id, await get_user_name(user_id, None)))
        elif level == 7: dev.append(format_vk_link(user_id, await get_user_name(user_id, None)))
        elif level == 3: zamglt.append(format_vk_link(user_id, await get_user_name(user_id, None)))
        elif level == 5: glt.append(format_vk_link(user_id, await get_user_name(user_id, None)))

    return {
        'moders': moders,
        'stmoders': stmoders,
        'admins': admins,
        'stadmins': stadmins,
        'zamspecadm': zamspecadm,
        'specadm': specadm,
        'testers': testers,
        'zamruk': zamruk,
        'oszamruk': oszamruk,
        'ruk': ruk,
        'dev': dev,
        'zamglt': zamglt,
        'glt': glt
    }    

async def add_mute(user_id=int, chat_id=int, moder=int, reason=str, mute_time=int):
    cd = str(datetime.now()).split('.')
    date_string = cd[0]
    sql.execute(f"INSERT INTO mutes_{chat_id} VALUES (?, ?, ?, ?, ?, ?)", (user_id, moder, reason, time.time(), date_string, mute_time))
    database.commit()

async def add_mutelog(chat_id=int, user_id=int, moder_id=int, reason=str, mute_time=int, status=str):
    sql.execute(f"CREATE TABLE IF NOT EXISTS mutelogs_{chat_id} (user_id BIGINT, moder_id BIGINT, reason TEXT, date BIGINT, date_string TEXT, mute_time BIGINT, status TEXT);")
    cd = str(datetime.now()).split('.')
    date_string = cd[0]
    sql.execute(f"INSERT INTO mutelogs_{chat_id} VALUES (?, ?, ?, ?, ?, ?, ?)", (user_id, moder_id, reason, time.time(), date_string, mute_time, status))
    database.commit()

async def get_mute(user_id=int, chat_id=int):
    await checkMute(chat_id, user_id)

    sql.execute(f"SELECT * FROM mutes_{chat_id} WHERE user_id = {user_id}")
    fetch = sql.fetchone()

    if fetch == None: return False
    else:
        return {
            'moder': fetch[1],
            'reason': fetch[2],
            'date': fetch[4],
            'time': fetch[5]
        }

async def unmute(user_id=int, chat_id=int):
    sql.execute(f"DELETE FROM mutes_{chat_id} WHERE user_id = {user_id}")
    database.commit()

async def mutelist(chat_id=int):
    sql.execute(f"SELECT * FROM mutes_{chat_id}")
    fetch = sql.fetchall()
    mutes = []
    if fetch==None: return False
    else:
        for i in fetch:
            if not await checkMute(chat_id, i[0]):
                do_time = datetime.fromisoformat(i[4]) + timedelta(minutes=i[5])
                mute_time = str(do_time).split('.')[0]
                try:
                    int(i[1])
                    mutes.append(f"@id{i[0]} (Пользователь) | {i[2]} | @id{i[1]} (модератор) | До: {mute_time}")
                except: mutes.append(f"@id{i[0]} (Пользователь) | {i[2]} | Бот | До: {mute_time}")

    return mutes

async def checkMute(chat_id=int, user_id=int):
    sql.execute(f"SELECT * FROM mutes_{chat_id} WHERE user_id = {user_id}")
    fetch = sql.fetchone()
    if not fetch == None:
        do_time = datetime.fromisoformat(fetch[4]) + timedelta(minutes=fetch[5])
        if datetime.now() > do_time:
            sql.execute(f"DELETE FROM mutes_{chat_id} WHERE user_id = {user_id}")
            database.commit()
            return True
        else: return False
    return False

async def get_banwords(chat_id=int):
    sql.execute(f"SELECT * FROM banwords_{chat_id}")
    banwords = []
    fetch = sql.fetchall()
    for i in fetch:
        banwords.append(i[0])

    return banwords

async def clear(user_id=int, chat_id=int, group_id=int, peer_id=int):
    sql.execute(f"SELECT cmid FROM messages_{chat_id} WHERE user_id = {user_id}")
    fetch = sql.fetchall()
    cmids = []
    gi = 0
    for i in fetch:
        gi = gi + 1
        if gi <= 199:
            cmids.append(i[0])
    try: await bot.api.messages.delete(group_id=group_id, peer_id=peer_id, delete_for_all=True, cmids=cmids)
    except: pass

    sql.execute(f"DELETE FROM messages_{chat_id} WHERE user_id = {user_id}")
    database.commit()

async def new_message(user_id=int, message_id=int, cmid=int, chat_id=int):
    cd = str(datetime.now()).split('.')
    date_string = cd[0]
    sql.execute(f"INSERT INTO messages_{chat_id} VALUES (?, ?, ?, ?, ?)", (user_id, time.time(), date_string, message_id, cmid))
    database.commit()

async def add_money(user_id, amount):
    balances = load_data(BALANCES_FILE)
    bal = balances.get(str(user_id), get_balance(user_id))
    bal["wallet"] += amount
    balances[str(user_id)] = bal
    save_data(BALANCES_FILE, balances)
    await log_economy(user_id=user_id, target_id=None, amount=amount, log=f"получил(+а) {amount}$ через промокод")
    return True

async def give_vip(user_id, days):
    balances = load_data(BALANCES_FILE)
    bal = balances.get(str(user_id), get_balance(user_id))

    now = datetime.now()
    if bal.get("vip_until"):
        try:
            until = datetime.fromisoformat(bal["vip_until"])
            if until > now:
                bal["vip_until"] = (until + timedelta(days=days)).isoformat()
            else:
                bal["vip_until"] = (now + timedelta(days=days)).isoformat()
        except:
            bal["vip_until"] = (now + timedelta(days=days)).isoformat()
    else:
        bal["vip_until"] = (now + timedelta(days=days)).isoformat()

    balances[str(user_id)] = bal
    save_data(BALANCES_FILE, balances)
    await log_economy(user_id=user_id, target_id=None, amount=None, log=f"получил(+а) VIP на {days} дней через промокод")
    return True    


def has_active_vip(balance_data: dict) -> bool:
    vip_until = balance_data.get("vip_until")
    if not vip_until:
        return False
    try:
        return datetime.fromisoformat(str(vip_until)) > datetime.now()
    except Exception:
        return False

# --- Функция проверки бана только в одном чате ---
async def checkban(user_id: int, chat_id: int):
    try:
        sql.execute(f"SELECT * FROM bans_{chat_id} WHERE user_id = ?", (user_id,))
        fetch = sql.fetchone()
        if not fetch:
            return False
        return {
            'moder': fetch[1],
            'reason': fetch[2],
            'date': fetch[4]
        }
    except:
        return False  # если таблицы нет   
        
async def checkban_all(user_id: int):
    sql.execute("SELECT chat_id, title FROM chats")
    chats_list = sql.fetchall()

    all_bans = []
    count_bans = 0

    i = 1
    for c in chats_list:
        chat_id_check, chat_title = c
        table_name = f"bans_{chat_id_check}"
        try:
            sql.execute(f"SELECT moderator_id, reason, date FROM {table_name} WHERE user_id = ?", (user_id,))
            user_bans = sql.fetchall()
            for ub in user_bans:
                mod_id, reason, date = ub
                all_bans.append(f"{i}) {chat_title} | @id{mod_id} (Модератор) | {reason} | {date} МСК (UTC+3)")
                i += 1
                count_bans += 1
        except:
            continue  # если таблицы нет, пропускаем

    return count_bans, all_bans        

# --- Функция добавления/обновления бана ---
async def ban(user_id: int, moder: int, chat_id: int, reason: str):
    # Проверяем, есть ли уже бан
    sql.execute(f"SELECT user_id FROM bans_{chat_id} WHERE user_id = ?", (user_id,))
    fetch = sql.fetchone()

    # Текущее время в формате YYYY-MM-DD HH:MM:SS
    date_string = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if fetch is None:
        # Добавляем нового забаненного пользователя
        sql.execute(
            f"INSERT INTO bans_{chat_id} (user_id, moder, reason, date) VALUES (?, ?, ?, ?)",
            (user_id, moder, reason, date_string)
        )
        database.commit()
    else:
        # Обновляем данные, если пользователь уже в бане
        sql.execute(
            f"UPDATE bans_{chat_id} SET moder = ?, reason = ?, date = ? WHERE user_id = ?",
            (moder, reason, date_string, user_id)
        )
        database.commit()
        
async def unban(user_id=int, chat_id=int):
    sql.execute(f"DELETE FROM bans_{chat_id} WHERE user_id = {user_id}")
    database.commit()

async def globalrole(user_id: int, level: int):
    """
    Выдаёт или обновляет глобальную роль пользователя в таблице global_managers.

    level:
        0 - удаление роли
        8 - zamruk
        9 - oszamruk
        10 - ruk
        11 - dev
    """
    # Проверяем есть ли запись
    sql.execute("SELECT user_id FROM global_managers WHERE user_id = ?", (user_id,))
    fetch = sql.fetchone()

    if fetch is None:
        if level != 0:
            sql.execute("INSERT INTO global_managers (user_id, level) VALUES (?, ?)", (user_id, level))
    else:
        if level == 0:
            sql.execute("DELETE FROM global_managers WHERE user_id = ?", (user_id,))
        else:
            sql.execute("UPDATE global_managers SET level = ? WHERE user_id = ?", (level, user_id))

    database.commit()    

async def roleG(user_id=int, chat_id=int, role=int):
    sql.execute(f"SElECT user_id FROM permissions_{chat_id} WHERE user_id = {user_id}")
    fetch = sql.fetchone()
    if fetch == None:
        if role == 0: sql.execute(f"DELETE FROM permissions_{chat_id} WHERE user_id = {user_id}")
        else: sql.execute(f"INSERT INTO permissions_{chat_id} VALUES (?, ?)", (user_id, role))
    else:
        if role == 0: sql.execute(f"DELETE FROM permissions_{chat_id} WHERE user_id = {user_id}")
        else: sql.execute(f"UPDATE permissions_{chat_id} SET level = ? WHERE user_id = ?", (role, user_id))

    database.commit()

async def banlist(chat_id=int):
    sql.execute(f"SELECT * FROM bans_{chat_id}")
    fetch = sql.fetchall()
    banlist = []
    for i in fetch:
        banlist.append(f"@id{i[0]} (Пользователь) | {i[2]} | @id{i[1]} (Модератор) | {i[4]}")

    return banlist

async def quiet(chat_id=int):
    sql.execute(f"SELECT silence FROM chats WHERE chat_id = {chat_id}")
    result = sql.fetchone()[0]
    if not await get_logic(result):
        sql.execute(f"UPDATE chats SET silence = 1 WHERE chat_id = {chat_id}")
        database.commit()
        return True
    else:
        sql.execute(f"UPDATE chats SET silence = 0 WHERE chat_id = {chat_id}")
        database.commit()
        return False

async def get_pull_chats(chat_id=int):
    sql.execute(f"SELECT owner_id, in_pull FROM chats WHERE chat_id = {chat_id}")
    fetch = sql.fetchone()
    if fetch == None: return False
    if not await get_logic(fetch[1]): return False
    sql.execute(f"SELECT chat_id FROM chats WHERE owner_id = ? AND in_pull = ?", (fetch[0], fetch[1]))
    result = []
    fetch2 = sql.fetchall()
    for i in fetch2:
        result.append(i[0])

    return result

async def get_pull_id(chat_id=int):
    sql.execute(f"SELECT in_pull FROM chats WHERE chat_id = {chat_id}")
    fetch = sql.fetchone()
    return fetch[0]

async def rnickall(chat_id=int):
    sql.execute(f"DELETE FROM nicks_{chat_id}")
    database.commit()    

async def banwords(slovo=str, delete=bool, chat_id=int):
    if delete:
        sql.execute(f"DELETE FROM banwords_{chat_id} WHERE banword = ?", (slovo, ))
        database.commit()
    else:
        sql.execute(f"SELECT * FROM banwords_{chat_id} WHERE banword = ?", (slovo, ))
        fetch = sql.fetchone()
        if fetch == None:
            sql.execute(f"INSERT INTO banwords_{chat_id} VALUES (?)", (slovo,))
            database.commit()

async def get_filter(chat_id=int):
    sql.execute(f"SELECT filter FROM chats WHERE chat_id = {chat_id}")
    fetch = sql.fetchone()
    return await get_logic(fetch[0])

async def set_filter(chat_id=int, value=int):
    sql.execute("UPDATE chats SET filter = ? WHERE chat_id = ?", (value, chat_id))
    database.commit()

async def get_antiflood(chat_id=int):
    sql.execute(f"SELECT antiflood FROM chats WHERE chat_id = {chat_id}")
    fetch = sql.fetchone()
    return await get_logic(fetch[0])

async def set_antiflood(chat_id=int, value=int):
    sql.execute("UPDATE chats SET antiflood = ? WHERE chat_id = ?", (value, chat_id))
    database.commit()

async def get_spam(user_id=int, chat_id=int):
    sql.execute(f"SELECT date_string FROM messages_{chat_id}  WHERE user_id = {user_id} ORDER BY date_string DESC LIMIT 3")
    fetch = sql.fetchall()
    list_messages = []
    for i in fetch:
        list_messages.append(datetime.fromisoformat(i[0]))
    if len(list_messages) < 3:
        return False
    list_messages = list_messages[:3]
    return list_messages[0] - list_messages[2] < timedelta(seconds=2)

async def set_welcome(chat_id=int, text=int):
    sql.execute(f"UPDATE chats SET welcome_text = ? WHERE chat_id = ?", (text, chat_id))
    database.commit()

async def get_welcome(chat_id=int):
    sql.execute("SELECT welcome_text FROM chats WHERE chat_id = ?", (chat_id, ))
    fetch = sql.fetchone()
    if str(fetch[0]).lower().strip() == "off" and "None": return False
    else: return str(fetch[0])

async def invite_kick(chat_id=int, change=None):
    sql.execute("SELECT invite_kick FROM chats WHERE chat_id = ?", (chat_id, ))
    fetch = sql.fetchone()
    if not change == None:
        if await get_logic(fetch[0]):
            sql.execute("UPDATE chats SET invite_kick = 0 WHERE chat_id = ?", (chat_id, ))
            database.commit()
            return False
        else:
            sql.execute("UPDATE chats SET invite_kick = 1 WHERE chat_id = ?", (chat_id,))
            database.commit()
            return True
    else:
        return await get_logic(fetch[0])

async def leave_kick(chat_id=int, change=None):
    sql.execute("SELECT leave_kick FROM chats WHERE chat_id = ?", (chat_id,))
    fetch = sql.fetchone()
    if fetch == None: return False
    if change == None: return await get_logic(fetch[0])
    if await get_logic(fetch[0]):
        sql.execute("UPDATE chats SET leave_kick = 0 WHERE chat_id = ?", (chat_id,))
        database.commit()
        return False
    else:
        sql.execute("UPDATE chats SET leave_kick = 1 WHERE chat_id = ?", (chat_id,))
        database.commit()
        return True

async def get_server_chats(chat_id):
    """
    Определяет, к какому серверу принадлежит чат, и возвращает список всех chat_id из этого сервера.
    """
    sql.execute("SELECT owner_id, server_number, table_name FROM servers_list")
    servers = sql.fetchall()

    for owner_id, server_number, table_name in servers:
        try:
            sql.execute(f"SELECT chat_id FROM {table_name} WHERE chat_id = ?", (chat_id,))
            if sql.fetchone():
                sql.execute(f"SELECT chat_id FROM {table_name}")
                chats = sql.fetchall()
                return [c[0] for c in chats]
        except:
            continue
    return None    

async def get_current_server(chat_id):
    """
    Возвращает номер сервера, к которому привязан данный chat_id, или None, если не привязан.
    """
    sql.execute("SELECT owner_id, server_number, table_name FROM servers_list")
    servers = sql.fetchall()

    for owner_id, server_number, table_name in servers:
        try:
            sql.execute(f"SELECT chat_id FROM {table_name} WHERE chat_id = ?", (chat_id,))
            if sql.fetchone():
                return server_number  # возвращаем только номер сервера
        except Exception as e:
            print(f"[get_current_server] Ошибка при проверке таблицы {table_name}: {e}")
            continue
    return None    

async def message_stats(user_id=int, chat_id=int):
    try:
        sql.execute(f"SELECT date_string FROM messages_{chat_id} WHERE user_id = ?", (user_id, ))
        fetch_all = sql.fetchall()
        sql.execute(f"SELECT date_string FROM messages_{chat_id} WHERE user_id = ? ORDER BY date_string DESC LIMIT 1", (user_id,))
        fetch_last = sql.fetchone()
        last = fetch_last[0]
        return {
            'count': len(fetch_all),
            'last': last
        }
    except: return {
        'count': 0,
        'last': 0
    }

async def set_pull(chat_id=int, value=int):
    sql.execute(f"UPDATE chats SET in_pull = ? WHERE chat_id = ?", (value, chat_id))
    database.commit()

async def get_all_peerids():
    sql.execute("SELECT peer_id FROM chats")
    fetch = sql.fetchall()
    peer_ids = []
    for i in fetch:
        peer_ids.append(i[0])

    return peer_ids

async def add_punishment(chat_id=int, user_id=int):
    cd = str(datetime.now()).split('.')
    date_string = cd[0]
    sql.execute(f"INSERT INTO punishments_{chat_id} VALUES (?, ?)", (user_id, date_string))
    database.commit()

async def get_sliv(user_id=int, chat_id=int):
    sql.execute(f"SELECT date FROM punishments_{chat_id}  WHERE user_id = {user_id} ORDER BY date DESC LIMIT 3")
    fetch = sql.fetchall()
    list_messages = []
    for i in fetch:
        list_messages.append(datetime.fromisoformat(i[0]))
    try: list_messages = list_messages[:3]
    except: return False

    if list_messages[0] - list_messages[2] < timedelta(seconds=6): return True
    else: return False

async def get_ServerChat(chat_id: int):
    try:
        # Получаем id сервера, к которому привязан chat_id
        sql.execute("SELECT server FROM server_links WHERE chat_id = ?", (chat_id,))
        result = sql.fetchone()
        if not result:
            return None

        server_id = result[0]

        # Получаем все chat_id, привязанные к этому серверу
        sql.execute("SELECT chat_id FROM server_links WHERE server = ?", (server_id,))
        chats = [row[0] for row in sql.fetchall()]

        return {
            "server": server_id,
            "chats": chats
        }
    except Exception as e:
        print(f"[SERVER] Ошибка при получении сервера: {e}")
        return None     

def load_json_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_json_file(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def staff_zov(chat_id=int):
    sql.execute(f"SElECT user_id FROM permissions_{chat_id}")
    fetch = sql.fetchall()
    staff_zov_str = []
    for i in fetch:
        staff_zov_str.append(f"@id{i[0]} (⚜️)")

    return ''.join(staff_zov_str)

async def delete_message(group_id=int, peer_id=int, cmid=int):
    try: await bot.api.messages.delete(group_id=group_id, peer_id=peer_id, delete_for_all=True, cmids=cmid)
    except: pass

async def check_and_clear_midnight():
    msk_tz = pytz.timezone('Europe/Moscow')
    last_cleared = None
    
    while True:
        now = datetime.now(msk_tz)
        
        if now.hour == 0 and now.minute == 0 and last_cleared != now.date():
            clear_table_daily()
            last_cleared = now.date()
        
        await asyncio.sleep(1)

# Получить текущее состояние антислива (0 — выкл, 1 — вкл)
async def get_antisliv(chat_id):
    sql.execute("SELECT mode FROM antisliv WHERE chat_id = ?", (chat_id,))
    data = sql.fetchone()
    return data[0] if data else 0

# Установить новое состояние антислива
async def antisliv_mode(chat_id, mode):
    sql.execute("INSERT OR REPLACE INTO antisliv (chat_id, mode) VALUES (?, ?)", (chat_id, mode))
    database.commit()

async def set_onwer(user=int, chat=int):
    sql.execute("UPDATE chats SET owner_id = ? WHERE chat_id = ?", (user, chat))
    database.commit()

async def equals_roles(user_id_sender: int, user_id_two: int, chat_id: int, message):
    sender_role = await get_role(user_id_sender, chat_id)
    target_role = await get_role(user_id_two, chat_id)
    if sender_role > target_role:
        return 2
    return 0
  
chat_types = {
    "def": "общие беседы",
    "ext": "расширенная беседа",
    "pl": "беседа игроков",
    "hel": "беседа хелперов",
    "ld": "беседа лидеров",
    "adm": "беседа администраторов",
    "mod": "беседа модераторов",
    "tex": "беседа техов",
    "test": "беседа тестеров",
    "med": "беседа медиа-партнёров",
    "ruk": "беседа руководства",
    "users": "беседа пользователей"
}

def get_block_game(chat=None):
    sql.execute("SELECT mode FROM gamesettings WHERE chat_id = ?", (chat,))
    mode_data = sql.fetchone()
    mode = mode_data[0] if mode_data else 0
    
    if mode == 1:
        return True
    else:
        return False


GAME_COMMANDS = {
    "games", "game", "игры", "gamehelp",
    "казино", "casino",
    "баланс",
    "дуэль", "duel",
    "приз", "prize",
    "топ",
    "передать", "pay", "transfer",
    "положить", "depositbank",
    "снять", "withdrawbank",
    "открытьдепозит", "opendeposit",
    "закрытьдепозит", "closedeposit",
    "подписка",
    "кейс", "case",
    "кейсы", "кейсысклад", "моикейсы", "cases",
    "открытькейс", "openmycase",
    "инв", "инвентарь", "инвент", "inventory", "inv",
    "применить", "useitem", "applyitem",
    "распылить", "salvageitem", "dustitem",
    "бизнес", "business",
    "ппрод",
    "улучшбиз",
    "собратьбиз", "collectbiz",
    "аукцион", "аук", "auction",
    "выставитьаук", "sellauction",
    "купаук", "buyauction",
    "снятьаук", "removeauction",
    "благо",
    "топблаго",
    "buyvip", "купитьвипку",
    "промо", "promo",
}


GAME_CALLBACK_COMMANDS = {
    "buy_case", "open_case", "buybiz_menu", "buy_business",
    "biz_show_branches", "biz_menu", "biz_open", "biz_sell_confirm",
    "biz_sell_execute", "biz_branch_sell_confirm", "biz_branch_sell_execute",
    "biz_upgrade", "biz_refill", "apply_talisman_choose",
    "apply_talisman_menu", "my_cases", "case_chances", "case_menu",
    "buy_bananas_offer",
    "inventory_page", "auction_page",
}

@bot.on.private_message()
async def on_private_message(message: Message):
    await message.reply(p_message)
    return True

@bot.on.chat_message(rules.ChatActionRule("chat_kick_user"))
async def user_leave(message: Message) -> None:
    user_id = message.from_id
    chat_id = message.chat_id
    if not await check_chat(chat_id): return True
    if not message.action.member_id == message.from_id: return True
    if await leave_kick(chat_id):
        try: await bot.api.messages.remove_chat_user(chat_id, user_id)
        except: pass
        await message.answer(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), вышел(-ла) из беседы", disable_mentions=1)
    else:
        keyboard = (
            Keyboard(inline=True)
            .add(Callback("Исключить", {"command": "kick", "user": user_id, "chatId": chat_id}), color=KeyboardButtonColor.NEGATIVE)
        )
        await message.answer(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), вышел(-ла) из беседы", disable_mentions=1, keyboard=keyboard)

@bot.on.chat_message(rules.ChatActionRule("chat_invite_user"))
async def user_joined(message: Message) -> None:
    invited_user = message.action.member_id
    user_id = message.from_id
    chat_id = message.chat_id    
        
    async def _safe_first_name(uid: int) -> str:
        try:
            resp = await bot.api.users.get(uid)
            if resp and len(resp) > 0:
                return resp[0].first_name
        except Exception:
            pass
        return str(uid)

    try:
        # Бот добавлен
        if invited_user == -groupid:
            await message.answer(
                "Бот добавлен в беседу, выдайте мне администратора, а затем введите /start для активации беседы!\n\n"
                "Также с помощью /type Вы можете выбрать тип беседы!"
            )
            return True
        
        # ==== 🔹 Проверка защиты от сторонних сообществ ====
        sql.execute("SELECT * FROM protection WHERE chat_id = ? AND mode = 1", (chat_id,))
        prot = sql.fetchone()
        if prot:
            if invited_user < 0:  # сообщество
                try:
                    await bot.api.messages.remove_chat_user(chat_id, invited_user)
                except:
                    pass
                await message.answer(
                    f"@id{user_id} ({await get_user_name(user_id, chat_id)}) добавил сообщество, это запрещено в настройках данного чата!\n\n"
                    f"Выключить можно: «/защита»",
                    disable_mentions=1
                )
                return True

        # ==== 🔹 Проверка глобального бана ====
        sql.execute("SELECT * FROM blacklist WHERE user_id = ?", (invited_user,))
        blacklist_user = sql.fetchone()
        if blacklist_user:
            try:
                await bot.api.messages.remove_chat_user(chat_id, invited_user)
            except:
                pass

            await message.answer(
                f"@id{invited_user} ({await get_user_name(invited_user, chat_id)}) находится в ЧСБ BANANA MANAGER.",
                disable_mentions=1
            )
            return True

        # ==== 🔹 Проверка глобального бана ====
        sql.execute("SELECT * FROM gbanlist WHERE user_id = ?", (invited_user,))
        globalban = sql.fetchone()
        if globalban:
            try:
                await bot.api.messages.remove_chat_user(chat_id, invited_user)
            except:
                pass

            first = await _safe_first_name(invited_user)
            await message.answer(
                f"@id{invited_user} ({await get_user_name(invited_user, chat_id)}) имеет глобальную блокировку!\n\n"
                f"@id{globalban[1]} (Модератор) | {globalban[2]} | {globalban[3]}",
                disable_mentions=1
            )
            return True
            
        # ==== 🔹 Проверка глобального бана ====
        sql.execute("SELECT * FROM globalban WHERE user_id = ?", (invited_user,))
        globalban = sql.fetchone()
        if globalban:
            try:
                await bot.api.messages.remove_chat_user(chat_id, invited_user)
            except:
                pass

            first = await _safe_first_name(invited_user)
            await message.answer(
                f"@id{invited_user} ({await get_user_name(invited_user, chat_id)}), имеет общую блокировку во всех беседах!\n\n"
                f"@id{globalban[1]} (Модератор) | {globalban[2]} | {globalban[3]}",
                disable_mentions=1
            )
            return True            

        # ==== Пользователь вошёл сам ====
        if user_id == invited_user:
            checkban_str = await checkban(invited_user, chat_id)
            if checkban_str:
                try:
                    await bot.api.messages.remove_chat_user(chat_id, invited_user)
                except:
                    pass

                first = await _safe_first_name(invited_user)
                keyboard = (
                    Keyboard(inline=True)
                    .add(Callback("✅ Снять бан", {"command": "unban", "user": invited_user, "chatId": chat_id}), color=KeyboardButtonColor.POSITIVE)
                )
                await message.answer(
                    f"@id{invited_user} ({await get_user_name(invited_user, chat_id)}) заблокирован(-а) в этой беседе!\n\n"
                    f"Информация о блокировке:\n@id{checkban_str['moder']} (Модератор) | {checkban_str['reason']} | {checkban_str['date']}",
                    disable_mentions=1,
                    keyboard=keyboard
                )
                return True

            welcome = await get_welcome(chat_id)
            if welcome:
                first = await _safe_first_name(invited_user)
                inviter_first = await _safe_first_name(user_id)
                welcome = welcome.replace('%u', f'@id{invited_user}')
                welcome = welcome.replace('%n', f'@id{invited_user} ({await get_user_name(invited_user, chat_id)})')
                welcome = welcome.replace('%i', f'@id{user_id}')
                welcome = welcome.replace('%p', f'@id{user_id} ({await get_user_name(user_id, chat_id)})')
                await message.answer(welcome)
                return True

        # ==== Кто-то пригласил другого пользователя ====
        if await get_role(user_id, chat_id) < 1 and await invite_kick(chat_id):
            try:
                await bot.api.messages.remove_chat_user(chat_id, invited_user)
            except:
                pass
            return True

        checkban_str = await checkban(invited_user, chat_id)
        if checkban_str:
            try:
                await bot.api.messages.remove_chat_user(chat_id, invited_user)
            except:
                pass

            first = await _safe_first_name(invited_user)
            keyboard = (
                Keyboard(inline=True)
                .add(Callback("✅ Снять бан", {"command": "unban", "user": invited_user, "chatId": chat_id}), color=KeyboardButtonColor.POSITIVE)
            )
            await message.answer(
                f"@id{invited_user} ({await get_user_name(invited_user, chat_id)}) заблокирован(-а) в этой беседе!\n\n"
                f"Информация о блокировке:\n@id{checkban_str['moder']} (Модератор) | {checkban_str['reason']} | {checkban_str['date']}",
                disable_mentions=1,
                keyboard=keyboard
            )
            return True

        welcome = await get_welcome(chat_id)
        if welcome:
            first = await _safe_first_name(invited_user)
            inviter_first = await _safe_first_name(user_id)
            welcome = welcome.replace('%u', f'@id{invited_user}')
            welcome = welcome.replace('%n', f'@id{invited_user} ({await get_user_name(invited_user, chat_id)})')
            welcome = welcome.replace('%i', f'@id{user_id}')
            welcome = welcome.replace('%p', f'@id{user_id} ({await get_user_name(user_id, chat_id)})')
            await message.answer(welcome)
            return True

    except Exception as e:
        print(f"[user_joined] Ошибка: {e}")
        return True        

@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, dataclass=GroupTypes.MessageEvent)
async def handlers(message: GroupTypes.MessageEvent):
    global balances
    payload = message.object.payload or {}
    command = str(payload.get("command", "")).lower()
    user_id = message.object.user_id
    chat_id = payload.get("chatId")
    if not chat_id:
        peer_id = int(message.object.peer_id)
        chat_id = peer_id - 2000000000 if peer_id >= 2000000000 else 0

    # Лог для каждой кнопки
    log_cmd = payload.get("log") or "нет лога"
    print(f"{user_id} использовал кнопку {command}. ВК выдало: {log_cmd}")
    if chat_id and get_block_game(chat_id) and command in GAME_CALLBACK_COMMANDS:
        await answer_callback_event(message, "Игровые команды отключены в этой беседе")
        return True
    if command == "buy_case":
        case_type = str(payload.get("case_type", ""))
        if case_type not in CASE_DEFS or CASE_DEFS[case_type]["daily"]:
            await answer_callback_event(message, "Недоступное действие")
            return True
        owner_id = int(payload.get("owner_id", 0) or 0)
        if owner_id and owner_id != user_id:
            await answer_callback_event(message, "Эта кнопка доступна только автору команды")
            return True
        bal = _cached_user_balance(user_id)
        case_def = CASE_DEFS[case_type]
        if case_def["money_cost"] > bal.get("wallet", 0):
            await answer_callback_event(message, "Недостаточно валюты")
            return True
        if case_def["banana_cost"] > bal.get("bananas", 0):
            await answer_callback_event(message, "Недостаточно бананов")
            return True
        if case_def["money_cost"]:
            bal["wallet"] -= case_def["money_cost"]
        if case_def["banana_cost"]:
            bal["bananas"] = max(0, bal.get("bananas", 0) - case_def["banana_cost"])
        case_id = await add_user_case(user_id, case_type)
        balances[str(user_id)] = bal
        save_data(BALANCES_FILE, balances)
        _drop_user_cache(user_id)
        paid_amount = int(case_def["banana_cost"] or case_def["money_cost"] or 0)
        paid_currency = "бананов" if int(case_def["banana_cost"] or 0) > 0 else "$"
        await log_economy(user_id=user_id, target_id=None, amount=paid_amount, log=f"купил(-а) кейс «{case_def['name']}» за {paid_amount} {paid_currency}")
        await answer_callback_event(message, f"Вы купили {case_def['name']}")
        await delete_message(groupid, message.object.peer_id, message.object.conversation_message_id)
        buyer_name = await get_user_name(user_id, None)
        kb = Keyboard(inline=True)
        kb.add(
            Callback("Открыть кейс", {"command": "open_case", "case_type": case_type, "owner_id": user_id, "case_id": case_id}),
            color=KeyboardButtonColor.POSITIVE,
        ).row()
        kb.add(Callback("Мои кейсы", {"command": "my_cases", "owner_id": user_id}), color=KeyboardButtonColor.SECONDARY)
        purchase_image = CASE_PURCHASE_IMAGES.get(case_type)
        purchase_attachment = await upload_message_photo(message.object.peer_id, purchase_image) if purchase_image else None
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            random_id=0,
            keyboard=kb,
            attachment=purchase_attachment,
            message=(
                f"@id{user_id} ({buyer_name}) успешно купил {case_def['name']}.\n"
                f"Кейс добавлен на склад под номером #{case_id}.\n"
                "Нажмите кнопку ниже или используйте /открытькейс [номер]."
            ),
        )
        return True

    if command == "join_giveaway":
        giveaway_id = str(payload.get("giveaway_id", "")).strip()
        if not giveaway_id or giveaway_id not in giveaways:
            await answer_callback_event(message, "Эта раздача уже завершена или недоступна")
            return True

        giveaway = giveaways.get(giveaway_id, {})
        if int(giveaway.get("creator_id", 0) or 0) == user_id:
            await answer_callback_event(message, "Нельзя участвовать в собственной раздаче")
            return True

        if not await is_user_subscribed_to_bot_group(user_id):
            await answer_callback_event(message, "Вы не подписаны на сообщество бота")
            return True

        participants = set(str(uid) for uid in giveaway.get("participants", []))
        if str(user_id) in participants:
            await answer_callback_event(message, "Вы уже участвуете в этой раздаче")
            return True

        participants.add(str(user_id))
        giveaway["participants"] = list(participants)
        giveaways[giveaway_id] = giveaway
        save_data(GIVEAWAYS_FILE, giveaways)
        await answer_callback_event(message, "Поздравляю! Жди окончания раздачи потом будет результат")
        return True

    if command == "buy_bananas_offer":
        offer_id = str(payload.get("offer_id", "")).strip()
        offer = banana_offers.get(offer_id)
        if not offer:
            await answer_callback_event(message, "Это предложение уже недоступно")
            return True
        if int(offer.get("seller_id", 0)) == user_id:
            await answer_callback_event(message, "Нельзя купить собственное предложение")
            return True
        buyer_bal = get_balance(user_id)
        total_price = int(offer.get("price", 0))
        banana_amount = int(offer.get("amount", 0))
        if buyer_bal.get("wallet", 0) < total_price:
            await answer_callback_event(message, "Недостаточно монет")
            return True
        seller_id = int(offer.get("seller_id", 0))
        seller_bal = get_balance(seller_id)
        buyer_bal["wallet"] -= total_price
        buyer_bal["bananas"] = int(buyer_bal.get("bananas", 0)) + banana_amount
        seller_bal["wallet"] = int(seller_bal.get("wallet", 0)) + total_price
        _persist_user_balance(user_id, buyer_bal)
        _persist_user_balance(seller_id, seller_bal)
        banana_offers.pop(offer_id, None)
        save_data(BANANA_OFFERS_FILE, banana_offers)
        await log_economy(user_id=user_id, target_id=seller_id, amount=total_price, log=f"купил(-а) {banana_amount} бананов за {total_price}$")
        await log_economy(user_id=seller_id, target_id=user_id, amount=total_price, log=f"продал(-а) {banana_amount} бананов за {total_price}$")
        await answer_callback_event(message, "Бананы куплены")
        await delete_message(groupid, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            random_id=0,
            message=(
                f"🍌 Сделка завершена!\n\n"
                f"Покупатель: @id{user_id} ({await get_user_name(user_id, chat_id)})\n"
                f"Продавец: @id{seller_id} ({await get_user_name(seller_id, chat_id)})\n"
                f"Количество: {format_number(banana_amount)} бананов\n"
                f"Цена: {format_number(total_price)}$"
            ),
            disable_mentions=1,
        )
        return True

    if command == "open_case":
        case_type = str(payload.get("case_type", ""))
        if case_type not in CASE_DEFS:
            await answer_callback_event(message, "Неизвестный кейс")
            return True
        owner_id = int(payload.get("owner_id", 0) or 0)
        if owner_id and owner_id != user_id:
            await answer_callback_event(message, "Эта кнопка доступна только автору команды")
            return True
        try:
            bal = _cached_user_balance(user_id)
            case_def = CASE_DEFS[case_type]
            case_id = int(payload.get("case_id", 0) or 0)
            if case_def["daily"]:
                remaining = await get_daily_remaining(user_id)
                if remaining:
                    await answer_callback_event(message, f"Ежедневный кейс через {_daily_remaining_text(remaining)}")
                    return True
            elif case_id:
                stored_case = await get_user_case_by_id(user_id, case_id)
                if not stored_case:
                    await answer_callback_event(message, "Этот кейс уже открыт или не найден")
                    return True
            else:
                if case_def["money_cost"] > bal.get("wallet", 0):
                    await answer_callback_event(message, "Недостаточно валюты")
                    return True
                if case_def["banana_cost"] > bal.get("bananas", 0):
                    await answer_callback_event(message, "Недостаточно бананов")
                    return True
                if case_def["money_cost"]:
                    bal["wallet"] -= case_def["money_cost"]
                if case_def["banana_cost"]:
                    bal["bananas"] = max(0, bal.get("bananas", 0) - case_def["banana_cost"])

            reward, reward_text = await open_case(case_type, user_id)
            if case_id:
                await remove_user_case(user_id, case_id)
            if reward["type"] == "money":
                bal["wallet"] += int(reward["amount"])
            elif reward["type"] == "vip_days":
                now = datetime.now()
                current_vip = bal.get("vip_until")
                start_dt = now
                if current_vip:
                    try:
                        vip_dt = datetime.fromisoformat(current_vip)
                        if vip_dt > now:
                            start_dt = vip_dt
                    except Exception:
                        pass
                bal["vip_until"] = (start_dt + timedelta(days=int(reward["days"]))).isoformat()

            balances[str(user_id)] = bal
            save_data(BALANCES_FILE, balances)
            _drop_user_cache(user_id)
            await log_economy(user_id=user_id, target_id=None, amount=None, log=f"открыл(-а) кейс «{case_def['name']}» и получил {reward_text}")
            await answer_callback_event(message, "Кейс открыт")
            await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
            opener_name = await get_user_name(user_id, None)
            reward_attachment = await upload_message_photo(
                message.object.peer_id,
                CASE_REWARD_IMAGES.get(case_type)
            ) if CASE_REWARD_IMAGES.get(case_type) else None
            reward_hint = ""
            if reward["type"] == "business":
                reward_hint = "\nБизнес уже активирован. Пропишите /business, чтобы посмотреть свои бизнесы."
            elif reward["type"] == "item":
                reward_hint = "\nПредмет уже добавлен в ваш инвентарь."
            elif reward["type"] == "vip_days":
                reward_hint = "\nVIP-статус уже автоматически добавлен к вашему текущему VIP."
            result_kb = None
            if not case_def["daily"]:
                result_kb = Keyboard(inline=True)
                result_kb.add(
                    Callback(
                        "🛒 Купить ещё",
                        {"command": "buy_case", "case_type": case_type, "owner_id": user_id},
                    ),
                    color=KeyboardButtonColor.POSITIVE,
                )
            await bot.api.messages.send(
                peer_id=message.object.peer_id,
                random_id=0,
                attachment=reward_attachment,
                keyboard=result_kb,
                message=(
                    f"@id{user_id} ({opener_name}) открыл {case_def['name']}.\n"
                    f"Результат открытия:\n"
                    f"Вы получили: {reward_text}{reward_hint}\n\n"
                    "Забирайте награду и возвращайтесь за следующим кейсом."
                ),
            )
        except Exception as e:
            log.exception("Ошибка открытия кейса: %s", e)
            await answer_callback_event(message, "Ошибка открытия кейса")
        return True

    if command == "buybiz_menu":
        await answer_callback_event(message, "Открываю список бизнесов")
        await delete_message(groupid, message.object.peer_id, message.object.conversation_message_id)
        page = max(1, int(payload.get("page", 1) or 1))
        owner_id = int(payload.get("owner_id", user_id) or user_id)
        keys = _business_keys_ordered()
        per_page = 5
        total_pages = max(1, (len(keys) + per_page - 1) // per_page)
        page = min(page, total_pages)
        start = (page - 1) * per_page
        end = start + per_page
        page_keys = keys[start:end]
        kb = Keyboard(inline=True)
        lines = [f"🏢 Покупка бизнеса [{page}/{total_pages}]", "", "Выберите бизнес из списка ниже:", ""]
        for idx, key in enumerate(page_keys, start=start + 1):
            info = BUSINESSES_CATALOG[key]
            icon = _business_emoji(key)
            income_min = int(info.get("income_min", info.get("base_income", 0)))
            income_max = int(info.get("income_max", info.get("base_income", 0)))
            lines.append(
                f'{idx}. {icon} {info["name"]}\n'
                f'💰 Цена: {format_number(int(info["price"]))}$\n'
                f'📈 Прибыль в день: {format_number(income_min)}$ - {format_number(income_max)}$\n'
            )
            kb.add(
                Callback(
                    _short_business_button_label(info["name"], int(info["price"])),
                    {"command": "buy_business", "business_key": key, "owner_id": owner_id},
                ),
                color=KeyboardButtonColor.PRIMARY,
            ).row()
        if total_pages > 1:
            kb.row()
            if page > 1:
                kb.add(Callback("Назад", {"command": "buybiz_menu", "page": page - 1, "owner_id": owner_id}), color=KeyboardButtonColor.SECONDARY)
            if page < total_pages:
                kb.add(Callback("Вперед", {"command": "buybiz_menu", "page": page + 1, "owner_id": owner_id}), color=KeyboardButtonColor.SECONDARY)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            random_id=0,
            keyboard=kb,
            message="\n".join(lines),
        )
        return True

    if command == "buy_business":
        if not _callback_owner_allowed(payload, user_id):
            await answer_callback_event(message, "Эта кнопка доступна только автору меню")
            return True
        key = str(payload.get("business_key", ""))
        if key not in BUSINESSES_CATALOG:
            await answer_callback_event(message, "Неизвестный бизнес")
            return True
        info = BUSINESSES_CATALOG[key]
        bal = _cached_user_balance(user_id)
        if bal.get("wallet", 0) < int(info["price"]):
            await answer_callback_event(message, "Недостаточно валюты для покупки")
            return True
        bal["wallet"] -= int(info["price"])
        balances[str(user_id)] = bal
        save_data(BALANCES_FILE, balances)
        _drop_user_cache(user_id)
        branch_no = await add_business(user_id, key)
        await log_economy(user_id=user_id, target_id=None, amount=int(info["price"]), log=f"купил(-а) бизнес «{info['name']}» за {int(info['price'])}$")
        await answer_callback_event(message, "Бизнес куплен")
        await delete_message(groupid, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            random_id=0,
            message=(
                f'{_business_emoji(key)} Вы приобрели «{info["name"]}».\n'
                f'🏬 Новый филиал: #{branch_no}\n'
                f'💸 Стоимость покупки: {format_number(int(info["price"]))}$'
            ),
        )
        return True

    if command == "biz_show_branches":
        if not _callback_owner_allowed(payload, user_id):
            await answer_callback_event(message, "Эта кнопка доступна только автору меню")
            return True
        business_key = str(payload.get("business_key", ""))
        page = max(1, int(payload.get("page", 1) or 1))
        if not business_key:
            await answer_callback_event(message, "Неизвестный бизнес")
            return True
        await sync_user_business_income(user_id)
        businesses = await get_user_businesses(user_id)
        branches = [b for b in businesses if b["business_key"] == business_key]
        if not branches:
            await answer_callback_event(message, "Филиалы не найдены")
            return True
        await answer_callback_event(message, "Открываю филиалы")
        await delete_message(groupid, message.object.peer_id, message.object.conversation_message_id)
        per_page = 3
        total_pages = max(1, (len(branches) + per_page - 1) // per_page)
        page = min(page, total_pages)
        page_branches = branches[(page - 1) * per_page: page * per_page]
        kb = Keyboard(inline=True)
        for branch in page_branches:
            kb.add(
                Callback(
                    f'{_business_emoji(business_key)} Филиал #{branch["branch_no"]}',
                    {"command": "biz_open", "business_id": branch["id"], "owner_id": user_id, "business_key": business_key, "page": page},
                ),
                color=KeyboardButtonColor.PRIMARY,
            ).row()
        if total_pages > 1:
            if page > 1:
                kb.add(
                    Callback("⬅️ Назад", {"command": "biz_show_branches", "business_key": business_key, "owner_id": user_id, "page": page - 1}),
                    color=KeyboardButtonColor.SECONDARY,
                )
            if page < total_pages:
                kb.add(
                    Callback("➡️ Вперед", {"command": "biz_show_branches", "business_key": business_key, "owner_id": user_id, "page": page + 1}),
                    color=KeyboardButtonColor.SECONDARY,
                )
            kb.row()
        title = BUSINESSES_CATALOG.get(business_key, {"name": business_key})["name"]
        kb.add(
            Callback("💸 Продать бизнес", {"command": "biz_sell_confirm", "business_key": business_key, "owner_id": user_id}),
            color=KeyboardButtonColor.NEGATIVE,
        ).row()
        kb.add(Callback("⬅️ Назад", {"command": "biz_menu", "owner_id": user_id}), color=KeyboardButtonColor.SECONDARY)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            random_id=0,
            keyboard=kb,
            message=f"{_business_emoji(business_key)} Бизнес: {title}\n🏬 Выберите филиал для управления [{page}/{total_pages}]:",
        )
        return True

    if command == "biz_menu":
        if not _callback_owner_allowed(payload, user_id):
            await answer_callback_event(message, "Эта кнопка доступна только автору меню")
            return True
        await delete_message(groupid, message.object.peer_id, message.object.conversation_message_id)
        page = max(1, int(payload.get("page", 1) or 1))
        await sync_user_business_income(user_id)
        businesses = await get_user_businesses(user_id)
        if not businesses:
            kb = Keyboard(inline=True)
            kb.add(Callback("🛒 Купить бизнес", {"command": "buybiz_menu", "owner_id": user_id}), color=KeyboardButtonColor.PRIMARY)
            await bot.api.messages.send(
                peer_id=message.object.peer_id,
                random_id=0,
                keyboard=kb,
                message="🏢 У вас пока нет бизнесов.\n🛒 Нажмите кнопку ниже, чтобы купить первый бизнес.",
            )
            return True
        grouped = {}
        for biz in businesses:
            grouped.setdefault(biz["business_key"], []).append(biz)
        grouped_items = sorted(
            grouped.items(),
            key=lambda item: int(BUSINESSES_CATALOG.get(item[0], {"price": 0}).get("price", 0)),
        )
        per_page = 4
        total_pages = max(1, (len(grouped_items) + per_page - 1) // per_page)
        page = min(page, total_pages)
        start = (page - 1) * per_page
        end = start + per_page
        page_items = grouped_items[start:end]
        kb = Keyboard(inline=True)
        total_daily_income = sum(_business_daily_potential(branch) for branch in businesses)
        lines = [
            f"🏢 Ваши бизнесы [{page}/{total_pages}]",
            "",
            f"📈 Общий доход за 1 день: {format_number(total_daily_income)}$",
            "",
        ]
        for business_key, branches in page_items:
            title = BUSINESSES_CATALOG.get(business_key, {"name": business_key})["name"]
            icon = _business_emoji(business_key)
            products = sum(int(branch.get("products", 0)) for branch in branches)
            daily_income = sum(_business_daily_potential(branch) for branch in branches)
            lines.append(
                f"{icon} {title}\n"
                f"🏬 Филиалов: {len(branches)} | 📦 Продуктов: {products}\n"
                f"📈 Доход за 1 день: {format_number(daily_income)}$"
            )
            kb.add(
                Callback(
                    f"{icon} {_short_business_button_label(title, 0)}",
                    {"command": "biz_show_branches", "business_key": business_key, "owner_id": user_id},
                ),
                color=KeyboardButtonColor.PRIMARY,
            ).row()
        if total_pages > 1:
            if page > 1:
                kb.add(Callback("⬅️ Назад", {"command": "biz_menu", "page": page - 1, "owner_id": user_id}), color=KeyboardButtonColor.SECONDARY)
            if page < total_pages:
                kb.add(Callback("➡️ Вперед", {"command": "biz_menu", "page": page + 1, "owner_id": user_id}), color=KeyboardButtonColor.SECONDARY)
            if page > 1 or page < total_pages:
                kb.row()
        kb.add(Callback("🛒 Купить бизнес", {"command": "buybiz_menu", "owner_id": user_id}), color=KeyboardButtonColor.SECONDARY)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            random_id=0,
            keyboard=kb,
            message="\n".join(lines),
        )
        return True

    if command == "biz_open":
        if not _callback_owner_allowed(payload, user_id):
            await answer_callback_event(message, "Эта кнопка доступна только автору меню")
            return True
        business_id = int(payload.get("business_id", 0))
        await sync_user_business_income(user_id)
        biz = await get_business_by_id(user_id, business_id)
        if not biz:
            await answer_callback_event(message, "Филиал не найден")
            return True
        await answer_callback_event(message, "Открываю филиал")
        await delete_message(groupid, message.object.peer_id, message.object.conversation_message_id)
        level = int(biz["upgrade_level"])
        products = int(biz["products"])
        income_preview = int(biz["meta"]["base_income"] * (1 + UPGRADE_BONUSES.get(level, 0.0) + (5.0 if int(biz["talisman_active"]) else 0.0)))
        product_cost = _business_product_cost(biz["meta"])
        next_upgrade_cost = get_upgrade_cost_for_business(biz["meta"], min(level + 1, 3)) if level < 3 else 0
        kb = Keyboard(inline=True)
        kb.add(
            Callback("⬆️ Улучшить биз", {"command": "biz_upgrade", "business_id": business_id, "owner_id": user_id}),
            color=KeyboardButtonColor.POSITIVE,
        ).row()
        kb.add(
            Callback("📦 Заполнить склад 100/100", {"command": "biz_refill", "business_id": business_id, "owner_id": user_id, "amount": 100}),
            color=KeyboardButtonColor.PRIMARY,
        ).row()
        kb.add(
            Callback(
                "💸 Продать филиал",
                {"command": "biz_branch_sell_confirm", "business_id": business_id, "owner_id": user_id, "business_key": biz["business_key"]},
            ),
            color=KeyboardButtonColor.NEGATIVE,
        ).row()
        kb.add(
            Callback(
                "⬅️ Назад",
                {"command": "biz_show_branches", "business_key": str(payload.get("business_key", biz["business_key"])), "owner_id": user_id, "page": int(payload.get("page", 1) or 1)},
            ),
            color=KeyboardButtonColor.SECONDARY,
        )
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            random_id=0,
            keyboard=kb,
            message=(
                f'{_business_emoji(biz["business_key"])} Филиал #{biz["branch_no"]}: {biz["meta"]["name"]}\n'
                f'⭐ Уровень: {level}\n'
                f'📦 Продукты: {products}/100\n'
                f'💼 Счет филиала: {format_number(int(biz["branch_balance"]))}$\n'
                f'📈 Доход бизнеса за 1 день: {format_number(income_preview)}$\n'
                f'⬆️ Цена следующего улучшения: {format_number(next_upgrade_cost)}$\n'
                f'⏳ Следующий сбор: {_format_business_collect_cooldown(biz)}\n'
                f'🪬 Талисман: {"активен" if int(biz.get("talisman_active", 0)) else "не активен"}\n'
                f'🏦 Цена 1 продукта: {format_number(product_cost)}$ с банка'
            ),
        )
        return True

    if command == "biz_sell_confirm":
        if not _callback_owner_allowed(payload, user_id):
            await answer_callback_event(message, "Эта кнопка доступна только автору меню")
            return True
        business_key = str(payload.get("business_key", ""))
        businesses = await get_user_businesses(user_id)
        branches = [b for b in businesses if b["business_key"] == business_key]
        if not branches:
            await answer_callback_event(message, "Бизнес не найден")
            return True
        title = BUSINESSES_CATALOG.get(business_key, {"name": business_key})["name"]
        await answer_callback_event(message, "Подтверждение продажи бизнеса")
        await delete_message(groupid, message.object.peer_id, message.object.conversation_message_id)
        kb = Keyboard(inline=True)
        kb.add(
            Callback("💸 Продать бизнес", {"command": "biz_sell_execute", "business_key": business_key, "owner_id": user_id}),
            color=KeyboardButtonColor.NEGATIVE,
        )
        kb.add(
            Callback("⬅️ Выйти", {"command": "biz_show_branches", "business_key": business_key, "owner_id": user_id}),
            color=KeyboardButtonColor.SECONDARY,
        )
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            random_id=0,
            keyboard=kb,
            message=f"⚠️ Вы точно хотите продать бизнес «{title}»?\n🏬 Будут удалены все филиалы этого бизнеса.",
        )
        return True

    if command == "biz_sell_execute":
        if not _callback_owner_allowed(payload, user_id):
            await answer_callback_event(message, "Эта кнопка доступна только автору меню")
            return True
        business_key = str(payload.get("business_key", ""))
        deleted_count, sample = await delete_business_group(user_id, business_key)
        if deleted_count < 1 or not sample:
            await answer_callback_event(message, "Бизнес не найден")
            return True
        await log_economy(user_id=user_id, target_id=None, amount=None, log=f"продал(-а) бизнес «{sample['meta']['name']}». Удалено филиалов: {deleted_count}")
        await answer_callback_event(message, "Бизнес продан")
        await delete_message(groupid, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            random_id=0,
            message=f"🏢 Бизнес «{sample['meta']['name']}» продан. Удалено филиалов: {deleted_count}.",
        )
        return True

    if command == "biz_branch_sell_confirm":
        if not _callback_owner_allowed(payload, user_id):
            await answer_callback_event(message, "Эта кнопка доступна только автору меню")
            return True
        business_id = int(payload.get("business_id", 0) or 0)
        biz = await get_business_by_id(user_id, business_id)
        if not biz:
            await answer_callback_event(message, "Филиал не найден")
            return True
        await answer_callback_event(message, "Подтверждение продажи филиала")
        await delete_message(groupid, message.object.peer_id, message.object.conversation_message_id)
        kb = Keyboard(inline=True)
        kb.add(
            Callback(
                "💸 Продать филиал",
                {"command": "biz_branch_sell_execute", "business_id": business_id, "owner_id": user_id, "business_key": biz["business_key"]},
            ),
            color=KeyboardButtonColor.NEGATIVE,
        )
        kb.add(
            Callback("⬅️ Выйти", {"command": "biz_open", "business_id": business_id, "owner_id": user_id, "business_key": biz["business_key"]}),
            color=KeyboardButtonColor.SECONDARY,
        )
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            random_id=0,
            keyboard=kb,
            message=(
                f"⚠️ Вы точно хотите продать филиал #{biz['branch_no']}?\n"
                f"{_business_emoji(biz['business_key'])} Бизнес: «{biz['meta']['name']}»"
            ),
        )
        return True

    if command == "biz_branch_sell_execute":
        if not _callback_owner_allowed(payload, user_id):
            await answer_callback_event(message, "Эта кнопка доступна только автору меню")
            return True
        business_id = int(payload.get("business_id", 0) or 0)
        ok, biz = await delete_business_branch(user_id, business_id)
        if not ok or not biz:
            await answer_callback_event(message, "Филиал не найден")
            return True
        await log_economy(user_id=user_id, target_id=None, amount=None, log=f"продал(-а) филиал #{biz['branch_no']} бизнеса «{biz['meta']['name']}»")
        await answer_callback_event(message, "Филиал продан")
        await delete_message(groupid, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            random_id=0,
            message=f"🏢 Филиал #{biz['branch_no']} бизнеса «{biz['meta']['name']}» продан.",
        )
        return True

    if command == "biz_upgrade":
        if not _callback_owner_allowed(payload, user_id):
            await answer_callback_event(message, "Эта кнопка доступна только автору меню")
            return True
        business_id = int(payload.get("business_id", 0) or 0)
        biz = await get_business_by_id(user_id, business_id)
        if not biz:
            await answer_callback_event(message, "Филиал не найден")
            return True
        success, text, cost = await upgrade_business(user_id, business_id)
        if not success:
            await answer_callback_event(message, text)
            return True
        bal = get_balance(user_id)
        if bal["wallet"] < cost:
            sql.execute("UPDATE businesses SET upgrade_level = ? WHERE id = ?", (int(biz["upgrade_level"]), business_id))
            database.commit()
            await answer_callback_event(message, f"Нужно {format_number(cost)}$")
            return True
        bal["wallet"] -= cost
        balances[str(user_id)] = bal
        save_data(BALANCES_FILE, balances)
        _drop_user_cache(user_id)
        await answer_callback_event(message, f"Улучшено за {format_number(cost)}$")
        payload["command"] = "biz_open"
        payload["business_key"] = biz["business_key"]
        message.object.payload = payload
        return await handlers(message)

    if command == "biz_refill":
        if not _callback_owner_allowed(payload, user_id):
            await answer_callback_event(message, "Эта кнопка доступна только автору меню")
            return True
        business_id = int(payload.get("business_id", 0) or 0)
        amount = max(1, int(payload.get("amount", 100) or 100))
        biz = await get_business_by_id(user_id, business_id)
        if not biz:
            await answer_callback_event(message, "Филиал не найден")
            return True
        current_products = int(biz.get("products", 0))
        if current_products >= 100:
            await answer_callback_event(message, "Склад уже заполнен")
            return True
        add_amount = min(amount, 100 - current_products)
        total_cost = add_amount * _business_product_cost(biz["meta"])
        bal = get_balance(user_id)
        if bal["bank"] < total_cost:
            await answer_callback_event(message, f"Нужно {format_number(total_cost)}$ на банке")
            return True
        ok, msg, _added = await refill_products(user_id, business_id, add_amount)
        if not ok:
            await answer_callback_event(message, msg)
            return True
        bal["bank"] -= total_cost
        balances[str(user_id)] = bal
        save_data(BALANCES_FILE, balances)
        _drop_user_cache(user_id)
        await answer_callback_event(message, f"Склад пополнен до {current_products + add_amount}/100")
        payload["command"] = "biz_open"
        payload["business_key"] = biz["business_key"]
        message.object.payload = payload
        return await handlers(message)

    if command == "apply_talisman_choose":
        if not _callback_owner_allowed(payload, user_id):
            await answer_callback_event(message, "Эта кнопка доступна только автору меню")
            return True
        item_id = int(payload.get("item_id", 0) or 0)
        business_id = int(payload.get("business_id", 0) or 0)
        item = await get_item_by_id(user_id, item_id)
        if not item or not _is_business_talisman(item):
            await answer_callback_event(message, "Талисман не найден в инвентаре")
            return True
        ok, text = await activate_business_talisman(user_id, business_id)
        if not ok:
            await answer_callback_event(message, text)
            return True
        await remove_item(user_id, item_id)
        biz = await get_business_by_id(user_id, business_id)
        if biz:
            await log_economy(user_id=user_id, target_id=None, amount=None, log=f"использовал(-а) талисман «{item['item_name']}» на филиал #{biz['branch_no']} бизнеса «{biz['meta']['name']}»")
        await answer_callback_event(message, "Талисман активирован")
        await delete_message(groupid, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            random_id=0,
            message=(
                f"🪬 Талисман активирован.\n"
                f"{_business_emoji(biz['business_key'])} Филиал #{biz['branch_no']}: {biz['meta']['name']}\n"
                f"📈 Бонус к доходу: +500%"
            ),
        )
        return True

    if command == "apply_talisman_menu":
        if not _callback_owner_allowed(payload, user_id):
            await answer_callback_event(message, "Эта кнопка доступна только автору меню")
            return True
        item_id = int(payload.get("item_id", 0) or 0)
        page = int(payload.get("page", 1) or 1)
        item = await get_item_by_id(user_id, item_id)
        if not item or not _is_business_talisman(item):
            await answer_callback_event(message, "Талисман не найден в инвентаре")
            return True
        kb, _page, talisman_text = await _build_talisman_business_menu(user_id, item_id, page)
        await answer_callback_event(message, "Открываю список филиалов")
        await delete_message(groupid, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            random_id=0,
            keyboard=kb if kb.buttons else None,
            message=talisman_text,
        )
        return True

    if command == "my_cases":
        if not _callback_owner_allowed(payload, user_id):
            await answer_callback_event(message, "Эта кнопка доступна только автору меню")
            return True
        await answer_callback_event(message, "Открываю склад кейсов")
        await delete_message(groupid, message.object.peer_id, message.object.conversation_message_id)
        cases = await get_user_cases(user_id)
        kb = Keyboard(inline=True)
        kb.add(Callback("Назад к кейсам", {"command": "case_menu", "owner_id": user_id}), color=KeyboardButtonColor.SECONDARY)
        if not cases:
            await bot.api.messages.send(
                peer_id=message.object.peer_id,
                random_id=0,
                keyboard=kb,
                message="Склад кейсов пуст.\nПокупайте кейсы через +кейс.",
            )
            return True
        lines = ["Неоткрытые кейсы:", ""]
        for idx, case in enumerate(cases, start=1):
            lines.append(f"{idx}. {case['meta']['name']} | ID: {case['id']}")
            if idx <= 8:
                kb.add(
                    Callback(
                        f"Открыть #{idx}",
                        {"command": "open_case", "case_type": case["case_type"], "case_id": case["id"], "owner_id": user_id},
                    ),
                    color=KeyboardButtonColor.PRIMARY,
                ).row()
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            random_id=0,
            keyboard=kb,
            message="\n".join(lines) + "\n\nКоманда: /открытькейс [номер]",
        )
        return True

    if command == "inventory_page":
        if not _callback_owner_allowed(payload, user_id):
            await answer_callback_event(message, "Эта кнопка доступна только автору меню")
            return True
        await answer_callback_event(message, "Открываю инвентарь")
        await delete_message(groupid, message.object.peer_id, message.object.conversation_message_id)
        page = max(1, int(payload.get("page", 1) or 1))
        items, kb, text = await _build_inventory_page(user_id, page)
        if not items:
            await bot.api.messages.send(
                peer_id=message.object.peer_id,
                random_id=0,
                message="🎒 Инвентарь пуст.\nПолучайте предметы из кейсов и наград.",
            )
            return True
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            random_id=0,
            keyboard=kb if kb.buttons else None,
            message=text,
        )
        return True

    if command == "auction_page":
        await answer_callback_event(message, "Открываю аукцион")
        await delete_message(groupid, message.object.peer_id, message.object.conversation_message_id)
        page = max(1, int(payload.get("page", 1) or 1))
        lots, kb, text = await _build_auction_page(chat_id or 0, page)
        if not lots:
            await bot.api.messages.send(
                peer_id=message.object.peer_id,
                random_id=0,
                message="🏛 Аукцион пуст.\nВыставить лот: /выставитьаук [ID предмета] [ставка]",
            )
            return True
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            random_id=0,
            keyboard=kb if kb.buttons else None,
            message=text,
        )
        return True

    if command == "case_chances":
        if not _callback_owner_allowed(payload, user_id):
            await answer_callback_event(message, "Эта кнопка доступна только автору меню")
            return True
        await answer_callback_event(message, "Показываю шансы")
        await delete_message(groupid, message.object.peer_id, message.object.conversation_message_id)
        kb = Keyboard(inline=True)
        kb.add(Callback("Назад к кейсам", {"command": "case_menu", "owner_id": user_id}), color=KeyboardButtonColor.SECONDARY)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            random_id=0,
            keyboard=kb,
            message=CASE_CHANCES_TEXT,
        )
        return True

    if command == "case_menu":
        if not _callback_owner_allowed(payload, user_id):
            await answer_callback_event(message, "Эта кнопка доступна только автору меню")
            return True
        await answer_callback_event(message, "Открываю кейсы")
        await delete_message(groupid, message.object.peer_id, message.object.conversation_message_id)
        kb, case_text = await build_cases_menu(user_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            random_id=0,
            keyboard=kb,
            message=case_text,
        )
        return True

    if command == "nicksminus":
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True
        page = payload.get("page")
        if page < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это первая страница!"})
            )
            return True

        keyboard = (
            Keyboard(inline=True)
            .add(Callback("⏪", {"command": "nicksMinus", "page": page - 1, "chatId": chat_id}),
                 color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("Без ников", {"command": "nonicks", "chatId": chat_id}), color=KeyboardButtonColor.PRIMARY)
            .add(Callback("⏩", {"command": "nicksPlus", "page": page - 1, "chatId": chat_id}),
                 color=KeyboardButtonColor.POSITIVE)
        )
        await delete_message(groupid, message.object.peer_id, message.object.conversation_message_id)
        nicks_str = '\n'.join(await nlist(chat_id, page-1))
        await bot.api.messages.send(peer_id=2000000000 + chat_id, message=f"Пользователи с ником [{page-1} страница]:\n{nicks_str}\n\nПользователи без ников: «/nonick»", disable_mentions=1, random_id=0, keyboard=keyboard)

    if command == "nicksplus":
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        page = payload.get("page")

        nicks = await nlist(chat_id, page + 1)
        if len(nicks) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это последняя страница!"})
            )
            return True

        keyboard = (
            Keyboard(inline=True)
            .add(Callback("⏪", {"command": "nicksMinus", "page": page+1, "chatId": chat_id}),
                 color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("Без ников", {"command": "nonicks", "chatId": chat_id}), color=KeyboardButtonColor.PRIMARY)
            .add(Callback("⏩", {"command": "nicksPlus", "page": page+1, "chatId": chat_id}),
                 color=KeyboardButtonColor.POSITIVE)
        )
        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        nicks_str = '\n'.join(nicks)
        await bot.api.messages.send(peer_id=2000000000 + chat_id,message=f"Пользователи с ником [{page + 1} страница]:\n{nicks_str}\n\nПользователи без ников: «/nonick»",disable_mentions=1, random_id=0, keyboard=keyboard)

    if command == "chatsminus":
        if await get_role(user_id, chat_id) < 10:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        page = payload.get("page")
        if page < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это первая страница!"})
            )
            return True

        sql.execute("SELECT chat_id, owner_id FROM chats ORDER BY chat_id ASC")
        all_rows = sql.fetchall()
        total = len(all_rows)
        per_page = 5
        max_page = (total + per_page - 1) // per_page

        async def get_chats_page(page: int):
            start = (page - 1) * per_page
            end = start + per_page
            selected = all_rows[start:end]
            formatted = []
            for idx, (chat_id_row, owner_id) in enumerate(selected, start=start + 1):
                rel_id = 2000000000 + chat_id_row
                try:
                    resp = await bot.api.messages.get_conversations_by_id(peer_ids=rel_id)
                    if resp.items:
                        chat_title = resp.items[0].chat_settings.title or "Без названия"
                    else:
                        chat_title = "Без названия"
                except:
                    chat_title = "Ошибка получения названия"

                try:
                    link_resp = await bot.api.messages.get_invite_link(peer_id=rel_id, reset=0)
                    chat_link = link_resp.link
                except:
                    chat_link = "Ошибка"

                try:
                    owner_info = await bot.api.users.get(user_ids=owner_id)
                    owner_name = f"{owner_info[0].first_name} {owner_info[0].last_name}"
                except:
                    owner_name = "Не удалось получить имя"

                formatted.append(
                    f"{idx}) {chat_id_row} | {chat_title} | @id{owner_id} ({owner_name}) | [{chat_link}|Ссылка на чат]"
                )
            return formatted

        new_page = page - 1
        chats = await get_chats_page(new_page)
        chats_text = "\n".join(chats)
        if not chats_text:
            chats_text = "Беседы отсутствуют!"

        keyboard = (
            Keyboard(inline=True)
            .add(Callback("⏪", {"command": "chatsMinus", "page": new_page}), color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("⏩", {"command": "chatsPlus", "page": new_page}), color=KeyboardButtonColor.POSITIVE)
        )

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            message=f"Список зарегистрированных чатов [{new_page} страница]:\n\n{chats_text}",
            disable_mentions=1, random_id=0, keyboard=keyboard
        )
        return True


    if command == "chatsplus":
        if await get_role(user_id, chat_id) < 10:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        page = payload.get("page")

        sql.execute("SELECT chat_id, owner_id FROM chats ORDER BY chat_id ASC")
        all_rows = sql.fetchall()
        total = len(all_rows)
        per_page = 5
        max_page = (total + per_page - 1) // per_page

        async def get_chats_page(page: int):
            start = (page - 1) * per_page
            end = start + per_page
            selected = all_rows[start:end]
            formatted = []
            for idx, (chat_id_row, owner_id) in enumerate(selected, start=start + 1):
                rel_id = 2000000000 + chat_id_row
                try:
                    resp = await bot.api.messages.get_conversations_by_id(peer_ids=rel_id)
                    if resp.items:
                        chat_title = resp.items[0].chat_settings.title or "Без названия"
                    else:
                        chat_title = "Без названия"
                except:
                    chat_title = "Ошибка получения названия"

                try:
                    link_resp = await bot.api.messages.get_invite_link(peer_id=rel_id, reset=0)
                    chat_link = link_resp.link
                except:
                    chat_link = "Ошибка"

                try:
                    owner_info = await bot.api.users.get(user_ids=owner_id)
                    owner_name = f"{owner_info[0].first_name} {owner_info[0].last_name}"
                except:
                    owner_name = "Не удалось получить имя"

                formatted.append(
                    f"{idx}) {chat_id_row} | {chat_title} | @id{owner_id} ({owner_name}) | [{chat_link}|Ссылка на чат]"
                )
            return formatted

        new_page = page + 1
        chats = await get_chats_page(new_page)
        if len(chats) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это последняя страница!"})
            )
            return True

        chats_text = "\n".join(chats)
        keyboard = (
            Keyboard(inline=True)
            .add(Callback("⏪", {"command": "chatsMinus", "page": new_page}), color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("⏩", {"command": "chatsPlus", "page": new_page}), color=KeyboardButtonColor.POSITIVE)
        )

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            message=f"Список зарегистрированных чатов [{new_page} страница]:\n\n{chats_text}",
            disable_mentions=1, random_id=0, keyboard=keyboard
        )
        return True
        
    if command == "nonicks":
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        nonicks = await nonick(chat_id, 1)
        nonick_list = '\n'.join(nonicks)
        if nonick_list == "": nonick_list = "Пользователи без ников отсутствуют!"

        keyboard = (
            Keyboard(inline=True)
            .add(Callback("⏪", {"command": "nonickMinus", "page": 1, "chatId": chat_id}),
                 color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("С никами", {"command": "nicks", "chatId": chat_id}), color=KeyboardButtonColor.PRIMARY)
            .add(Callback("⏩", {"command": "nonickPlus", "page": 1, "chatId": chat_id}),
                 color=KeyboardButtonColor.POSITIVE)
        )

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(peer_id=2000000000+chat_id, message=f"Пользователи без ников [1]:\n{nonick_list}\n\nПользователи с никами: «/nlist»", disable_mentions=1, random_id=0 ,keyboard=keyboard)

    if command == "nicks":
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        nicks = await nlist(chat_id, 1)
        nick_list = '\n'.join(nicks)
        if nick_list == "": nick_list = "Ники отсутствуют!"

        keyboard = (
            Keyboard(inline=True)
            .add(Callback("⏪", {"command": "nicksMinus", "page": 1, "chatId": chat_id}),
                 color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("Без ников", {"command": "nonicks", "chatId": chat_id}), color=KeyboardButtonColor.PRIMARY)
            .add(Callback("⏩", {"command": "nicksPlus", "page": 1, "chatId": chat_id}),
                 color=KeyboardButtonColor.POSITIVE)
        )

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(peer_id=2000000000+chat_id, message=f"Пользователи с ником [1 страница]:\n{nick_list}\n\nПользователи без ников: «/nonick»",
                            disable_mentions=1, keyboard=keyboard, random_id=0)

    if command == "nonickminus":
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        page = payload.get("page")
        if page < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это первая страница!"})
            )
            return True

        nonicks = await nonick(chat_id, 1)
        nonick_list = '\n'.join(nonicks)
        if nonick_list == "": nonick_list = "Пользователи без ников отсутствуют!"

        keyboard = (
            Keyboard(inline=True)
            .add(Callback("⏪", {"command": "nonickMinus", "page": page+1, "chatId": chat_id}),
                 color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("С никами", {"command": "nicks", "chatId": chat_id}), color=KeyboardButtonColor.PRIMARY)
            .add(Callback("⏩", {"command": "nonickPlus", "page": page+1, "chatId": chat_id}),
                 color=KeyboardButtonColor.POSITIVE)
        )

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(peer_id=2000000000 + chat_id, message=f"Пользователи без ников [{page-1}]:\n{nonick_list}\n\nПользователи с никами: «/nlist»", disable_mentions=1, random_id=0, keyboard=keyboard)

    if command == "nonickplus":
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True
        page = payload.get("page")
        nonicks = await nonick(chat_id, page+1)
        if len(nonicks) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это последняя страница!"})
            )
            return True

        nonicks_str = '\n'.join(nonicks)
        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(peer_id=2000000000 + chat_id,
                                    message=f"Пользователи без ников [{page + 1}]:\n{nonicks_str}\n\nПользователи с никами: «/nlist»",
                                    disable_mentions=1, random_id=0, keyboard=keyboard)

    if command == "clear":
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        user = payload.get("user")
        await clear(user, chat_id, message.group_id, 2000000000+chat_id)
        x = await bot.api.messages.get_by_conversation_message_id(peer_id=2000000000+chat_id, conversation_message_ids=message.object.conversation_message_id, group_id=message.group_id)
        x = json.loads(x.json())['items'][0]['text']
        await bot.api.messages.edit(peer_id=2000000000 + chat_id, message=x, conversation_message_id=message.object.conversation_message_id, keyboard=None)
        await bot.api.messages.send(peer_id=2000000000 + chat_id, message=f"@id{user_id} ({await get_user_name(user_id, chat_id)}) очистил(-а) сообщения", disable_mentions=1, random_id=0)

    if command == "unwarn":
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        user = payload.get("user")
        if await equals_roles(user_id, user, chat_id, message) < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Вы не можете снять пред данному пользователю!"})
            )
            return True

        await unwarn(chat_id, user)
        x = await bot.api.messages.get_by_conversation_message_id(peer_id=2000000000 + chat_id,conversation_message_ids=message.object.conversation_message_id,group_id=message.group_id)
        x = json.loads(x.json())['items'][0]['text']
        await bot.api.messages.edit(peer_id=2000000000 + chat_id, message=x, conversation_message_id=message.object.conversation_message_id, keyboard=None)
        await bot.api.messages.send(peer_id=2000000000 + chat_id, message=f"@id{user_id} ({await get_user_name(user_id, chat_id)}) снял(-а) предупреждение @id{user} ({await get_user_name(user, chat_id)})", disable_mentions=1, random_id=0)

    if command == 'stats':
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        user = payload.get("user")
        reg_data = await get_registration_date(user)
        info = await bot.api.users.get(user)
        role = await get_role(user, chat_id)
        warns = await get_warns(user, chat_id)
        if await is_nick(user_id, chat_id):
            nick = await get_user_name(user, chat_id)
        else:
            nick = "Нет"
        messages = await message_stats(user_id, chat_id)

        roles = {0: "Пользователь", 1: "Модератор", 2: "Старший Модератор", 3: "Администратор",
                 4: "Старший Администратор", 5: "Владелец беседы", 6: "Менеджер бота"}

        x = await bot.api.messages.get_by_conversation_message_id(peer_id=2000000000 + chat_id,
                                                                  conversation_message_ids=message.object.conversation_message_id,
                                                                  group_id=message.group_id)
        x = json.loads(x.json())['items'][0]['text']
        await bot.api.messages.edit(peer_id=2000000000 + chat_id, message=x,conversation_message_id=message.object.conversation_message_id, keyboard=None)
        await bot.api.messages.send(peer_id=2000000000 + chat_id, message=f"@id{user_id} ({await get_user_name(user_id, chat_id)}), статистика @id{user} (пользователя):\nИмя и фамилия: {info[0].first_name} {info[0].last_name}\nДата регистрации: {reg_data}\nНик: {nick}\nРоль: {roles.get(role)}\nВсего предупреждений: {warns}/3\nВсего сообщений: {messages['count']}\nПоследнее сообщение: {messages['last']}", disable_mentions=1, random_id=0)

    if command == "activewarns":
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        user = payload.get("user")
        warns = await gwarn(user, chat_id)
        string_info = str
        if not warns: string_info = "Активных предупреждений нет!"
        else: string_info = f"@id{warns['moder']} (Модератор) | {warns['reason']} | {warns['count']}/3 | {warns['time']}"

        keyboard = (
            Keyboard(inline=True)
            .add(Callback("История всех предупреждений", {"command": "warnhistory", "user": user, "chatId": chat_id}),
                 color=KeyboardButtonColor.PRIMARY)
        )

        x = await bot.api.messages.get_by_conversation_message_id(peer_id=2000000000 + chat_id,
                                                                  conversation_message_ids=message.object.conversation_message_id,
                                                                  group_id=message.group_id)
        x = json.loads(x.json())['items'][0]['text']
        await bot.api.messages.edit(peer_id=2000000000 + chat_id, message=x,
                                    conversation_message_id=message.object.conversation_message_id, keyboard=None)
        await bot.api.messages.send(peer_id=2000000000 + chat_id, message=f"@id{user_id} ({await get_user_name(user_id, chat_id)}), информация о активных предупреждениях @id{user} (пользователя):\n{string_info}", disable_mentions=1, keyboard=keyboard, random_id=0)

    if command == "warnhistory":
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        user = payload.get("user")

        warnhistory_mass = await warnhistory(user, chat_id)
        if not warnhistory_mass:wh_string = "Предупреждений не было!"
        else:wh_string = '\n'.join(warnhistory_mass)

        x = await bot.api.messages.get_by_conversation_message_id(peer_id=2000000000 + chat_id,
                                                                  conversation_message_ids=message.object.conversation_message_id,
                                                                  group_id=message.group_id)
        x = json.loads(x.json())['items'][0]['text']
        await bot.api.messages.edit(peer_id=2000000000 + chat_id, message=x,
                                    conversation_message_id=message.object.conversation_message_id, keyboard=None)
        await bot.api.messages.send(peer_id=2000000000 + chat_id, message=f"Информация о всех предупреждениях @id{user} ({await get_user_name(user, chat_id)})\nКоличество предупреждений пользователя: {await get_warns(user, chat_id)}\n\nИнформация о последних 10 предупреждений пользователя:\n{wh_string}",disable_mentions=1, random_id=0)

    if command == "unmute":
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        user = payload.get("user")

        if await equals_roles(user_id, user, chat_id, None) < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        # Получаем информацию о муте ДО снятия
        mute_info = await get_mute(user, chat_id)
        await unmute(user, chat_id)
        # Добавляем лог для кнопки "Снять мут"
        if mute_info:
            await add_mutelog(chat_id, user, user_id, mute_info['reason'], mute_info['time'], "снят")
        x = await bot.api.messages.get_by_conversation_message_id(peer_id=2000000000 + chat_id,
                                                                  conversation_message_ids=message.object.conversation_message_id,
                                                                  group_id=message.group_id)
        x = json.loads(x.json())['items'][0]['text']
        await bot.api.messages.edit(peer_id=2000000000 + chat_id, message=x,
                                    conversation_message_id=message.object.conversation_message_id, keyboard=None)
        await bot.api.messages.send(peer_id=2000000000 + chat_id,
                                    message=f"@id{user_id} ({await get_user_name(user_id, chat_id)}) размутил(-а) @id{user} ({await get_user_name(user, chat_id)})",
                                    disable_mentions=1, random_id=0)

    if command == "unban":
        if await get_role(user_id, chat_id) < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        user = payload.get("user")
        if await equals_roles(user_id, user, chat_id, message) < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps(
                    {"type": "show_snackbar", "text": "Вы не можете снять бан данному пользователю!"})
            )
            return True

        await unban(user, chat_id)
        x = await bot.api.messages.get_by_conversation_message_id(peer_id=2000000000 + chat_id,
                                                                  conversation_message_ids=message.object.conversation_message_id,
                                                                  group_id=message.group_id)
        x = json.loads(x.json())['items'][0]['text']
        await bot.api.messages.edit(peer_id=2000000000 + chat_id, message=x,
                                    conversation_message_id=message.object.conversation_message_id, keyboard=None)
        await bot.api.messages.send(peer_id=2000000000 + chat_id,
                                    message=f"@id{user_id} ({await get_user_name(user_id, chat_id)}) разблокировал(-а) @id{user} ({await get_user_name(user, chat_id)})",
                                    disable_mentions=1, random_id=0)

    if command == "kick":
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        user = payload.get("user")
        if await equals_roles(user_id, user, chat_id, message) < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps(
                    {"type": "show_snackbar", "text": "Вы не можете кикнуть данного пользователя!"})
            )
            return True

        try: await bot.api.messages.remove_chat_user(chat_id, user)
        except: pass

        x = await bot.api.messages.get_by_conversation_message_id(peer_id=2000000000 + chat_id,
                                                                  conversation_message_ids=message.object.conversation_message_id,
                                                                  group_id=message.group_id)
        x = json.loads(x.json())['items'][0]['text']
        await bot.api.messages.edit(peer_id=2000000000 + chat_id, message=x,
                                    conversation_message_id=message.object.conversation_message_id, keyboard=None)
        await bot.api.messages.send(peer_id=2000000000 + chat_id,
                                    message=f"@id{user_id} ({await get_user_name(user_id, chat_id)}) кикнул(-а) @id{user} ({await get_user_name(user, chat_id)})",
                                    disable_mentions=1, random_id=0)

    if command == "approve_form" or command == "reject_form":
        # Получаем chat_id из peer_id, если нужно
        chat_id = message.object.peer_id
        if chat_id > 2000000000:  # беседа
            chat_id -= 2000000000

        # Проверка прав
        if await get_role(user_id, chat_id) < 8:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        # Получаем данные из payload безопасно
        target = payload.get("target")
        sender = payload.get("sender")
        reason = payload.get("reason", "Не указано")

        if not target or not sender:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Ошибка: нет данных пользователя"})
            )
            return True

        # Редактируем предыдущее сообщение без кнопок
        x_resp = await bot.api.messages.get_by_conversation_message_id(
            peer_id=message.object.peer_id,
            conversation_message_ids=message.object.conversation_message_id,
            group_id=message.group_id
        )
        items = json.loads(x_resp.json()).get('items', [])
        if not items:
            return True
        x_text = items[0]['text']

        await bot.api.messages.edit(
            peer_id=message.object.peer_id,
            message=x_text,
            conversation_message_id=message.object.conversation_message_id,
            keyboard=None
        )

        # Выполняем approve или reject
        if command == "approve_form":
            sql.execute(
                "INSERT INTO gbanlist (user_id, moderator_id, reason_gban, datetime_globalban) VALUES (?, ?, ?, ?)",
                (target, user_id, f"{reason} | By form | @id{sender} (пользователь)",
                 datetime.now().strftime("%d.%m.%Y %H:%M"))
            )
            database.commit()

            await bot.api.messages.send(
                peer_id=message.object.peer_id,
                message=f"@id{user_id} ({await get_user_name(user_id, chat_id)}) одобрил форму пользователя @id{sender} ({await get_user_name(sender, chat_id)})",
                disable_mentions=1,
                random_id=0
            )
        else:
            await bot.api.messages.send(
                peer_id=message.object.peer_id,
                message=f"@id{user_id} ({await get_user_name(user_id, chat_id)}) отклонил форму пользователя @id{sender} ({await get_user_name(sender, chat_id)})",
                disable_mentions=1,
                random_id=0
            )

        return True

    if command == "banwordsminus":
        if await get_role(user_id, chat_id) < 10:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id, peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        page = payload.get("page")
        if page < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id, peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это первая страница!"})
            )
            return True

        sql.execute("SELECT word, creator_id, time FROM ban_words ORDER BY time DESC")
        rows = sql.fetchall()
        total = len(rows)
        per_page = 5
        max_page = (total + per_page - 1) // per_page

        async def get_words_page(page: int):
            start = (page - 1) * per_page
            end = start + per_page
            formatted = []
            for i, (word, creator, tm) in enumerate(rows[start:end], start=start + 1):
                try:
                    info = await bot.api.users.get(user_ids=creator)
                    creator_name = f"{info[0].first_name} {info[0].last_name}"
                except:
                    creator_name = "Не удалось получить имя"
                formatted.append(f"{i}. {word} | @id{creator} ({creator_name}) | Время: {tm}")
            return formatted

        new_page = page - 1
        words = await get_words_page(new_page)
        words_text = "\n\n".join(words)

        keyboard = (
            Keyboard(inline=True)
            .add(Callback("⏪", {"command": "banwordsMinus", "page": new_page}), color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("⏩", {"command": "banwordsPlus", "page": new_page}), color=KeyboardButtonColor.POSITIVE)
        )

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            message=f"Запрещённые слова (Страница: {new_page}):\n\n{words_text}\n\nВсего запрещенных слов: {total}",
            disable_mentions=1, random_id=0, keyboard=keyboard
        )
        return True


    if command == "banwordsplus":
        if await get_role(user_id, chat_id) < 10:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id, peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        page = payload.get("page")

        sql.execute("SELECT word, creator_id, time FROM ban_words ORDER BY time DESC")
        rows = sql.fetchall()
        total = len(rows)
        per_page = 5
        max_page = (total + per_page - 1) // per_page

        async def get_words_page(page: int):
            start = (page - 1) * per_page
            end = start + per_page
            formatted = []
            for i, (word, creator, tm) in enumerate(rows[start:end], start=start + 1):
                try:
                    info = await bot.api.users.get(user_ids=creator)
                    creator_name = f"{info[0].first_name} {info[0].last_name}"
                except:
                    creator_name = "Не удалось получить имя"
                formatted.append(f"{i}. {word} | @id{creator} ({creator_name}) | Время: {tm}")
            return formatted

        new_page = page + 1
        words = await get_words_page(new_page)
        if len(words) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id, peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это последняя страница!"})
            )
            return True

        words_text = "\n\n".join(words)
        keyboard = (
            Keyboard(inline=True)
            .add(Callback("⏪", {"command": "banwordsMinus", "page": new_page}), color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("⏩", {"command": "banwordsPlus", "page": new_page}), color=KeyboardButtonColor.POSITIVE)
        )

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            message=f"Запрещённые слова (Страница {new_page}):\n\n{words_text}\n\nВсего запрещенных слов: {total}",
            disable_mentions=1, random_id=0, keyboard=keyboard
        )
        return True        
        
    if command == "join_duel":
        try:
            # Разбор payload
            data = {}
            if message.object.payload:
                try:
                    if isinstance(message.object.payload, str):
                        data = json.loads(message.object.payload)
                    elif isinstance(message.object.payload, dict):
                        data = message.object.payload
                    else:
                        print(f"[join_duel] payload неизвестного типа: {type(message.object.payload)}")
                except Exception as e:
                    print(f"[join_duel] Ошибка парсинга payload: {e}")

            peer = str(data.get("peer")) if data else None
            print(f"[join_duel] peer из payload: {peer}")

            if not peer or peer not in duels:
                print(f"[join_duel] Дуэль недоступна: ключ '{peer}' не найден в duels. "
                      f"Текущие ключи: {list(duels.keys())}")
                await bot.api.messages.send_message_event_answer(
                    event_id=message.object.event_id,
                    peer_id=message.object.peer_id,
                    user_id=message.object.user_id,
                    event_data=json.dumps({"type": "show_snackbar", "text": "⚔️ Дуэль недоступна"})
                )
                return True

            duel = duels[peer]
            print(f"[join_duel] Найдена дуэль: {duel}")
            duel["accepted"] = True

            author = duel["author"]
            stake = duel["stake"]
            user_id = message.object.user_id

            if user_id == author:
                print("[join_duel] Игрок пытается вступить в свою же дуэль!")
                await bot.api.messages.send_message_event_answer(
                    event_id=message.object.event_id,
                    peer_id=message.object.peer_id,
                    user_id=user_id,
                    event_data=json.dumps({"type": "show_snackbar", "text": "Ты не можешь вступить в свою же дуэль!"})
                )
                return True

            # Загружаем баланс
            balances = load_data(BALANCES_FILE)
            joiner = balances.get(str(user_id), get_balance(user_id))
            if joiner["wallet"] < stake:
                print(f"[join_duel] Недостаточно монет у {user_id}: {joiner['wallet']} < {stake}")
                await bot.api.messages.send_message_event_answer(
                    event_id=message.object.event_id,
                    peer_id=message.object.peer_id,
                    user_id=user_id,
                    event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно монет!"})
                )
                return True

            # Определяем победителя
            winner = random.choice([author, user_id])
            loser = user_id if winner == author else author
            print(f"[join_duel] Победитель: {winner}, Проигравший: {loser}")

            w_bal = balances.get(str(winner), get_balance(winner))
            l_bal = balances.get(str(loser), get_balance(loser))

            w_bal["wallet"] += stake
            w_bal["won"] += 1
            w_bal["won_total"] += stake

            l_bal["wallet"] -= stake
            l_bal["lost"] += 1
            l_bal["lost_total"] += stake

            balances[str(winner)] = w_bal
            balances[str(loser)] = l_bal
            save_data(BALANCES_FILE, balances)
            print("[join_duel] Балансы обновлены и сохранены")

            # Получаем имена
            try:
                w_info = await bot.api.users.get(user_ids=winner)
                l_info = await bot.api.users.get(user_ids=loser)
                w_name = f"{w_info[0].first_name} {w_info[0].last_name}"
                l_name = f"{l_info[0].first_name} {l_info[0].last_name}"
            except Exception as e:
                print(f"[join_duel] Ошибка получения имён: {e}")
                w_name = str(winner)
                l_name = str(loser)

            # Убираем кнопки с исходного сообщения
            try:
                x_resp = await bot.api.messages.get_by_conversation_message_id(
                    peer_id=message.object.peer_id,
                    conversation_message_ids=duel["message_id"],
                    group_id=message.group_id
                )
                items = json.loads(x_resp.json()).get('items', [])
                if items:
                    x_text = items[0]['text']
                    await bot.api.messages.edit(
                        peer_id=message.object.peer_id,
                        message=x_text,
                        conversation_message_id=duel["message_id"],
                        keyboard=None
                    )
                    print("[join_duel] Кнопки успешно убраны")
            except Exception as e:
                print(f"[join_duel] Ошибка при удалении кнопок: {e}")

            # Отправляем результат
            await bot.api.messages.send(
                peer_id=message.object.peer_id,
                message=(
                    f"💥 Дуэль завершена!\n\n"
                    f"[id{winner}|{w_name}] vs [id{loser}|{l_name}]\n"
                    f"👑 Победитель: [id{winner}|{w_name}]\n\n"
                    f"💰 Он забирает {format_number(stake)}$"
                ),
                random_id=0
            )
            duels.pop(peer, None)
            save_data(DUELS_FILE, duels)
            print("[join_duel] Результат отправлен")

            duels.pop(peer, None)
            save_data(DUELS_FILE, duels)
            print(f"[join_duel] Дуэль {peer} удалена из списка")
            return True

        except Exception as e:
            print(f"[join_duel] Общая ошибка: {e}")
            return True

    if command == "getban":
        target_user = payload.get("user")
        if not target_user:
            return True

        # Проверяем роль того, кто нажал кнопку
        role = await get_role(user_id, chat_id)
        if role < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps(
                    {"type": "show_snackbar", "text": "Недостаточно прав для просмотра информации о блокировках!"})
            )
            return True

        # Удаляем старое сообщение (кнопку)
        try:
            await bot.api.messages.delete(
                group_id=message.group_id,
                peer_id=message.object.peer_id,
                cmids=message.object.conversation_message_id,
                delete_for_all=True
            )
        except:
            pass

        # --- Получаем информацию о блокировках (код из команды /getban) ---
        # Глобальные баны
        sql.execute("SELECT * FROM gbanlist WHERE user_id = ?", (target_user,))
        gbanlist = sql.fetchone()
        sql.execute("SELECT * FROM globalban WHERE user_id = ?", (target_user,))
        globalban = sql.fetchone()

        globalbans_chats = ""
        if globalban and gbanlist:
            gbanchats = f"@id{globalban[1]} (Модератор) | {globalban[2]} | {globalban[3]} МСК (UTC+3)"
            gban_str = f"@id{gbanlist[1]} (Модератор) | {gbanlist[2]} | {gbanlist[3]} МСК (UTC+3)"
            globalbans_chats = f"Информация об общей блокировке в беседах:\n{gbanchats}\n\nИнформация о блокировке в беседах игроков:\n{gban_str}"
        elif globalban:
            gbanchats = f"@id{globalban[1]} (Модератор) | {globalban[2]} | {globalban[3]} МСК (UTC+3)"
            globalbans_chats = f"Информация об общей блокировке в беседах:\n{gbanchats}"
        elif gbanlist:
            gban_str = f"@id{gbanlist[1]} (Модератор) | {gbanlist[2]} | {gbanlist[3]} МСК (UTC+3)"
            globalbans_chats = f"Информация о блокировке в беседах игроков:\n{gban_str}"
        else:
            globalbans_chats = "Блокировка во всех беседах — отсутствует\nБлокировка в беседах игроков — отсутствует"

        # Баны в чатах
        sql.execute("SELECT chat_id FROM chats")
        chats_list = sql.fetchall()
        bans = ""
        count_bans = 0
        i = 1
        for c in chats_list:
            chat_id_check = c[0]
            try:
                sql.execute(f"SELECT moder, reason, date FROM bans_{chat_id_check} WHERE user_id = ?", (target_user,))
                user_bans = sql.fetchall()
                if user_bans:
                    rel_id = 2000000000 + chat_id_check
                    try:
                        resp = await bot.api.messages.get_conversations_by_id(peer_ids=rel_id)
                        if resp.items:
                            chat_title = resp.items[0].chat_settings.title or "Без названия"
                        else:
                            chat_title = "Без названия"
                    except:
                        chat_title = "Ошибка получения названия"

                    count_bans += 1
                    for ub in user_bans:
                        mod, reason, date = ub
                        bans += f"{i}) {chat_title} | @id{mod} (Модератор) | {reason} | {date} МСК (UTC+3)\n"
                        i += 1
            except:
                continue

        if count_bans == 0:
            bans_chats = "Блокировки в беседах отсутствуют"
        else:
            bans_chats = f"Количество бесед, в которых заблокирован пользователь: {count_bans}\nИнформация о банах пользователя:\n{bans}"

        # Отправляем сообщение в чат
        user_name = await get_user_name(target_user, chat_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            random_id=0,
            message=(
                f"Информация о блокировках @id{target_user} (Пользователь):\n\n"
                f"{globalbans_chats}\n\n"
                f"{bans_chats}"
            ),
            disable_mentions=1
        )
        return True        

        if command == "kick_blacklisted":
            # Проверка прав — если меньше 7, показываем snackbar
            if await get_role(user_id, chat_id) < 7:
                try:
                    await bot.api.messages.send_message_event_answer(
                        event_id=message.object.event_id,
                        peer_id=message.object.peer_id,
                        user_id=message.object.user_id,
                        event_data=json.dumps({
                            "type": "show_snackbar",
                            "text": "Недостаточно прав!"
                        })
                    )
                except:
                    pass
                return True

            # Получаем пользователей из blacklist
            sql.execute("SELECT user_id FROM blacklist")
            blacklisted = sql.fetchall()
            if not blacklisted:
                try:
                    await bot.api.messages.edit(
                        peer_id=message.peer_id,
                        conversation_message_id=message.conversation_message_id,
                        message="Не удалось исключить ни одного пользователя из ЧСБ.",
                        keyboard=None
                    )
                except:
                    pass
                return True

            kicked_users = ""
            i = 1
            for user_ban in blacklisted:
                user_ban_id = user_ban[0]
                try:
                    await bot.api.messages.remove_chat_user(chat_id=chat_id, member_id=user_ban_id)
                    kicked_users += f"{i}. @id{user_ban_id} ({await get_user_name(user_ban_id, chat_id)})\n"
                    i += 1
                except:
                    pass  # если не удалось кикнуть — пропускаем

            # Убираем кнопку из исходного сообщения
            try:
                await bot.api.messages.edit(
                    peer_id=message.peer_id,
                    conversation_message_id=message.conversation_message_id,
                    message="Удаление пользователей в ЧСБ, завершено...",
                    keyboard=None
                )
            except:
                pass

            # Отправляем отчёт, если кого-то реально исключили
            if kicked_users:
                await bot.api.messages.send(
                    peer_id=message.peer_id,
                    random_id=0,
                    message=(
                        f"@id{user_id} ({await get_user_name(user_id, chat_id)}), "
                        f"исключил(-а) пользователей в ЧСБ:\n\n{kicked_users}"
                    ),
                    disable_mentions=1
                )
            else:
                await bot.api.messages.send(
                    peer_id=message.peer_id,
                    random_id=0,
                    message="Не удалось исключить ни одного пользователя из ЧСБ.",
                    disable_mentions=1
                )

            return True            

    if command == "blacklistminus":
        if await get_role(user_id, chat_id) < 9:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        page = payload.get("page")
        if page < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это первая страница!"})
            )
            return True

        sql.execute("SELECT user_id, moderator_id, reason_gban, datetime_globalban FROM blacklist ORDER BY datetime_globalban DESC")
        all_rows = sql.fetchall()
        total = len(all_rows)
        per_page = 20
        max_page = (total + per_page - 1) // per_page       

        async def get_page(page):
            start = (page - 1) * per_page
            end = start + per_page
            data = all_rows[start:end]
            formatted = []
            for i, (uid, mid, reason, date) in enumerate(data, start=start + 1):
                formatted.append(f"{i}. @id{uid} | Модератор: @id{mid} | Причина: {reason} | Дата: {date}")
            return formatted

        new_page = page - 1
        users = await get_page(new_page)
        text = "\n".join(users) if users else "Нет данных."

        keyboard = (
            Keyboard(inline=True)
            .add(Callback("⏪", {"command": "blacklistminus", "page": new_page}), color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("⏩", {"command": "blacklistplus", "page": new_page}), color=KeyboardButtonColor.POSITIVE)
        )

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            message=f"Список пользователей в черном списке бота (страница {new_page}/{max_page}):\n\n{text}",
            disable_mentions=1, random_id=0, keyboard=keyboard
        )
        return True


    if command == "blacklistplus":
        if await get_role(user_id, chat_id) < 9:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        page = payload.get("page")

        sql.execute("SELECT user_id, moderator_id, reason_gban, datetime_globalban FROM blacklist ORDER BY datetime_globalban DESC")
        all_rows = sql.fetchall()
        total = len(all_rows)
        per_page = 20
        max_page = (total + per_page - 1) // per_page

        async def get_page(page):
            start = (page - 1) * per_page
            end = start + per_page
            data = all_rows[start:end]
            formatted = []
            for i, (uid, mid, reason, date) in enumerate(data, start=start + 1):
                formatted.append(f"{i}. @id{uid} | Модератор: @id{mid} | Причина: {reason} | Дата: {date}")
            return formatted

        new_page = page + 1
        users = await get_page(new_page)
        if page >= total:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это последняя страница!"})
            )
            return True

        text = "\n".join(users)
        keyboard = (
            Keyboard(inline=True)
            .add(Callback("⏪", {"command": "blacklistminus", "page": new_page}), color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("⏩", {"command": "blacklistplus", "page": new_page}), color=KeyboardButtonColor.POSITIVE)
        )

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            message=f"Список пользователей в черном списке бота (страница {new_page}/{max_page}):\n\n{text}",
            disable_mentions=1, random_id=0, keyboard=keyboard
        )
        return True


    if command == "gbanlistminus":
        if await get_role(user_id, chat_id) < 8:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        page = payload.get("page")
        if page < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это первая страница!"})
            )
            return True

        sql.execute("SELECT user_id, moderator_id, reason_gban, datetime_globalban FROM gbanlist UNION SELECT user_id, moderator_id, reason_gban, datetime_globalban FROM globalban ORDER BY datetime_globalban DESC")
        all_rows = sql.fetchall()
        total = len(all_rows)
        per_page = 20
        max_page = (total + per_page - 1) // per_page

        async def get_page(page):
            start = (page - 1) * per_page
            end = start + per_page
            data = all_rows[start:end]
            formatted = []
            for i, (uid, mid, reason, date) in enumerate(data, start=start + 1):
                formatted.append(f"{i}. @id{uid} | Модератор: @id{mid} | Причина: {reason} | Дата: {date}")
            return formatted

        new_page = page - 1
        users = await get_page(new_page)
        text = "\n".join(users) if users else "Нет данных."

        keyboard = (
            Keyboard(inline=True)
            .add(Callback("⏪", {"command": "gbanlistminus", "page": new_page}), color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("⏩", {"command": "gbanlistplus", "page": new_page}), color=KeyboardButtonColor.POSITIVE)
        )

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            message=f"Список пользователей в глобальной блокировке (страница {new_page}/{max_page}):\n\n{text}",
            disable_mentions=1, random_id=0, keyboard=keyboard
        )
        return True


    if command == "gbanlistplus":
        if await get_role(user_id, chat_id) < 8:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        page = payload.get("page")

        sql.execute("SELECT user_id, moderator_id, reason_gban, datetime_globalban FROM gbanlist UNION SELECT user_id, moderator_id, reason_gban, datetime_globalban FROM globalban ORDER BY datetime_globalban DESC")
        all_rows = sql.fetchall()
        total = len(all_rows)
        per_page = 20
        max_page = (total + per_page - 1) // per_page

        async def get_page(page):
            start = (page - 1) * per_page
            end = start + per_page
            data = all_rows[start:end]
            formatted = []
            for i, (uid, mid, reason, date) in enumerate(data, start=start + 1):
                formatted.append(f"{i}. @id{uid} | Модератор: @id{mid} | Причина: {reason} | Дата: {date}")
            return formatted

        new_page = page + 1
        users = await get_page(new_page)
        if page >= total:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это последняя страница!"})
            )
            return True

        text = "\n".join(users)
        keyboard = (
            Keyboard(inline=True)
            .add(Callback("⏪", {"command": "gbanlistminus", "page": new_page}), color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("⏩", {"command": "gbanlistplus", "page": new_page}), color=KeyboardButtonColor.POSITIVE)
        )

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            message=f"Список пользователей в глобальной блокировке (страница {new_page}/{max_page}):\n\n{text}",
            disable_mentions=1, random_id=0, keyboard=keyboard
        )
        return True

    if command == "infoidminus":
        page = payload.get("page")
        target = payload.get("user")

        if await get_role(user_id, chat_id) < 10:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        if page < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это первая страница!"})
            )
            return True

        sql.execute("SELECT chat_id FROM chats WHERE owner_id = ?", (target,))
        user_chats = sql.fetchall()
        per_page = 5
        start = (page - 2) * per_page
        end = start + per_page
        page_chats = user_chats[start:end]

        all_chats = []
        for idx, (chat_id_val,) in enumerate(page_chats, start=1):
            try:
                peer_id = 2000000000 + chat_id_val
                info = await bot.api.messages.get_conversations_by_id(peer_ids=peer_id)
                if info.items:
                    chat_title = info.items[0].chat_settings.title
                else:
                    chat_title = "Без названия"
                link = (await bot.api.messages.get_invite_link(peer_id=peer_id, reset=0)).link
            except:
                chat_title = "Не удалось получить"
                link = "Не удалось получить"

            all_chats.append(f"{idx}. {chat_title} | 🆔: {chat_id_val} | 🔗 Ссылка: {link}")

        keyboard = (
            Keyboard(inline=True)
            .add(Callback("Назад", {"command": "infoidMinus", "page": page - 1, "user": target}), color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("Вперёд", {"command": "infoidPlus", "page": page - 1, "user": target}), color=KeyboardButtonColor.POSITIVE)
        )

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        all_chats_text = "\n".join(all_chats)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            message=f"❗ Список бесед @id{target} (пользователя):\n(Страница: {page - 1})\n\n{all_chats_text}\n\n🗨️ Всего бесед у пользователя: {idx}",
            random_id=0,
            disable_mentions=1,
            keyboard=keyboard
        )

    if command == "modersallminus":
        if await get_role(user_id, chat_id) < 8:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        page = payload.get("page")

        if page < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это первая страница!"})
            )
            return True

        sql.execute("SELECT * FROM logchats ORDER BY rowid DESC LIMIT 9999999999999")
        logs = sql.fetchall()

        total = len(logs)
        per_page = MAX_LOGS
        max_page = (total + per_page - 1) // per_page

        async def get_moders_page(page: int):
            start = (page - 1) * per_page
            end = start + per_page
            selected = logs[start:end]
            formatted = []
            for idx, entry in enumerate(selected, start=start + 1):
                u_id, t_id, amount, log_text = entry

                try:
                    u_info = await bot.api.users.get(user_ids=u_id)
                    u_name = f"{u_info[0].first_name} {u_info[0].last_name}"
                except:
                    u_name = str(u_id)

                if t_id:
                    try:
                        t_info = await bot.api.users.get(user_ids=t_id)
                        t_name = f"{t_info[0].first_name} {t_info[0].last_name}"
                        t_display = f"@id{t_id} ({t_name})"
                    except:
                        t_display = f"@id{t_id}"
                else:
                    t_display = "None"

                a_display = f"{format_number(amount)}$" if amount else "None"
                l_display = log_text if log_text else "—"

                formatted.append(f"{idx}. @id{u_id} ({u_name}) | Кому: {t_display} | Роль: {a_display} | Лог: {l_display}")
            return formatted

        new_page = page - 1
        moders_page = await get_moders_page(new_page)
        moders_text = "\n\n".join(moders_page)

        keyboard = (
            Keyboard(inline=True)
            .add(Callback("⏪", {"command": "modersAllMinus", "page": new_page}), color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("⏩", {"command": "modersAllPlus", "page": new_page}), color=KeyboardButtonColor.POSITIVE)
        )

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            message=f"Общие логи модерации [{new_page}/{max_page}]:\n\n{moders_text}",
            disable_mentions=1, random_id=0, keyboard=keyboard
        )
        return True

    if command == "modersallplus":
        if await get_role(user_id, chat_id) < 8:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        page = payload.get("page")

        sql.execute("SELECT * FROM logchats ORDER BY rowid DESC LIMIT 9999999999999")
        logs = sql.fetchall()

        total = len(logs)
        per_page = MAX_LOGS
        max_page = (total + per_page - 1) // per_page

        async def get_moders_page(page: int):
            start = (page - 1) * per_page
            end = start + per_page
            selected = logs[start:end]
            formatted = []
            for idx, entry in enumerate(selected, start=start + 1):
                u_id, t_id, amount, log_text = entry

                try:
                    u_info = await bot.api.users.get(user_ids=u_id)
                    u_name = f"{u_info[0].first_name} {u_info[0].last_name}"
                except:
                    u_name = str(u_id)

                if t_id:
                    try:
                        t_info = await bot.api.users.get(user_ids=t_id)
                        t_name = f"{t_info[0].first_name} {t_info[0].last_name}"
                        t_display = f"@id{t_id} ({t_name})"
                    except:
                        t_display = f"@id{t_id}"
                else:
                    t_display = "None"

                a_display = f"{format_number(amount)}$" if amount else "None"
                l_display = log_text if log_text else "—"

                formatted.append(f"{idx}. @id{u_id} ({u_name}) | Кому: {t_display} | Роль: {a_display} | Лог: {l_display}")
            return formatted

        new_page = page + 1
        moders_page = await get_moders_page(new_page)
        if len(moders_page) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это последняя страница!"})
            )
            return True

        moders_text = "\n\n".join(moders_page)

        keyboard = (
            Keyboard(inline=True)
            .add(Callback("⏪", {"command": "modersAllMinus", "page": new_page}), color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("⏩", {"command": "modersAllPlus", "page": new_page}), color=KeyboardButtonColor.POSITIVE)
        )

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            message=f"Общие логи модерации [{new_page}/{max_page}]:\n\n{moders_text}",
            disable_mentions=1, random_id=0, keyboard=keyboard
        )
        return True
        
    if command == "modersminus":
        if await get_role(user_id, chat_id) < 8:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        page = payload.get("page")
        target = payload.get("target")

        if page < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это первая страница!"})
            )
            return True

        if target:
            sql.execute("SELECT * FROM logchats WHERE user_id = ? ORDER BY rowid DESC LIMIT 9999999999999", (target,))
            logs = sql.fetchall()
        else:
            sql.execute("SELECT * FROM logchats ORDER BY rowid DESC LIMIT 9999999999999")
            logs = sql.fetchall()

        total = len(logs)
        per_page = MAX_LOGS
        max_page = (total + per_page - 1) // per_page

        async def get_moders_page(page: int):
            start = (page - 1) * per_page
            end = start + per_page
            selected = logs[start:end]
            formatted = []
            for idx, entry in enumerate(selected, start=start + 1):
                u_id, t_id, amount, log_text = entry

                try:
                    u_info = await bot.api.users.get(user_ids=u_id)
                    u_name = f"{u_info[0].first_name} {u_info[0].last_name}"
                except:
                    u_name = str(u_id)

                if t_id:
                    try:
                        t_info = await bot.api.users.get(user_ids=t_id)
                        t_name = f"{t_info[0].first_name} {t_info[0].last_name}"
                        t_display = f"@id{t_id} ({t_name})"
                    except:
                        t_display = f"@id{t_id}"
                else:
                    t_display = "None"

                a_display = f"{format_number(amount)}$" if amount else "None"
                l_display = log_text if log_text else "—"

                formatted.append(f"{idx}. @id{u_id} ({u_name}) | Кому: {t_display} | Роль: {a_display} | Лог: {l_display}")
            return formatted

        new_page = page - 1
        moders_page = await get_moders_page(new_page)
        moders_text = "\n\n".join(moders_page)

        if target:
            keyboard = (
                Keyboard(inline=True)
                .add(Callback("⏪", {"command": "modersMinus", "target": target, "page": new_page}), color=KeyboardButtonColor.NEGATIVE)
                .add(Callback("⏩", {"command": "modersPlus", "target": target, "page": new_page}), color=KeyboardButtonColor.POSITIVE)
            )
            message_text = f"Логи модерации @id{target} ({await get_user_name(target, chat_id)}) [{new_page}/{max_page}]:\n\n{moders_text}"
        else:
            keyboard = (
                Keyboard(inline=True)
                .add(Callback("⏪", {"command": "modersAllMinus", "page": new_page}), color=KeyboardButtonColor.NEGATIVE)
                .add(Callback("⏩", {"command": "modersAllPlus", "page": new_page}), color=KeyboardButtonColor.POSITIVE)
            )
            message_text = f"Общие логи модерации [{new_page}/{max_page}]:\n\n{moders_text}"

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            message=message_text,
            disable_mentions=1, random_id=0, keyboard=keyboard
        )
        return True

    if command == "modersplus":
        if await get_role(user_id, chat_id) < 8:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        page = payload.get("page")
        target = payload.get("target")

        if target:
            sql.execute("SELECT * FROM logchats WHERE user_id = ? ORDER BY rowid DESC LIMIT 9999999999999", (target,))
            logs = sql.fetchall()
        else:
            sql.execute("SELECT * FROM logchats ORDER BY rowid DESC LIMIT 9999999999999")
            logs = sql.fetchall()

        total = len(logs)
        per_page = MAX_LOGS
        max_page = (total + per_page - 1) // per_page

        async def get_moders_page(page: int):
            start = (page - 1) * per_page
            end = start + per_page
            selected = logs[start:end]
            formatted = []
            for idx, entry in enumerate(selected, start=start + 1):
                u_id, t_id, amount, log_text = entry

                try:
                    u_info = await bot.api.users.get(user_ids=u_id)
                    u_name = f"{u_info[0].first_name} {u_info[0].last_name}"
                except:
                    u_name = str(u_id)

                if t_id:
                    try:
                        t_info = await bot.api.users.get(user_ids=t_id)
                        t_name = f"{t_info[0].first_name} {t_info[0].last_name}"
                        t_display = f"@id{t_id} ({t_name})"
                    except:
                        t_display = f"@id{t_id}"
                else:
                    t_display = "None"

                a_display = f"{format_number(amount)}$" if amount else "None"
                l_display = log_text if log_text else "—"

                formatted.append(f"{idx}. @id{u_id} ({u_name}) | Кому: {t_display} | Роль: {a_display} | Лог: {l_display}")
            return formatted

        new_page = page + 1
        moders_page = await get_moders_page(new_page)
        if len(moders_page) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это последняя страница!"})
            )
            return True

        moders_text = "\n\n".join(moders_page)

        if target:
            keyboard = (
                Keyboard(inline=True)
                .add(Callback("⏪", {"command": "modersMinus", "target": target, "page": new_page}), color=KeyboardButtonColor.NEGATIVE)
                .add(Callback("⏩", {"command": "modersPlus", "target": target, "page": new_page}), color=KeyboardButtonColor.POSITIVE)
            )
            message_text = f"Логи модерации @id{target} ({await get_user_name(target, chat_id)}) [{new_page}/{max_page}]:\n\n{moders_text}"
        else:
            keyboard = (
                Keyboard(inline=True)
                .add(Callback("⏪", {"command": "modersAllMinus", "page": new_page}), color=KeyboardButtonColor.NEGATIVE)
                .add(Callback("⏩", {"command": "modersAllPlus", "page": new_page}), color=KeyboardButtonColor.POSITIVE)
            )
            message_text = f"Общие логи модерации [{new_page}/{max_page}]:\n\n{moders_text}"

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            message=message_text,
            disable_mentions=1, random_id=0, keyboard=keyboard
        )
        return True        

    if command == "economyminus":
        if await get_role(user_id, chat_id) < 8:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        page = payload.get("page")
        target = payload.get("target")

        if page < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это первая страница!"})
            )
            return True

        if target:
            sql.execute("SELECT * FROM economy WHERE user_id = ? ORDER BY rowid DESC LIMIT 9999999999999", (target,))
            logs = sql.fetchall()
        else:
            sql.execute("SELECT * FROM economy ORDER BY rowid DESC LIMIT 9999999999999")
            logs = sql.fetchall()

        total = len(logs)
        per_page = MAX_LOGS
        max_page = (total + per_page - 1) // per_page

        async def get_economy_page(page: int):
            start = (page - 1) * per_page
            end = start + per_page
            selected = logs[start:end]
            formatted = []
            for idx, entry in enumerate(selected, start=start + 1):
                u_id, t_id, amount, log_text = entry

                try:
                    u_info = await bot.api.users.get(user_ids=u_id)
                    u_name = f"{u_info[0].first_name} {u_info[0].last_name}"
                except:
                    u_name = str(u_id)

                if t_id:
                    try:
                        t_info = await bot.api.users.get(user_ids=t_id)
                        t_name = f"{t_info[0].first_name} {t_info[0].last_name}"
                        t_display = f"@id{t_id} ({t_name})"
                    except:
                        t_display = f"@id{t_id}"
                else:
                    t_display = "None"

                a_display = f"{format_number(amount)}$" if amount else "None"
                l_display = log_text if log_text else "—"

                formatted.append(f"{idx}. @id{u_id} ({u_name}) | Кому: {t_display} | Сколько: {a_display} | Лог: {l_display}")
            return formatted

        new_page = page - 1
        economy_page = await get_economy_page(new_page)
        economy_text = "\n\n".join(economy_page)

        if target:
            keyboard = (
                Keyboard(inline=True)
                .add(Callback("⏪", {"command": "economyMinus", "target": target, "page": new_page}), color=KeyboardButtonColor.NEGATIVE)
                .add(Callback("⏩", {"command": "economyPlus", "target": target, "page": new_page}), color=KeyboardButtonColor.POSITIVE)
            )
            message_text = f"Логи экономики @id{target} ({await get_user_name(target, chat_id)}) [{new_page}/{max_page}]:\n\n{economy_text}"
        else:
            keyboard = (
                Keyboard(inline=True)
                .add(Callback("⏪", {"command": "economyAllMinus", "page": new_page}), color=KeyboardButtonColor.NEGATIVE)
                .add(Callback("⏩", {"command": "economyAllPlus", "page": new_page}), color=KeyboardButtonColor.POSITIVE)
            )
            message_text = f"Общие логи экономики [{new_page}/{max_page}]:\n\n{economy_text}"

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            message=message_text,
            disable_mentions=1, random_id=0, keyboard=keyboard
        )
        return True

    if command == "economyplus":
        if await get_role(user_id, chat_id) < 8:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        page = payload.get("page")
        target = payload.get("target")

        if target:
            sql.execute("SELECT * FROM economy WHERE user_id = ? ORDER BY rowid DESC LIMIT 9999999999999", (target,))
            logs = sql.fetchall()
        else:
            sql.execute("SELECT * FROM economy ORDER BY rowid DESC LIMIT 9999999999999")
            logs = sql.fetchall()

        total = len(logs)
        per_page = MAX_LOGS
        max_page = (total + per_page - 1) // per_page

        async def get_economy_page(page: int):
            start = (page - 1) * per_page
            end = start + per_page
            selected = logs[start:end]
            formatted = []
            for idx, entry in enumerate(selected, start=start + 1):
                u_id, t_id, amount, log_text = entry

                try:
                    u_info = await bot.api.users.get(user_ids=u_id)
                    u_name = f"{u_info[0].first_name} {u_info[0].last_name}"
                except:
                    u_name = str(u_id)

                if t_id:
                    try:
                        t_info = await bot.api.users.get(user_ids=t_id)
                        t_name = f"{t_info[0].first_name} {t_info[0].last_name}"
                        t_display = f"@id{t_id} ({t_name})"
                    except:
                        t_display = f"@id{t_id}"
                else:
                    t_display = "None"

                a_display = f"{format_number(amount)}$" if amount else "None"
                l_display = log_text if log_text else "—"

                formatted.append(f"{idx}. @id{u_id} ({u_name}) | Кому: {t_display} | Сколько: {a_display} | Лог: {l_display}")
            return formatted

        new_page = page + 1
        economy_page = await get_economy_page(new_page)
        if len(economy_page) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это последняя страница!"})
            )
            return True

        economy_text = "\n\n".join(economy_page)

        if target:
            keyboard = (
                Keyboard(inline=True)
                .add(Callback("⏪", {"command": "economyMinus", "target": target, "page": new_page}), color=KeyboardButtonColor.NEGATIVE)
                .add(Callback("⏩", {"command": "economyPlus", "target": target, "page": new_page}), color=KeyboardButtonColor.POSITIVE)
            )
            message_text = f"Логи экономики @id{target} ({await get_user_name(target, chat_id)}) [{new_page}/{max_page}]:\n\n{economy_text}"
        else:
            keyboard = (
                Keyboard(inline=True)
                .add(Callback("⏪", {"command": "economyAllMinus", "page": new_page}), color=KeyboardButtonColor.NEGATIVE)
                .add(Callback("⏩", {"command": "economyAllPlus", "page": new_page}), color=KeyboardButtonColor.POSITIVE)
            )
            message_text = f"Общие логи экономики [{new_page}/{max_page}]:\n\n{economy_text}"

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            message=message_text,
            disable_mentions=1, random_id=0, keyboard=keyboard
        )
        return True
        
    if command == "economyallminus":
        if await get_role(user_id, chat_id) < 8:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        page = payload.get("page")

        if page < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это первая страница!"})
            )
            return True

        sql.execute("SELECT * FROM economy ORDER BY rowid DESC LIMIT 9999999999999")
        logs = sql.fetchall()

        total = len(logs)
        per_page = MAX_LOGS
        max_page = (total + per_page - 1) // per_page

        async def get_economy_page(page: int):
            start = (page - 1) * per_page
            end = start + per_page
            selected = logs[start:end]
            formatted = []
            for idx, entry in enumerate(selected, start=start + 1):
                u_id, t_id, amount, log_text = entry

                try:
                    u_info = await bot.api.users.get(user_ids=u_id)
                    u_name = f"{u_info[0].first_name} {u_info[0].last_name}"
                except:
                    u_name = str(u_id)

                if t_id:
                    try:
                        t_info = await bot.api.users.get(user_ids=t_id)
                        t_name = f"{t_info[0].first_name} {t_info[0].last_name}"
                        t_display = f"@id{t_id} ({t_name})"
                    except:
                        t_display = f"@id{t_id}"
                else:
                    t_display = "None"

                a_display = f"{format_number(amount)}$" if amount else "None"
                l_display = log_text if log_text else "—"

                formatted.append(f"{idx}. @id{u_id} ({u_name}) | Кому: {t_display} | Сколько: {a_display} | Лог: {l_display}")
            return formatted

        new_page = page - 1
        economy_page = await get_economy_page(new_page)
        economy_text = "\n\n".join(economy_page)

        keyboard = (
            Keyboard(inline=True)
            .add(Callback("⏪", {"command": "economyAllMinus", "page": new_page}), color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("⏩", {"command": "economyAllPlus", "page": new_page}), color=KeyboardButtonColor.POSITIVE)
        )

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            message=f"Общие логи экономики [{new_page}/{max_page}]:\n\n{economy_text}",
            disable_mentions=1, random_id=0, keyboard=keyboard
        )
        return True

    if command == "economyallplus":
        if await get_role(user_id, chat_id) < 8:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        page = payload.get("page")

        sql.execute("SELECT * FROM economy ORDER BY rowid DESC LIMIT 9999999999999")
        logs = sql.fetchall()

        total = len(logs)
        per_page = MAX_LOGS
        max_page = (total + per_page - 1) // per_page

        async def get_economy_page(page: int):
            start = (page - 1) * per_page
            end = start + per_page
            selected = logs[start:end]
            formatted = []
            for idx, entry in enumerate(selected, start=start + 1):
                u_id, t_id, amount, log_text = entry

                try:
                    u_info = await bot.api.users.get(user_ids=u_id)
                    u_name = f"{u_info[0].first_name} {u_info[0].last_name}"
                except:
                    u_name = str(u_id)

                if t_id:
                    try:
                        t_info = await bot.api.users.get(user_ids=t_id)
                        t_name = f"{t_info[0].first_name} {t_info[0].last_name}"
                        t_display = f"@id{t_id} ({t_name})"
                    except:
                        t_display = f"@id{t_id}"
                else:
                    t_display = "None"

                a_display = f"{format_number(amount)}$" if amount else "None"
                l_display = log_text if log_text else "—"

                formatted.append(f"{idx}. @id{u_id} ({u_name}) | Кому: {t_display} | Сколько: {a_display} | Лог: {l_display}")
            return formatted

        new_page = page + 1
        economy_page = await get_economy_page(new_page)
        if len(economy_page) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это последняя страница!"})
            )
            return True

        economy_text = "\n\n".join(economy_page)

        keyboard = (
            Keyboard(inline=True)
            .add(Callback("⏪", {"command": "economyAllMinus", "page": new_page}), color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("⏩", {"command": "economyAllPlus", "page": new_page}), color=KeyboardButtonColor.POSITIVE)
        )

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            message=f"Общие логи экономики [{new_page}/{max_page}]:\n\n{economy_text}",
            disable_mentions=1, random_id=0, keyboard=keyboard
        )
        return True        
        
    if command == "infoidplus":
        page = payload.get("page")
        target = payload.get("user")

        if await get_role(user_id, chat_id) < 10:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        sql.execute("SELECT chat_id FROM chats WHERE owner_id = ?", (target,))
        user_chats = sql.fetchall()
        per_page = 5
        total_pages = (len(user_chats) + per_page - 1) // per_page

        if page >= total_pages:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это последняя страница!"})
            )
            return True

        start = page * per_page
        end = start + per_page
        page_chats = user_chats[start:end]

        all_chats = []
        for idx, (chat_id_val,) in enumerate(page_chats, start=1):
            try:
                peer_id = 2000000000 + chat_id_val
                info = await bot.api.messages.get_conversations_by_id(peer_ids=peer_id)
                if info.items:
                    chat_title = info.items[0].chat_settings.title
                else:
                    chat_title = "Без названия"
                link = (await bot.api.messages.get_invite_link(peer_id=peer_id, reset=0)).link
            except:
                chat_title = "Не удалось получить"
                link = "Не удалось получить"

            all_chats.append(f"{idx}. {chat_title} | 🆔: {chat_id_val} | 🔗 Ссылка: {link}")

        keyboard = (
            Keyboard(inline=True)
            .add(Callback("Назад", {"command": "infoidMinus", "page": page + 1, "user": target}), color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("Вперёд", {"command": "infoidPlus", "page": page + 1, "user": target}), color=KeyboardButtonColor.POSITIVE)
        )

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        all_chats_text = "\n".join(all_chats)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            message=f"❗ Список бесед @id{target} (пользователя):\n(Страница: {page + 1})\n\n{all_chats_text}\n\nВсего бесед: {idx}",
            random_id=0,
            disable_mentions=1,
            keyboard=keyboard
        )        
              
    if command == "alt":
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        commands_levels = {
            1: [
                '\nКоманды модераторов:',
                '/setnick — snick, nick, addnick, ник, сетник, аддник',
                '/removenick —  removenick, clearnick, cnick, рник, удалитьник, снятьник',
                '/getnick — gnick, гник, гетник',
                '/getacc — acc, гетакк, аккаунт, account',
                '/nlist — ники, всеники, nlist, nickslist, nicklist, nicks',
                '/nonick — nonicks, nonicklist, nolist, nnlist, безников, ноникс',
                '/kick — кик, исключить',
                '/warn — пред, варн, pred, предупреждение',
                '/unwarn — унварн, анварн, снятьпред, минуспред',
                '/getwarn — gwarn, getwarns, гетварн, гварн',
                '/warnhistory — historywarns, whistory, историяварнов, историяпредов',
                '/warnlist — warns, wlist, варны, варнлист',
                '/staff — стафф',
                '/reg — registration, regdate, рег, регистрация, датарегистрации',
                '/mute — мут, мьют, муте, addmute',
                '/unmute — снятьмут, анмут, унмут, снятьмут',
                '/alt — альт, альтернативные',
                '/getmute -- gmute, гмут, гетмут, чекмут',
                '/mutelist -- mutes, муты, мутлист',
                '/clear -- чистка, очистить, очистка',
                '/getban -- чекбан, гетбан, checkban',
                '/delete -- удалить',
                '/chatid -- чатайди, айдичата'
            ],
            2: [
                '\nКоманды старших модераторов:',
                '/ban — бан, блокировка',
                '/unban -- унбан, снятьбан',
                '/addmoder -- moder, модер',
                '/removerole -- rrole, снятьроль',
                '/zov - зов, вызов',
                '/online - ozov, озов',
                '/onlinelist - olist, олист',
                '/banlist - bans, банлист, баны',
                '/inactive - ilist, inactive'
            ],
            3: [
                '\nКоманды администраторов:',
                '/quiet -- silence, тишина',
                '/skick -- скик, снят',
                '/sban -- сбан',
                '/sunban — сунбан, санбан',
                '/addsenmoder — senmoder, смодер',
                '/rnickall -- allrnick, arnick, mrnick',
                '/sremovenick -- srnick',
                '/szov -- serverzov, сзов',
                '/srole -- none',
                '/ssetnick -- ssnick, ссник'
            ],
            4: [
                '\nКоманды старших администраторов:',
                '/addadmin -- admin, админ',
                '/serverinfo -- серверинфо',
                '/filter -- none',
                '/sremoverole -- srrole',
                '/bug -- баг',
                '/report -- реп, rep, жалоба'
            ],
            5: [
                '\nКоманды зам. спец. администраторов:',
                '/addsenadmin -- senadm, addsenadm, senadmin, садмин',
                '/sync -- синхронизация, сунс, синхронка',
                '/pin -- закрепить, пин',
                '/unpin -- открепить, унпин',
                '/deleteall -- удалитьвсе',
                '/gsinfo -- none',
                '/gsrnick -- none',
                '/gssnick -- none',
                '/gskick -- none',
                '/gsban -- none',
                '/gsunban -- none'
            ],
            6: [
                '\nКоманды спец. администраторов:',
                '/addzsa -- zsa, зса',
                '/server -- сервер',
                '/settings -- настройки',
                '/clearwarn -- очиститьварны',
                '/title -- none',
                '/antisliv -- антислив'
            ],
            7: [
                '\nСписок команд владельца беседы',
                '/addsa -- sa, са, spec, specadm',
                '/antiflood -- af',
                '/welcometext -- welcome, wtext',
                '/invite -- none',
                '/leave -- none',
                '/editowner -- owner',
                '/защита -- protection',
                '/settingsmute -- настройкимута',
                '/setinfo -- установитьинфо',
                '/setrules -- установитьправила',
                '/type -- тип',
                '/gsync -- привязка',
                '/gunsync -- удалитьпривязку',
                '/masskick - mkick',
                '/amnesty -- амнистия',
                '/settingsgame -- настройкиигр',
                '/settingsphoto -- настройкифото'
            ]
        }

        user_role = await get_role(user_id, chat_id)

        commands = []
        for i in commands_levels.keys():
            if i <= user_role:
                for b in commands_levels[i]:
                    commands.append(b)

        level_commands = '\n'.join(commands)

        await bot.api.messages.edit(peer_id=2000000000 + chat_id, message=f"Альтернативные команды\n\n{level_commands}",
                                    conversation_message_id=message.object.conversation_message_id, keyboard=None)
                                                                       
@bot.on.chat_message()
async def on_chat_message(message: Message):
    global balances
    bot_identifiers = ['!', '+', '/']

    user_id = message.from_id
    chat_id = message.chat_id
    peer_id = message.peer_id
    arguments = message.text.split(' ')
    args = message.text.split(' ')
    arguments_lower = message.text.lower().split(' ')
    args_lower = message.text.lower().split(' ')
    userf = f'@id{user_id} ({await get_user_name(user_id, chat_id)})'

    # --- Проверка на бан чата до всего остального ---
    sql.execute("SELECT chat_id FROM banschats WHERE chat_id = ?", (chat_id,))
    if sql.fetchone():
        await message.reply("Владелец беседы, не член BANANA MANAGER! Я не буду здесь работать.")
        return True

    # --- Проверка, зарегистрирован ли чат ---
    is_registered = await check_chat(chat_id)
    if is_registered and user_id > 0:
        try:
            await sync_user_business_income(user_id)
        except Exception as e:
            print(f"[BUSINESS AUTO SYNC] {e}")

    if is_registered and await check_quit(chat_id):
        if await get_role(user_id, chat_id) == 0:
            try:
                await bot.api.messages.delete(
                    group_id=message.group_id, 
                    peer_id=message.peer_id, 
                    delete_for_all=True, 
                    cmids=message.conversation_message_id
                )    
                return True
            except Exception as error:
                print(f"[QUIET (/ТИШИНА)]:", error)
        else:
            pass       

    if is_registered and message.attachments and any(attach.type.value == 'photo' for attach in message.attachments):
        sql.execute("SELECT mode FROM photosettings WHERE chat_id = ?", (chat_id,))
        mode_data = sql.fetchone()
        mode = mode_data[0] if mode_data else 0

        if mode == 1:
            await message.reply(f"В данной беседе «№{chat_id}» запрещено отправлять фотографии!\n\nДанную настройку можно выключить в: «/settingsphoto»")
            await bot.api.messages.delete(
                group_id=message.group_id,
                peer_id=message.peer_id,
                delete_for_all=True,
                cmids=message.conversation_message_id
            )
            return True

    # --- Проверка на запрещённые слова ---
    if is_registered and await get_role(user_id, chat_id) <= 0:
        try:
            sql.execute("SELECT word FROM ban_words")
            banned_words = [row[0].lower() for row in sql.fetchall()]
            text_lower = message.text.lower()
            for word in banned_words:
                if word in text_lower:
                    admin = "bananamanagerbot"
                    reason = "Написание запрещенных слов"
                    mute_time = 30

                    await add_mute(user_id, chat_id, admin, reason, mute_time)

                    keyboard = (
                        Keyboard(inline=True)
                        .add(Callback("Снять мут", {"command": "unmute", "user": user_id, "chatId": chat_id}), color=KeyboardButtonColor.POSITIVE)
                    )

                    await message.replyLocalizedMessage('mute_is_banwords', {
                        'user': userf
                    })

                    await bot.api.messages.delete(
                        group_id=message.group_id,
                        peer_id=message.peer_id,
                        delete_for_all=True,
                        cmids=message.conversation_message_id
                    )
                    return True
        except Exception as e:
            print(f"[BANWORDS] Ошибка проверки слов: {e}")            

    # --- Проверка мута и реакции в зависимости от настроек (только если чат активирован) ---
    if is_registered and await get_mute(user_id, chat_id) and not await checkMute(chat_id, user_id):
        sql.execute("SELECT mode FROM mutesettings WHERE chat_id = ?", (chat_id,))
        mode_data = sql.fetchone()
        mode = mode_data[0] if mode_data else 0

        warns = await get_warns(user_id, chat_id)

        if mode == 1:
            if warns < 3:
                bot_name = "blackrussiamanagerbot"
                reason = "Написание слов в муте"
                await warn(chat_id, user_id, bot_name, reason)
                await message.replyLocalizedMessage('mute_is_warn', {
                    'user': userf,
                    'warns': warns                    
                })
                await bot.api.messages.delete(
                    group_id=message.group_id,
                    peer_id=message.peer_id,
                    delete_for_all=True,
                    cmids=message.conversation_message_id
                )
            else:
                try:
                    await bot.api.messages.remove_chat_user(chat_id, user_id)
                    await message.replyLocalizedMessage('limit_warns_kick', {
                        'user': userf
                    })
                    await clear_warns(chat_id, user_id)
                except:
                    await message.replyLocalizedMessage('not_this_kick', {
                        'user': f'@id{user_id} (пользователя)'
                    })
                    await clear_warns(chat_id, user_id)
        else:
            await bot.api.messages.delete(
                group_id=message.group_id,
                peer_id=message.peer_id,
                delete_for_all=True,
                cmids=message.conversation_message_id
            )

    # --- Проверка на наличие заблокированных пользователей (только если чат активирован) ---
    if is_registered:
        sql.execute("SELECT user_id FROM blacklist WHERE user_id = ?", (user_id,))
        blacklist_entry = sql.fetchone()
        if blacklist_entry:
            await message.reply("Вы в ЧСБ BANANA MANAGER, использование команд бота запрещено.", disable_mentions=1)
            return True
            return True

    # --- Теперь обрабатываем команды (команды доступны всегда) ---
    try:
        command_identifier = arguments[0].strip()[0]
        command = arguments_lower[0][1:]
    except:
        command_identifier = " "
        command = " "

    if command_identifier in bot_identifiers:
        if is_registered and get_block_game(chat_id) and command in GAME_COMMANDS and command not in ['settingsgame', 'настройкиигр']:
            await message.reply("В данной беседе запрещено использовать любые игровые команды!\n\nВыключить данную настройку можно в: «/settingsgame»")
            return True
        try:
            test_admin = await bot.api.messages.get_conversation_members(peer_id=message.peer_id)
        except:
            await message.replyLocalizedMessage('not_this_admin')            
            return True

        # --- Если чат не активирован, разрешаем только /start ---
        if not is_registered and command not in ['start', 'старт', 'активировать']:
            await message.replyLocalizedMessage('not_this_started')            
            return True

        # ==== Проверка глобального бана ====
        if is_registered:
            sql.execute("SELECT * FROM gbanlist WHERE user_id = ?", (user_id,))
            check_global = sql.fetchone()
            if check_global:
                moderator_id = check_global[1]
                reason_gban = check_global[2]
                datetime_globalban = check_global[3]

                try:
                    resp = await bot.api.users.get(user_ids=user_id)
                    full_name = f"{resp[0].first_name} {resp[0].last_name}"
                except:
                    full_name = str(user_id)

                await message.reply(
                    f"@id{user_id} ({full_name}) заблокирован(-а) в беседах игроков!\n\n"
                    f"Информация о блокировке:\n@id{moderator_id} (Модератор) | {reason_gban} | {datetime_globalban}",
                    disable_mentions=1,
                )
                await bot.api.messages.remove_chat_user(chat_id, user_id)
                return True
                
        # ==== Проверка глобального бана ====
        if is_registered:
            sql.execute("SELECT * FROM globalban WHERE user_id = ?", (user_id,))
            check_global = sql.fetchone()
            if check_global:
                moderator_id = check_global[1]
                reason_gban = check_global[2]
                datetime_globalban = check_global[3]

                try:
                    resp = await bot.api.users.get(user_ids=user_id)
                    full_name = f"{resp[0].first_name} {resp[0].last_name}"
                except:
                    full_name = str(user_id)

                await message.reply(
                    f"@id{user_id} ({full_name}) заблокирован(-а) во всех беседах!\n\n"
                    f"Информация о блокировке:\n@id{moderator_id} (Модератор) | {reason_gban} | {datetime_globalban}",
                    disable_mentions=1,
                )
                await bot.api.messages.remove_chat_user(chat_id, user_id)
                return True                
                                        
        if command in ['start', 'старт', 'активировать']:
            if await check_chat(chat_id):
                await message.reply("Бот был ранее активирован в данной беседе!", disable_mentions=1)
                return True
            await new_chat(chat_id, peer_id, user_id)
            await message.reply("Беседа успешно занесена в базу данных бота!\n\nИспользуйте «/help» для ознакомления списка команд!", disable_mentions=1)
            return True  

        # ---------------- FORM ----------------
        if command in ["form", "форма"]:
            if chat_id != 1:
                await message.reply(
                    "❗ Команда доступна только [https://vk.me/join/OuYg9/aZJxJdh/8hTaNzoqk543xct/EUk1g=|в формах на блокировку]"
                )
                return True

            # Определяем target
            target = None
            reason = "Не указано"
            if message.reply_message:
                target = message.reply_message.from_id
                if len(arguments) > 1:
                    reason = await get_string(arguments, 1)
            elif len(arguments) > 1 and await getID(arguments[1]):
                target = await getID(arguments[1])
                if len(arguments) > 2:
                    reason = await get_string(arguments, 2)
            else:
                await message.reply("Укажите пользователя через реплай или ID!")
                return True

            if target == bansids:
                await message.reply(f"Вы не можете подать форму на данного @id{target} (пользователя)")
                return True

            sender_name = await get_user_name(user_id, chat_id)
            target_name = await get_user_name(target, chat_id)
            name = datetime.now().strftime("%I:%M:%S %p")

            # Клавиатура с кнопками
            keyboard = (
                Keyboard(inline=True)
                .add(
                    Callback(
                        "Одобрить",
                        {"command": "approve_form", "target": target, "sender": user_id, "reason": reason},
                    ),
                    color=KeyboardButtonColor.POSITIVE,
                )
                .add(
                    Callback(
                        "Отказать",
                        {"command": "reject_form", "target": target, "sender": user_id, "reason": reason},
                    ),
                    color=KeyboardButtonColor.NEGATIVE,
                )
            )

            # Отправляем сообщение прямо в чат, откуда пришла команда
            await message.reply(
                (
                    f"📌 | Форма на «/gbanpl»:\n"
                    f"1. Пользователь: @id{user_id} ({sender_name})\n"
                    f"2. Нарушитель: @id{target} ({target_name})\n"
                    f"3. Причина: {reason}\n"
                    f"4. Дата подачи формы: {name} МСК (UTC+3)"
                ),
                keyboard=keyboard,
            )
            return True            

        if command in ['id', 'ид', 'getid', 'гетид', 'получитьид', 'giveid']:
            user = int
            if message.reply_message:
                user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
            else:
                user = user_id
            if user < 0:
                await message.replyLocalizedMessage('command_getid_group', {
                        'target': f'[club{abs(user)}|сообщества]',
                        'link': f'https://vk.ru/club{abs(user)}'
                    })
                return True
            await message.replyLocalizedMessage('command_getid_user', {
                        'target': f'@id{user} (пользователя)',
                        'link': f'https://vk.ru/id{user}'
                    })

        if message.reply_message and message.reply_message.from_id < 0:
            return True     

        # ---------------- OFFER ----------------
        if command in ["offer", "предложение"]:
            try:
                user_info = await bot.api.users.get(user_ids=user_id)
                full_name = f"{user_info[0].first_name} {user_info[0].last_name}"
            except:
                full_name = f"id{user_id} (Ошибка)"

            args = message.text.split(maxsplit=1)
            if len(arguments) < 2 or len(args[1]) < 5:
                await message.reply("Укажите предложение по улучшению!")
                return

            offer = args[1]

            ADMIN_ID = 488828183,574393629

            await bot.api.messages.send(
                peer_id=200000003,
                random_id=0,
                message=(
                    f"⭐ | Предложение по улучшению бота:\n"
                    f"1. Пользователь: [id{user_id}|{full_name}]\n"
                    f"2. Предложение по улучшению: {offer}"
                )
            )
            
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"подал(-а) предложение по улучшению с содержанием: «{offer}»")            
            await message.reply("Спасибо за предложение по улучшению бота! Мы обязательно рассмотрим ваше предложение.")
            return

        if command in ['логэкономики', 'logeco', 'logeconomy', 'логиэко']:
            if await get_role(user_id, chat_id) < 8 and await get_tech_role(user_id, chat_id) < 1:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            target = None
            if message.reply_message:
                target = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                target = await getID(arguments[1])

            if target:
                sql.execute("SELECT * FROM economy WHERE user_id = ? ORDER BY rowid DESC LIMIT 9999999999999", (target,))
                logs = sql.fetchall()

                if not logs:
                    await message.reply(f"У @id{target} ({await get_user_name(target, chat_id)}) отсутствуют записи в логах экономики.", disable_mentions=1)
                    return True

                total = len(logs)
                per_page = MAX_LOGS
                max_page = (total + per_page - 1) // per_page

                async def get_economy_page(page: int):
                    start = (page - 1) * per_page
                    end = start + per_page
                    selected = logs[start:end]
                    formatted = []
                    for idx, entry in enumerate(selected, start=start + 1):
                        u_id, t_id, amount, log_text = entry

                        try:
                            u_info = await bot.api.users.get(user_ids=u_id)
                            u_name = f"{u_info[0].first_name} {u_info[0].last_name}"
                        except:
                            u_name = str(u_id)

                        if t_id:
                            try:
                                t_info = await bot.api.users.get(user_ids=t_id)
                                t_name = f"{t_info[0].first_name} {t_info[0].last_name}"
                                t_display = f"@id{t_id} ({t_name})"
                            except:
                                t_display = f"@id{t_id}"
                        else:
                            t_display = "None"

                        a_display = f"{format_number(amount)}$" if amount else "None"
                        l_display = log_text if log_text else "—"

                        formatted.append(f"{idx}. @id{u_id} ({u_name}) | Кому: {t_display} | Сколько: {a_display} | Лог: {l_display}")
                    return formatted

                page = 1
                economy_page = await get_economy_page(page)
                economy_text = "\n\n".join(economy_page)

                keyboard = (
                    Keyboard(inline=True)
                    .add(Callback("⏪", {"command": "economyMinus", "target": target, "page": 1}), color=KeyboardButtonColor.NEGATIVE)
                    .add(Callback("⏩", {"command": "economyPlus", "target": target, "page": 1}), color=KeyboardButtonColor.POSITIVE)
                )

                await message.reply(
                    f"Логи экономики @id{target} ({await get_user_name(target, chat_id)}) [1/{max_page}]:\n\n{economy_text}",
                    disable_mentions=1, keyboard=keyboard
                )
                return True

            else:
                sql.execute("SELECT * FROM economy ORDER BY rowid DESC LIMIT 9999999999999")
                logs = sql.fetchall()

                if not logs:
                    await message.reply(f"Логи экономики отсутствуют!", disable_mentions=1)
                    return True

                total = len(logs)
                per_page = MAX_LOGS
                max_page = (total + per_page - 1) // per_page

                async def get_economy_page(page: int):
                    start = (page - 1) * per_page
                    end = start + per_page
                    selected = logs[start:end]
                    formatted = []
                    for idx, entry in enumerate(selected, start=start + 1):
                        u_id, t_id, amount, log_text = entry

                        try:
                            u_info = await bot.api.users.get(user_ids=u_id)
                            u_name = f"{u_info[0].first_name} {u_info[0].last_name}"
                        except:
                            u_name = str(u_id)

                        if t_id:
                            try:
                                t_info = await bot.api.users.get(user_ids=t_id)
                                t_name = f"{t_info[0].first_name} {t_info[0].last_name}"
                                t_display = f"@id{t_id} ({t_name})"
                            except:
                                t_display = f"@id{t_id}"
                        else:
                            t_display = "None"

                        a_display = f"{format_number(amount)}$" if amount else "None"
                        l_display = log_text if log_text else "—"

                        formatted.append(f"{idx}. @id{u_id} ({u_name}) | Кому: {t_display} | Сколько: {a_display} | Лог: {l_display}")
                    return formatted

                page = 1
                economy_page = await get_economy_page(page)
                economy_text = "\n\n".join(economy_page)

                keyboard = (
                    Keyboard(inline=True)
                    .add(Callback("⏪", {"command": "economyAllMinus", "page": 1}), color=KeyboardButtonColor.NEGATIVE)
                    .add(Callback("⏩", {"command": "economyAllPlus", "page": 1}), color=KeyboardButtonColor.POSITIVE)
                )

                await message.reply(
                    f"Общие логи экономики [1/{max_page}]:\n\n{economy_text}",
                    disable_mentions=1, keyboard=keyboard
                )
                return True

        # === Добавление в Чёрный список ===
        if command in ['addblack', 'блеклист', 'чс', 'blackadd', 'addch']:
            if await get_role(user_id, chat_id) < 10:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == 89:
                await message.replyLocalizedMessage('testers_chat')
                return True

            # Определяем пользователя
            target = int
            arg = 0
            if message.reply_message:
                target = message.reply_message.from_id
                arg = 1
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                target = message.fwd_messages[0].from_id
                arg = 1
            elif len(arguments) >= 2 and await getID(arguments[1]):
                target = await getID(arguments[1])
                arg = 2
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            # Проверка — не в ЧС ли уже
            sql.execute("SELECT * FROM blacklist WHERE user_id = ?", (target,))
            if sql.fetchone():
                await message.reply("Данный пользователь уже находится в черном списке бота!", disable_mentions=1)
                return True

            if await equals_roles(user_id, target, chat_id, message) < 2:
                await message.reply("Вы не можете добавить данного пользователя в ЧС!", disable_mentions=1)
                return True

            reason = await get_string(arguments, arg)
            if not reason:
                await message.reply("Укажите причину блокировки!", disable_mentions=1)
                return True

            date_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            sql.execute("INSERT INTO blacklist (user_id, moderator_id, reason_gban, datetime_globalban) VALUES (?, ?, ?, ?)",
                        (target, user_id, reason, date_now))
            database.commit()

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) добавил @id{target} ({await get_user_name(target, chat_id)}) в черный список бота", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=target, role=None, log=f"добавил @id{target} (пользователя) в Чёрный список. Причина: {reason}")            
            return True


        # === Удаление из Чёрного списка ===
        if command in ['unblack', 'убратьчс', 'blackdel', 'unch']:
            if await get_role(user_id, chat_id) < 10:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == 89:
                await message.replyLocalizedMessage('testers_chat')
                return True

            target = int
            if message.reply_message:
                target = message.reply_message.from_id
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                target = message.fwd_messages[0].from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                target = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            sql.execute("SELECT * FROM blacklist WHERE user_id = ?", (target,))
            if not sql.fetchone():
                await message.reply("Данный пользователь не находится в черном списке бота!", disable_mentions=1)
                return True

            sql.execute("DELETE FROM blacklist WHERE user_id = ?", (target,))
            database.commit()

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) удалил @id{target} ({await get_user_name(target, chat_id)}) из черного списка бота!", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=target, role=None, log=f"удалил @id{target} (пользователя) из Чёрного списка")            
            return True           
                
        if command in ['логиобщие', 'logs', 'logsmoders', 'логи']:
            if await get_role(user_id, chat_id) < 8:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            target = None
            if message.reply_message:
                target = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                target = await getID(arguments[1])

            if target:
                sql.execute("SELECT * FROM logchats WHERE user_id = ? ORDER BY rowid DESC LIMIT 9999999999999", (target,))
                logs = sql.fetchall()

                if not logs:
                    await message.reply(f"У @id{target} ({await get_user_name(target, chat_id)}) отсутствуют записи в логах модерации.", disable_mentions=1)
                    return True

                total = len(logs)
                per_page = MAX_LOGS
                max_page = (total + per_page - 1) // per_page

                async def get_moders_page(page: int):
                    start = (page - 1) * per_page
                    end = start + per_page
                    selected = logs[start:end]
                    formatted = []
                    for idx, entry in enumerate(selected, start=start + 1):
                        u_id, t_id, amount, log_text = entry

                        try:
                            u_info = await bot.api.users.get(user_ids=u_id)
                            u_name = f"{u_info[0].first_name} {u_info[0].last_name}"
                        except:
                            u_name = str(u_id)

                        if t_id:
                            try:
                                t_info = await bot.api.users.get(user_ids=t_id)
                                t_name = f"{t_info[0].first_name} {t_info[0].last_name}"
                                t_display = f"@id{t_id} ({t_name})"
                            except:
                                t_display = f"@id{t_id}"
                        else:
                            t_display = "None"

                        a_display = f"{format_number(amount)}$" if amount else "None"
                        l_display = log_text if log_text else "—"

                        formatted.append(f"{idx}. @id{u_id} ({u_name}) | Кому: {t_display} | Роль: {a_display} | Лог: {l_display}")
                    return formatted

                page = 1
                moders_page = await get_moders_page(page)
                moders_text = "\n\n".join(moders_page)

                keyboard = (
                    Keyboard(inline=True)
                    .add(Callback("⏪", {"command": "modersMinus", "target": target, "page": 1}), color=KeyboardButtonColor.NEGATIVE)
                    .add(Callback("⏩", {"command": "modersPlus", "target": target, "page": 1}), color=KeyboardButtonColor.POSITIVE)
                )

                await message.reply(
                    f"Логи модерации @id{target} ({await get_user_name(target, chat_id)}) [1/{max_page}]:\n\n{moders_text}",
                    disable_mentions=1, keyboard=keyboard
                )
                return True

            else:
                sql.execute("SELECT * FROM logchats ORDER BY rowid DESC LIMIT 9999999999999")
                logs = sql.fetchall()

                if not logs:
                    await message.reply(f"Логи с действиями модераторов отсутствуют!", disable_mentions=1)
                    return True

                total = len(logs)
                per_page = MAX_LOGS
                max_page = (total + per_page - 1) // per_page

                async def get_moders_page(page: int):
                    start = (page - 1) * per_page
                    end = start + per_page
                    selected = logs[start:end]
                    formatted = []
                    for idx, entry in enumerate(selected, start=start + 1):
                        u_id, t_id, amount, log_text = entry

                        try:
                            u_info = await bot.api.users.get(user_ids=u_id)
                            u_name = f"{u_info[0].first_name} {u_info[0].last_name}"
                        except:
                            u_name = str(u_id)

                        if t_id:
                            try:
                                t_info = await bot.api.users.get(user_ids=t_id)
                                t_name = f"{t_info[0].first_name} {t_info[0].last_name}"
                                t_display = f"@id{t_id} ({t_name})"
                            except:
                                t_display = f"@id{t_id}"
                        else:
                            t_display = "None"

                        a_display = f"{format_number(amount)}$" if amount else "None"
                        l_display = log_text if log_text else "—"

                        formatted.append(f"{idx}. @id{u_id} ({u_name}) | Кому: {t_display} | Роль: {a_display} | Лог: {l_display}")
                    return formatted

                page = 1
                moders_page = await get_moders_page(page)
                moders_text = "\n\n".join(moders_page)

                keyboard = (
                    Keyboard(inline=True)
                    .add(Callback("⏪", {"command": "modersAllMinus", "page": 1}), color=KeyboardButtonColor.NEGATIVE)
                    .add(Callback("⏩", {"command": "modersAllPlus", "page": 1}), color=KeyboardButtonColor.POSITIVE)
                )

                await message.reply(
                    f"Общие логи модерации [1/{max_page}]:\n\n{moders_text}",
                    disable_mentions=1, keyboard=keyboard
                )
                return True
                            
        if command in ["casino", "казино"]:
            if get_block_game(chat_id):
                await message.reply(f"В данной беседе запрещено использовать любые игровые команды!\n\nВыключить данную настройку можно в: «/settingsgame»")
                return True
        	
            if len(arguments) < 1:
                await message.reply("🎰 Укажи сумму ставки: /казино 10000")
                return

            try:
                stake = int(arguments[-1])
            except:
                await message.reply("Ставка должна быть числом!")
                return

            if stake < 100:
                await message.reply("Минимальная ставка должна быть — 10$")
                return

            balances = load_data(BALANCES_FILE)
            bal = balances.get(str(user_id), get_balance(user_id))

            if bal["wallet"] < stake:
                await message.reply("Недостаточно средств для ставки!")
                return

            # Эмодзи рулетки. Бонусные значки встречаются реже.
            emojis = ["💎", "🌑", "🔔", "🍒", "🍀", "🍋", "💰", "⭐️", "🔥", "🎲"]
            weights = [2, 3, 3, 12, 12, 12, 12, 12, 12, 12]

            # Генерация случайных трёх эмодзи
            result = random.choices(emojis, weights=weights, k=3)

            # Проверка на джекпот
            jackpot = False
            if result[0] == result[1] == result[2]:
                jackpot = True

            # Подсчитываем бонусы
            multiplier = 0.0
            bonuses = {
                "🌑": 0.10,  # 10%
                "🔔": 0.15,  # 15%
                "💎": 0.25,  # 25%
            }

            triggered = []
            for emoji, bonus in bonuses.items():
                if emoji in result:
                    multiplier += bonus
                    triggered.append(emoji)

            # Базовый выигрыш / проигрыш
            if multiplier == 0 and not jackpot:
                # Проигрыш
                bal["wallet"] -= stake
                bal["lost_total"] = int(bal.get("lost_total", 0)) + int(stake)
                balances[str(user_id)] = bal
                save_data(BALANCES_FILE, balances)

                await message.reply(
                    f"🎰 Вы сыграли на ставку «{format_number(stake)}$»\n"
                    f"Результат: {' '.join(result)}\n\n"
                    f"❌ Не выпали бонусные значки 🌑, 🔔 или 💎 — вы проиграли!"
                )
                return
            else:
                base_win = stake * 2
                bonus_amount = int(stake * multiplier) if multiplier > 0 else 0
                win_amount = base_win + bonus_amount

                # Джекпот даёт ещё x3 к самой ставке сверху
                jackpot_bonus = 0
                if jackpot:
                    jackpot_bonus = stake * 3
                    win_amount += jackpot_bonus

                profit = win_amount - stake
                bal["wallet"] -= stake
                bal["wallet"] += win_amount
                bal["won_total"] = int(bal.get("won_total", 0)) + int(win_amount)
                balances[str(user_id)] = bal
                save_data(BALANCES_FILE, balances)
                await log_economy(user_id=user_id, target_id=None, amount=stake, log=f"сыграл(-а) в «Казино» на {stake}$")

                emoji_str = ", ".join(triggered) if triggered else "нет"
                jackpot_text = ""
                if jackpot:
                    jackpot_text = f"\n\n❗ JECKPOT! 3 одинаковых {result[0]} 🔥🔥🔥"

                await message.reply(
                    f"🎰 Вы сыграли на ставку «{format_number(stake)}$»\n"
                    f"Результат: {' '.join(result)}{jackpot_text}\n\n"
                    f"🎯 Бонусные значки: {emoji_str}\n"
                    f"💵 Базовый выигрыш: {format_number(base_win)}$\n"
                    f"📈 Бонус от значков: +{int(multiplier * 100)}% ({format_number(bonus_amount)}$)\n"
                    f"🔥 Джекпот бонус: {format_number(jackpot_bonus)}$\n"
                    f"💰 Итого выигрыш: {format_number(win_amount)}$ (чистая прибыль: {format_number(profit)}$)"
                )
                return            
            
        # ---------------- BUG ----------------
        if command in ["bug", "баг"]:
            if await get_role(user_id, chat_id) < 4:
                await message.replyLocalizedMessage('not_preminisionss')
                return True
        	
            try:
                user_info = await bot.api.users.get(user_ids=user_id)
                full_name = f"{user_info[0].first_name} {user_info[0].last_name}"
            except:
                full_name = f"id{user_id} (Ошибка)"

            args = message.text.split(maxsplit=1)
            if len(arguments) < 2 or len(args[1]) < 5:
                await message.replyLocalizedMessage('command_bug_min_params')
                return

            offer = args[1]

            ADMIN_ID = 488828183,574393629

            await bot.api.messages.send(
                peer_id=ADMIN_ID,
                random_id=0,
                message=(
                    f"👾 | Баг-трекер:\n"
                    f"1. Пользователь: [id{user_id}|{full_name}]\n"
                    f"2. Содержимое бага: {offer}"
                )
            )
            
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"подал(-а) баг-репорт с содержанием: «{offer}»")            
            await message.replyLocalizedMessage('command_bug')
            return            

        if command in ['stats', 'стата', 'статистика', 'stata', 'statistic']:
                # Определяем пользователя для показа статистики
                user = int
                if message.reply_message:
                    user = message.reply_message.from_id
                elif len(arguments) >= 2 and await getID(arguments[1]):
                    user = await getID(arguments[1])
                else:
                    user = user_id

                if user < 0:
                    await message.reply("Нельзя взаимодействовать с сообществом!")
                    return True

                reg_data = "-"  # вместо даты регистрации
                role = await get_role(user, chat_id)
                warns = await get_warns(user, chat_id)

                # Получаем ник
                if await is_nick(user, chat_id):
                    nick = await get_user_name(user, chat_id)
                else:
                    nick = "Нет"

                # Получаем имя и фамилию через VK
                try:
                    info = await bot.api.users.get(user_ids=user)
                    name = f"{info[0].first_name} {info[0].last_name}"
                except:
                    name = f"@id{user} (Не удалось получить имя)"

                messages = await message_stats(user, chat_id)
                msg = await messageslist(user, chat_id)
                msg_do = []
                ms = 0
                for i in msg:
                   ms = ms + 1
                   if ms <= 10: 
                   	msg_do.append(i)
                msg_str = "\n".join(msg_do)
                                                                                 
                # Проверка глобального бана
                sql.execute("SELECT * FROM gbanlist WHERE user_id = ?", (user,))
                gban = sql.fetchone()
                gban_status = "Да" if gban else "Нет"

                # Проверка глобального бана 2
                sql.execute("SELECT * FROM globalban WHERE user_id = ?", (user,))
                gban2 = sql.fetchone()
                globalban = "Да" if gban2 else "Нет"

                # Проверяем, есть ли мут
                sql.execute(f"SELECT * FROM mutes_{chat_id} WHERE user_id = ?", (user,))
                mute = sql.fetchone()
                mute_status = "Да" if mute else "Нет"

                # --- Проверка банов во всех чатах ---
                sql.execute("SELECT chat_id FROM chats")
                chats_list = sql.fetchall()
                bans = ""
                bans_count = 0
                i = 1
                for c in chats_list:
                    chat_id_check = c[0]
                    try:
                        sql.execute(f"SELECT moder, reason, date FROM bans_{chat_id_check} WHERE user_id = ?", (user,))
                        user_bans = sql.fetchall()
                        if user_bans:
                            bans_count += len(user_bans)
                            for ub in user_bans:
                                mod, reason, date = ub
                                bans += f"{i}) @id{mod} (Модератор) | {reason} | {date} МСК (UTC+3)\n"
                                i += 1
                    except:
                        continue  # если таблицы нет, пропускаем

                roles = {
                    0: "Пользователь",
                    1: "Модератор",
                    2: "Старший модератор",
                    3: "Администратор",
                    4: "Старший администратор",
                    5: "Зам. спец администратора",
                    6: "Спец администратор",
                    7: "Владелец беседы",
                    8: "Заместитель директора",
                    9: "Осн. заместитель директора",
                    10: "Директор бота",
                    11: "Разработчик бота"
                }
                role_display = roles.get(role, "Пользователь")
                if await is_tech_chat(chat_id):
                    tech_role = await get_tech_role(user, chat_id)
                    if tech_role > 0:
                        role_display = TECH_ROLE_NAMES.get(tech_role, role_display)

                # Создаём клавиатуру только если роль > 1
                keyboard = None
                if await get_role(user_id, chat_id) > 1:
                    keyboard = Keyboard(inline=True)
                    keyboard.add(
                        Callback("Все предупреждения", {"command": "activeWarns", "user": user, "chatId": chat_id}),
                        color=KeyboardButtonColor.PRIMARY
                    )
                    keyboard.add(
                        Callback("Информация о блокировках", {"command": "getban", "user": user, "chatId": chat_id}),
                        color=KeyboardButtonColor.PRIMARY
                    )

                await message.replyLocalizedMessage('command_stats', {
                        'user': f'@id{user} (пользователе)',
                        'role': role_display,
                        'bans': bans_count,
                        'gban': globalban,
                        'gbanpl': gban_status,
                        'warns': warns,
                        'mute': mute_status,
                        'nickname': nick,
                        'messages': messages['count'],
                        'last_message': messages['last'],                       
                    }, keyboard=keyboard)
                return True

        if command in ['подписка']:
            if await get_role(user_id, chat_id) < 0:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            subs = load_json_file(SUBS_FILE)
            user_key = str(user_id)
            sub_info = subs.get(user_key, {})
            is_subscribed = await is_user_subscribed_to_bot_group(user_id)

            if not is_subscribed:
                if sub_info.get("claimed"):
                    bal = get_balance(user_id)
                    bal = _revoke_subscription_rewards(bal, sub_info)
                    _persist_user_balance(user_id, bal)
                    sub_info["claimed"] = False
                    sub_info["revoked_at"] = datetime.now().isoformat()
                    subs[user_key] = sub_info
                    save_json_file(SUBS_FILE, subs)
                    await message.reply(
                        f"❌ Вы больше не подписаны на {BOT_GROUP_URL}.\n"
                        "Бонус за подписку был отозван. Подпишитесь снова и повторно используйте /подписка.",
                        disable_mentions=1,
                    )
                    await chats_log(user_id=user_id, target_id=None, role=None, log="потерял награду за подписку после отписки")
                    return True
                await message.reply(f"❗ Сначала подпишитесь на сообщество: {BOT_GROUP_URL}", disable_mentions=1)
                return True

            if sub_info.get("claimed"):
                await message.reply("Вы уже подписаны и награда за подписку у вас уже активирована.", disable_mentions=1)
                return True

            reward_money = 70000
            reward_vip_days = 7
            bal = get_balance(user_id)
            previous_vip_until = bal.get("vip_until")
            bal["wallet"] = int(bal.get("wallet", 0)) + reward_money
            now = datetime.now()
            current_vip = bal.get("vip_until")
            start_dt = now
            if current_vip:
                try:
                    vip_dt = datetime.fromisoformat(current_vip)
                    if vip_dt > now:
                        start_dt = vip_dt
                except Exception:
                    pass
            bal["vip_until"] = (start_dt + timedelta(days=reward_vip_days)).isoformat()
            _persist_user_balance(user_id, bal)
            await log_economy(
                user_id=user_id,
                target_id=None,
                amount=reward_money,
                log=f"получил(-а) награду за подписку: {reward_money}$ и VIP на {reward_vip_days} дней",
            )

            subs[user_key] = {
                "time": datetime.now().isoformat(),
                "claimed": True,
                "prev_vip_until": previous_vip_until,
                "reward": {"money": reward_money, "vip_days": reward_vip_days}
            }
            save_json_file(SUBS_FILE, subs)
            await message.reply(
                f"✅ @id{user_id} ({await get_user_name(user_id, chat_id)}) вы подписаны на сообщество и получили бонус: "
                f"{format_number(reward_money)}$ и VIP на {reward_vip_days} дней.",
                disable_mentions=1,
            )
            await chats_log(user_id=user_id, target_id=None, role=None, log="получил награду за подписку")
            return True
            
        if command in ['blacklist']:
            if await get_role(user_id, chat_id) < 8:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            page = 1
            if len(arguments) >= 2 and arguments[-1].isdigit():
                page = int(arguments[-1])

            try:
                sql.execute("SELECT user_id, moderator_id, reason_gban, datetime_globalban FROM blacklist ORDER BY rowid DESC")
                rows = sql.fetchall()
            except Exception as e:
                print(f"[blacklist] DB error: {e}")
                rows = []

            total_items = len(rows)
            page_items, total_pages = paginate_list(rows, page, 20)

            if not page_items:
                await message.reply("Чёрный список пуст.", disable_mentions=1)
                return True

            text = ""
            i = (page-1)*20 + 1
            for r in page_items:
                uid, mod, reason, dt = r
                try:
                    name = await get_user_name(uid, chat_id)
                except:
                    name = str(uid)
                text += f"{i}. @id{uid} ({name}) | @id{mod} (Модератор) | Причина: {reason} | {dt}\n"
                i += 1

            kb = make_nav_keyboard("blacklist", page, chat_id)
            await message.reply(f"Список пользователей в черном списке бота (страница {page}/{total_pages}):\n\n{text}", disable_mentions=1, keyboard=kb)
            return True

        if command in ['gbanlist']:
            if await get_role(user_id, chat_id) < 8:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            page = 1
            if len(arguments) >= 2 and arguments[-1].isdigit():
                page = int(arguments[-1])

            rows = []
            try:
                sql.execute("SELECT user_id, moderator_id, reason_gban, datetime_globalban FROM gbanlist ORDER BY rowid DESC")
                rows += sql.fetchall()
            except Exception as e:
                print(f"[gbanlist] gbanlist read error: {e}")
            try:
                sql.execute("SELECT user_id, moderator_id, reason_gban, datetime_globalban FROM globalban ORDER BY rowid DESC")
                rows += sql.fetchall()
            except Exception as e:
                print(f"[gbanlist] globalban read error: {e}")

            total_items = len(rows)
            page_items, total_pages = paginate_list(rows, page, 20)

            if not page_items:
                await message.reply("Список пользователей в глобальной блокировке отсутствует!", disable_mentions=1)
                return True

            text = ""
            i = (page-1)*20 + 1
            for r in page_items:
                uid, mod, reason, dt = r
                try:
                    name = await get_user_name(uid, chat_id)
                except:
                    name = str(uid)
                text += f"{i}. @id{uid} ({name}) | @id{mod} (Модератор) | Причина: {reason} | {dt}\n"
                i += 1

            kb = make_nav_keyboard("gbanlist", page, chat_id)
            await message.reply(f"Список пользователей в глобальной блокировке (страница {page}/{total_pages}):\n\n{text}", disable_mentions=1, keyboard=kb)
            return True
                         
        if command in ["banid", "банчата"]:
            if await get_role(user_id, chat_id) < 10:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == 89:
                await message.replyLocalizedMessage('testers_chat')
                return True

            if len(arguments) < 2:
                await message.reply("Укажите чат!")
                return True

            try:
                target_chat = int(arguments[1])
            except:
                await message.reply("Укажите чат!")
                return True

            sql.execute("SELECT chat_id FROM banschats WHERE chat_id = ?", (target_chat,))
            if sql.fetchone():
                await message.reply("Беседа уже находится в блокировке!")
                return True

            sql.execute("INSERT INTO banschats (chat_id) VALUES (?)", (target_chat,))
            database.commit()
            
            target_peer = 2000000000 + target_chat
            await bot.api.messages.send(
                peer_id=target_peer,
                random_id=0,
                message=(
                    f"Владелец беседы — не член, BANANA MANAGER! Я не буду здесь работать."
                )
            )

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) заблокировал(-а) беседу №«{target_chat}»")
            return True

        if command in ["unbanid", "разбанчата"]:
            if await get_role(user_id, chat_id) < 10:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == 89:
                await message.replyLocalizedMessage('testers_chat')
                return True

            if len(arguments) < 2:
                await message.reply("Укажите чат!")
                return True

            try:
                target_chat = int(arguments[-1])
            except:
                await message.reply("Укажите чат!")
                return True

            sql.execute("SELECT chat_id FROM banschats WHERE chat_id = ?", (target_chat,))
            if not sql.fetchone():
                await message.reply("Беседа и так находится в блокировке!")
                return True

            sql.execute("DELETE FROM banschats WHERE chat_id = ?", (target_chat,))
            database.commit()
            
            target_peer = 2000000000 + target_chat
            await bot.api.messages.send(
                peer_id=target_peer,
                random_id=0,
                message=(
                    f"Чат разблокирован в боте!"
                )
            )

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) разблокировал(-а) беседу №«{target_chat}»")
            return True
            
        if command in ["clearchat", "удалитьчат"]:
            if await get_role(user_id, chat_id) < 10:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == 89:
                await message.replyLocalizedMessage('testers_chat')
                return True

            if len(arguments) < 2:
                await message.reply("Укажите чат!")
                return True

            try:
                target_chat = int(arguments[-1])
            except:
                await message.reply("Укажите чат!")
                return True
                
            target_peer = 2000000000 + target_chat
            await bot.api.messages.send(
                peer_id=target_peer,
                random_id=0,
                message=(
                    f"Чат удален из базы данных бота! Работа бота в чате прекращена."
                )
            )

            sql.execute("DELETE FROM chats WHERE chat_id = ?", (target_chat,))
            database.commit()

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) удалил(-а) беседу №«{target_chat}»")
            return True
                        
        if command in ['help', 'помощь', 'хелп', 'команды', 'commands']:
            if await is_tech_chat(chat_id):
                tech_role = await get_tech_role(user_id, chat_id)
                global_role = await get_role(user_id, chat_id)
                if tech_role < 1 and global_role < 11:
                    await message.replyLocalizedMessage('not_preminisionss')
                    return True

                tech_commands_levels = {
                    1: [
                        "🔹 Младший Технический Специалист",
                        "/staff — технический состав беседы",
                        "/логиэко — просмотр логов экономики",
                    ],
                    2: [
                        "\n🔹 Технический Специалист",
                        "/addjtech — выдать Младшего Технического Специалиста",
                    ],
                    3: [
                        "\n🔹 Старший Технический Специалист",
                        "/addtech — выдать роль Технического Специалиста",
                    ],
                    4: [
                        "\n🔹 Куратор Технических Специалистов",
                        "/rrole — снять техническую роль",
                        "/addstech — выдать роль Старшего Технического Специалиста",
                    ],
                    5: [
                        "\n🔹 Заместитель Главного Технического Специалиста",
                        "/addctech — выдать роль Куратора Технических Специалистов",
                    ],
                    6: [
                        "\n🔹 Главный Технический Специалист",
                        "/addztech — выдать роль Заместителя Главного Технического Специалиста",
                    ],
                }

                effective_tech_role = tech_role
                if global_role >= 11:
                    effective_tech_role = 6
                    tech_commands_levels[7] = [
                        "\n👑 Команды разработчика",
                        "/addgtech — выдать роль Главного Технического Специалиста",
                        "/settypetech — включить или выключить технические права в беседе",
                    ]

                commands = []
                for level in sorted(tech_commands_levels.keys()):
                    if level <= effective_tech_role:
                        commands.extend(tech_commands_levels[level])
                if global_role >= 11 and 7 in tech_commands_levels:
                    commands.extend(tech_commands_levels[7])

                await message.reply("\n".join(commands), disable_mentions=1)
                await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) технический список доступных команд")
                return True

            commands_levels = {
                0: [
                    'Команды пользователя:',
                    '/info -- офицальные ресурсы проекта',
                    '/правила — правила чата установленные владельцем беседы',
                    '/infobot — офицальные ресурсы бота',                    
                    '/stats -- информация о пользователе',
                    '/getid -- узнать оригинальный ID пользователя в ВК',
                    '/q -- выход из текущей беседы',
                    '/игры -- игровые команды',
                    '/form -- подать форму на бан (в определенном чате)',
                    '/offer -- предложить улучшение для бота'
                ],
                1: [
                    '\nКоманды модератора:',
                    '/setnick — сменить ник у пользователя',
                    '/removenick — очистить ник у пользователя',
                    '/getnick — проверить ник пользователя',
                    '/getacc — узнать пользователя по нику',
                    '/nlist — просмотреть ники пользователей',
                    '/nonick — пользователи без ников',
                    '/kick — исключить пользователя из беседы',
                    '/warn — выдать предупреждение пользователю',
                    '/unwarn — снять предупреждение пользователю',
                    '/getwarn — информация о активных предупреждениях пользователя',
                    '/warnhistory — информация о всех предупреждениях пользователя',
                    '/warnlist — список пользователей с варном',
                    '/staff — пользователи с ролями',
                    '/mute — замутить пользователя',
                    '/unmute — размутить пользователя',
                    '/alt — узнать альтернативные команды',
                    '/getmute -- информация о муте пользователя',
                    '/mutelist -- список пользователей с мутом',
                    '/clear -- очистить сообщения',
                    '/getban -- информация о банах пользователя',
                    '/delete -- удалить сообщение пользователя',
                    '/chatid -- узнать оригинальный айди чата в боте'                    
                ],
                2: [
                    '\nКоманды старшего модератора:',
                    '/ban — заблокировать пользователя в беседе',
                    '/unban -- разблокировать пользователя в беседе',
                    '/addmoder -- выдать пользователю модератора',
                    '/removerole -- забрать роль у пользователя',
                    '/online -- упомянуть пользователей онлайн',
                    '/onlinelist — посмотреть пользователей в онлайн',
                    '/banlist -- посмотреть заблокированных',
                    '/inactivelist -- список неактивных пользователей'
                ],
                3: [
                    '\nСписок команд администратора:',
                    '/quiet -- Включить выключить режим тишины',
                    '/skick -- исключить пользователя с бесед сетки',
                    '/sban -- заблокировать пользователя в сетке бесед',
                    '/sunban — разбанить пользователя в сетке бесед',
                    '/addsenmoder — выдать права старшего модератора',
                    '/rnickall -- очистить все ники в беседе',
                    '/sremovenick -- очистить ник у пользователя в сетке бесед',
                    '/zov -- упомянуть всех пользователей',
                    '/srole -- выдать права в сетке бесед'
                ],
                4: [
                    '\nСписок команд старшего администратора:',
                    '/addadmin -- выдать права администратора',
                    '/serverinfo -- информация о сервере',
                    '/filter -- фильтр запрещенных слов',
                    '/sremoverole -- забрать роль у пользователя в сетке бесед',
                    '/ssetnick -- установить ник в сетке бесед',
                    '/bug -- отправить баг-трекер разработчику бота',
                    '/report -- жалоба на пользователя' 
                    '/szov -- вызов участников бесед сетки',                  
                ],
                5: [
                    '\nСписок команд зам. спец администратора:',
                    '/addsenadmin -- выдать права старшего администратора',
                    '/sync -- синхронизация с базой данных',
                    '/pin -- закрепить сообщение',
                    '/unpin -- открепить сообщение',
                    '/deleteall -- удалить последние 200 сообщений пользователя',
                    '/gsinfo -- информация о глобальной привязке',
                    '/gsrnick -- очистить ник у пользователя в беседах привязки',
                    '/gssnick -- поставить ник пользователю в беседах привязки',
                    '/gskick -- исключить пользователя с бесед привязки',
                    '/gsban -- заблокировать пользователя в беседах привязки',
                    '/gsunban -- разбанить пользователя в беседах привязки'                    
                ],                
                6: [
                    '\nСписок команд спец. администратора:',
                    '/addzsa -- выдать права зам. спец. администратора',
                    '/server -- привязать беседу к серверу',
                    '/settings -- показать настройки беседы',
                    '/clearwarn -- снять варны всем пользователям',
                    '/title -- изменить название беседы',
                    '/antisliv -- включить систему антислива в беседе'
                ],                
                7: [
                    '\nСписок команд владельца беседы:',
                    '/addsa -- выдать права спец. администратора',
                    '/antiflood -- режим защиты от спама',
                    '/welcometext -- текст приветствия',
                    '/invite -- система добавления пользователей только модераторами',
                    '/leave -- система исключения пользователей при выходе',
                    '/editowner -- передать права владельца беседы',
                    '/masskick -- исключить участников без ролей',
                    '/защита -- защита от сторонних сообществ',
                    '/settingsmute -- включить выдачу варнов за написание сообщений в муте',
                    '/setinfo -- установить информацию о официальных ресурсах проекта в «/info»',
                    '/setrules -- установить правила беседы в «/rules»',
                    '/type – изменить тип беседы',
                    '/gsync -- поставить глобальную синхронизацию бесед',
                    '/gunsync – отключить глобальную синхронизацию бесед',
                    '/masskick -- исключить нескольких пользователей',
                    '/amnesty -- амнистия наказаний в чате',
                    '/settingsgame -- запретить игры в беседе',
                    '/settingsphoto -- запретить отправку фото в беседу'
                ],          
                8: [
                    '\nСписок команд заместителя директора:',
                    '/gbanpl -- заблокировать пользователя во всех игровых беседах',
                    '/gunbanpl -- разбанить пользователя во всех игровых беседах',
                    '/gban -- заблокировать пользователя во всех беседах',
                    '/ungban -- разблокировать пользователя во всех беседах',
                    '/логиэко -- логирование экономики (пользователя или общие)',
                    '/логи -- логи модераторских действий (пользователя или общие)',
                    '/gbanlist -- список пользователей в глобальной блокировке',
                    '/blacklist -- список пользователей в черном списке бота'
                ],
                9: [
                    '\nСписок команд осн. заместителя директора:',
                    '/addzamdirector – выдать права заместителя директора',
                    '/setowner – установить владельца беседы',
                    '/gstaff – пользователи с глобальными ролями',
                    '/grrole -- забрать роль (глобальную)'
                ],
                10: [
                    '\nСписок команд директора бота:',
                    '/infoid -- группы по айди владельца',
                    '/banid -- забанить группу в боте по чат айди',
                    '/unbanid -- разбанить группу в боте по чат айди',
                    '/say -- сообщение от имени бота',
                    '/addoszamdirector – выдать права основного заместителя директора', 
                    '/clearchat -- очистить все данные из определенного чата',                   
                    '/listchats -- список чатов',
                    '/gzov -- упомянуть всех пользователей в категории бесед',
                    '/banwords -- просмотр списка запрещённых слов',
                    '/addbanwords -- добавить запрещённое слово',     
                    '/removebanwords -- удалить запрещённое слово',               
                    '/give -- выдать монеты',
                    '/addblack -- добавить пользоваля в черный список бота',
                    '/unblack -- вынести пользователя из черного списка бота',
                    '/infochat -- информация о беседе по айди',
                    '/zunban -- снять все баны пользователю',  
                    '/createpromo -- создать промо-код',                  
                    '/clearbans -- удалить все блокировки в определенном чате',
                    '/выдатьбананы -- выдать бананы пользователю'
                ],                
                11: [
                    '\nСписок команд разработчиков бота:',
                    '/resetmoney -- обнулить баланс пользователя',
                    '/раздача -- раздача монет пользователям',
                    '/adddirector -- выдать права директора бота',
                    '/removeduel -- удалить активную дуэль в беседе',
                    '/оффроль -- снять с себя права',
                    '/adddev -- выдать права разработчика бота',
                    '/показтоп -- включить или скрыть пользователя в топе',
                    '/settypetech -- включить или выключить технические права в беседе'
                ]                
            }

            user_role = await get_role(user_id, chat_id)

            commands_levels[0].extend([
                '/казино -- игра на ставку',
                '/кейс -- меню кейсов',
                '/кейсы -- ваши неоткрытые кейсы',
                '/инв -- ваш инвентарь',
                '/бизнес -- управление бизнесами',
                '/продатьбананы -- выставить бананы на продажу',
                '/promo -- активировать промо-код',
                '/открытьдепозит -- открыть депозит',
                '/закрытьдепозит -- закрыть депозит',
            ])

            if user_role > 1:
                keyboard = (
                    Keyboard(inline=True)
                    .add(Callback("Альтернативные команды", {"command": "alt", "chatId": chat_id}), color=KeyboardButtonColor.PRIMARY)
                )
            else:
                keyboard = None

            commands = []
            for i in commands_levels.keys():
                if i <= user_role:
                    for b in commands_levels[i]:
                        commands.append(b)

            level_commands = '\n'.join(commands)

            await message.reply(f"{level_commands}", disable_mentions=1, keyboard=keyboard)
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) список доступных команд")            

        if command in ['snick', 'setnick', 'nick', 'addnick', 'ник', 'сетник', 'аддник']:
            if await get_role(user_id, chat_id) < 1:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            user = int
            arg = 0
            if message.reply_message:
                user = message.reply_message.from_id
                arg = 1
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
                arg = 1
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
                arg = 2
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if user != user_id and await equals_roles(user_id, user, chat_id, message) == 0:
                await message.replyLocalizedMessage('command_setnick_preminissions')
                return True

            new_nick = await get_string(arguments, arg)
            if not new_nick:
                await message.replyLocalizedMessage('command_setnick_nick')
                return True
            else: await setnick(user, chat_id, new_nick)

            await message.replyLocalizedMessage('command_setnick', {
                        'user': userf,
                        'target': f'@id{user} (пользователю)',
                        'nick': new_nick
                    })
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"установил(-а) новый ник @id{user} (пользователю). Новый ник: {new_nick}")                       

        if command in ['rnick', 'removenick', 'clearnick', 'cnick', 'рник', 'удалитьник', 'снятьник']:
            if await get_role(user_id, chat_id) < 1:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            user = int
            if message.reply_message: user = message.reply_message.from_id
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) == 0:
                await message.replyLocalizedMessage('command_removenick_premminisions')
                return True

            await rnick(user, chat_id)
            await message.replyLocalizedMessage('command_removenick', {
                        'user': userf,
                        'target': f'@id{user} (пользователю)'
                    })
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"удалил(-а) старый ник @id{user} (пользователю)")            

        if command in ['type', 'тип']:
            if await get_role(user_id, chat_id) < 7:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            # получаем аргумент (новый тип)
            if len(arguments) < 2:
                # тип не указан, показываем текущий тип
                sql.execute(f"SELECT type FROM chats WHERE chat_id = {chat_id}")
                current_type = sql.fetchone()
                if current_type:
                    type_value = current_type[0]
                    await message.reply(
                        f"Беседа имеет тип: {chat_types.get(type_value, type_value)}\n\n"
                        "Все типы бесед:\n" +
                        "\n".join([f"{k} -- {v}" for k, v in chat_types.items()]),
                        disable_mentions=1
                    )
                return True

            new_type = arguments[1].lower()

            # проверка на валидность
            if new_type not in chat_types:
                await message.reply(
                    "Неверный тип беседы, типы:\n" +
                    "\n".join([f"{k} -- {v}" for k, v in chat_types.items()]),
                    disable_mentions=1
                )
                return True

            # устанавливаем новый тип
            sql.execute(f"UPDATE chats SET type = ? WHERE chat_id = ?", (new_type, chat_id))
            database.commit()

            await message.replyLocalizedMessage('command_settype', {
                        'type': chat_types[new_type]
                    })            
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"установил(-а) новый тип беседы. Новый тип: {chat_types[new_type]}")            
            
        if command in ["settings", "настройки"]:
            if await get_role(user_id, chat_id) < 6:
                await message.replyLocalizedMessage('not_preminisionss')
                return

            # Получаем владельца чата через VK API
            x = await bot.api.messages.get_conversations_by_id(
                peer_ids=peer_id,
                extended=1,
                fields='chat_settings',
                group_id=message.group_id
            )
            x = json.loads(x.json())
            chat_owner = None
            chat_title = None
            for i in x['items']:
                chat_owner = int(i["chat_settings"]["owner_id"])
                chat_title = i["chat_settings"]["title"]

            # Получаем данные из базы по chat_id
            sql.execute(f"SELECT type, in_pull, filter, leave_kick, invite_kick, antiflood FROM chats WHERE chat_id = {chat_id}")
            row = sql.fetchone()
            if row:
                type_value = chat_types.get(row[0], row[0])
                server = await get_current_server(chat_id)
                filter_text = "Включено" if row[2] == 1 else "Выключено"
                leave_text = "Включено" if row[3] == 1 else "Выключено"
                invite_text = "Включено" if row[4] == 1 else "Выключено"
                antiflood_text = "Включено" if row[5] == 1 else "Выключено"
            else:
                type_value = "Общие беседы"
                server = "0"
                filter_text = "Выключено"
                leave_text = "Выключено"
                invite_text = "Выключено"
                antiflood_text = "Выключено"

            await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) текущие настройки беседы")            
            await message.replyLocalizedMessage('command_settings', {
                        'chat_title': chat_title,
                        'owner': f'@id{chat_owner} ({await get_user_name(chat_owner, chat_id)})',
                        'type': type_value,
                        'chat_id': chat_id,
                        'filter': filter_text,
                        'leave': leave_text,
                        'antiflood': antiflood_text,
                        'invite': invite_text,
                        'server': server                                                                                               
                    })            
            return            

        if command in ['gsrnick', 'грник']:
            if await get_role(user_id, chat_id) < 5:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            gsync_chats = await get_gsync_chats(chat_id)
            if not gsync_chats:
                await message.reply("Беседа не привязана к глобальной связке!", disable_mentions=1)
                return True

            user = int
            if message.reply_message:
                user = message.reply_message.from_id
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) == 0:
                await message.reply("Вы не можете снять ник у данного пользователя!", disable_mentions=1)
                return True

            for i in gsync_chats:
                try:
                    await rnick(user, i)
                except:
                    continue

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) убрал ник у @id{user} (пользователя) во всех беседах глобальной связки.", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"снял ник @id{user} (пользователю) во всех беседах глобальной связки")
            return True
            
        if command in ['gssnick', 'гссник']:
            if await get_role(user_id, chat_id) < 5:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            gsync_chats = await get_gsync_chats(chat_id)
            if not gsync_chats:
                await message.reply("Беседа не привязана к глобальной связке!", disable_mentions=1)
                return True

            user = int
            arg = 0
            if message.reply_message:
                user = message.reply_message.from_id
                arg = 1
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
                arg = 1
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
                arg = 2
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) == 0:
                await message.reply("Вы не можете установить ник данному пользователю!", disable_mentions=1)
                return True

            new_nick = await get_string(arguments, arg)
            if not new_nick:
                await message.reply("Укажите ник!", disable_mentions=1)
                return True

            for i in gsync_chats:
                try:
                    await setnick(user, i, new_nick)
                except:
                    continue

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) установил ник @id{user} (пользователю) во всех беседах глобальной связки.\nНовый ник: {new_nick}", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"установил ник {new_nick} @id{user} (пользователю) во всех беседах глобальной связки")
            return True

        if command in ['settingsphoto', 'настройкифото']:
            if await get_role(user_id, chat_id) < 7:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            sql.execute("SELECT * FROM photosettings WHERE chat_id = ?", (chat_id,))
            row = sql.fetchone()
            if row is None:
                sql.execute("INSERT INTO photosettings (chat_id, mode) VALUES (?, ?)", (chat_id, 1))
                database.commit()
                await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), включил(-а) систему удаления фотографий!", disable_mentions=1)
            else:
                new_mode = 0 if row[1] == 1 else 1
                sql.execute("UPDATE photosettings SET mode = ? WHERE chat_id = ?", (new_mode, chat_id))
                database.commit()
                if new_mode == 0:
                    await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), выключил(-а) систему удаления фотографий!", disable_mentions=1)
                else:
                    await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), включил(-а) систему удаления фотографий!", disable_mentions=1)

            return True            

        if command in ['settingsgame', 'настройкиигр']:
            if await get_role(user_id, chat_id) < 7:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            sql.execute("SELECT * FROM gamesettings WHERE chat_id = ?", (chat_id,))
            row = sql.fetchone()
            if row is None:
                sql.execute("INSERT INTO gamesettings (chat_id, mode) VALUES (?, ?)", (chat_id, 1))
                database.commit()
                await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), включил(-а) систему блокировки игровых команд!", disable_mentions=1)
            else:
                new_mode = 0 if row[1] == 1 else 1
                sql.execute("UPDATE gamesettings SET mode = ? WHERE chat_id = ?", (new_mode, chat_id))
                database.commit()
                if new_mode == 0:
                    await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), выключил(-а) систему блокировки игровых команд!", disable_mentions=1)
                else:
                    await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), включил(-а) систему блокировки игровых команд!", disable_mentions=1)

            return True

        if command in ['gskick', 'гскик']:
            if await get_role(user_id, chat_id) < 5:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            gsync_chats = await get_gsync_chats(chat_id)
            if not gsync_chats:
                await message.reply("Беседа не привязана к глобальной связке!", disable_mentions=1)
                return True

            user = int
            reason = None
            if message.reply_message:
                user = message.reply_message.from_id
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.reply("Вы не можете исключить данного пользователя!", disable_mentions=1)
                return True

            for i in gsync_chats:
                try:
                    await bot.api.messages.remove_chat_user(i, user)
                    msg = f"@id{user_id} ({await get_user_name(user_id, chat_id)}) исключил @id{user} ({await get_user_name(user, chat_id)}) в беседах глобальной связки!"
                    if reason:
                        msg += f"\nПричина: {reason}"
                    await bot.api.messages.send(peer_id=2000000000 + i, message=msg, disable_mentions=1, random_id=0)
                except:
                    continue

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) исключил @id{user} (пользователя) из всех бесед глобальной связки.", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"исключил @id{user} из всех бесед глобальной связки")
            return True

        if command in ['gsban', 'гсбан']:
            if await get_role(user_id, chat_id) < 5:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            gsync_chats = await get_gsync_chats(chat_id)
            if not gsync_chats:
                await message.reply("Беседа не привязана к глобальной связке!", disable_mentions=1)
                return True

            user = int
            arg = 0
            if message.reply_message:
                user = message.reply_message.from_id
                arg = 1
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
                arg = 1
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
                arg = 2
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.reply("Вы не можете заблокировать данного пользователя!", disable_mentions=1)
                return True

            reason = await get_string(arguments, arg)
            if not reason:
                await message.reply("Укажите причину блокировки!", disable_mentions=1)
                return True

            for i in gsync_chats:
                try:
                    await ban(user, user_id, i, reason)
                    await bot.api.messages.remove_chat_user(i, user)
                    msg = f"@id{user_id} ({await get_user_name(user_id, chat_id)}) исключил @id{user} ({await get_user_name(user, chat_id)}) в беседах глобальной связки!"
                    if reason:
                        msg += f"\nПричина: {reason}"
                    await bot.api.messages.send(peer_id=2000000000 + i, message=msg, disable_mentions=1, random_id=0)
                except:
                    continue

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) заблокировал @id{user} (пользователя) во всех беседах глобальной связки.\nПричина: {reason}", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"заблокировал @id{user} (пользователя) во всех беседах глобальной связки. Причина: {reason}")
            return True            
            
        if command in ['gsunban', 'гсунбан']:
            if await get_role(user_id, chat_id) < 5:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            gsync_chats = await get_gsync_chats(chat_id)
            if not gsync_chats:
                await message.reply("Беседа не привязана к глобальной связке!", disable_mentions=1)
                return True

            user = int
            if message.reply_message:
                user = message.reply_message.from_id
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) == 0:
                await message.reply("Вы не можете разбанить данного пользователя!", disable_mentions=1)
                return True

            for i in gsync_chats:
                try:
                    await unban(user, i)
                except:
                    continue

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) снял блокировку с @id{user} (пользователя) во всех беседах глобальной связки.", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"разблокировал @id{user} во всех беседах глобальной связки")
            return True
            
        if command in ['getacc', 'acc', 'гетакк', 'аккаунт', 'account']:
            if await get_role(user_id, chat_id) < 1:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            nick = await get_string(arguments, 1)
            if not nick:
                await message.replyLocalizedMessage('command_getacc_params')
                return True

            nick_result = await get_acc(chat_id, nick)

            if not nick_result: await message.replyLocalizedMessage('command_getacc_not')
            else:
                info = await bot.api.users.get(nick_result)
                await message.reply(f"Ник {nick} принадлежит @id{nick_result} ({info[0].first_name} {info[0].last_name})", disable_mentions=1)
                await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-a) кому принадлежит НикНейм «{nick}»")            

        if command in ['getnick', 'gnick', 'гник', 'гетник']:
            if await get_role(user_id, chat_id) < 1:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            user = 0
            if message.reply_message: user = message.reply_message.from_id
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            nick = await get_nick(user, chat_id)
            if not nick: await message.replyLocalizedMessage('command_getnick_not')
            else: await message.reply(f"Ник данного @id{user} (пользователя): {nick}", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"посмотрел(-а) текущее имя @id{user} (пользователя). Текущий ник: «{nick}»")            

        if command in ['никлист', 'ники', 'всеники', 'nlist', 'nickslist', 'nicklist', 'nicks']:
            if await get_role(user_id, chat_id) < 1:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            nicks = await nlist(chat_id, 1)
            nick_list = '\n'.join(nicks)
            if nick_list == "": nick_list = "Ники отсутствуют!"

            keyboard = (
                Keyboard(inline=True)
                .add(Callback("⏪", {"command": "nicksMinus", "page": 1, "chatId": chat_id}), color=KeyboardButtonColor.NEGATIVE)
                .add(Callback("Без ников", {"command": "nonicks", "chatId": chat_id}), color=KeyboardButtonColor.PRIMARY)
                .add(Callback("⏩", {"command": "nicksPlus", "page": 1, "chatId": chat_id}), color=KeyboardButtonColor.POSITIVE)
            )

            await message.reply(f"Пользователи с ником [1 страница]:\n{nick_list}\n\nПользователи без ников: «/nonick»", disable_mentions=1, keyboard=keyboard)
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) пользователей с ником")            

        if command in ['nonick', 'nonicks', 'nonicklist', 'nolist', 'nnlist', 'безников', 'ноникс']:
            if await get_role(user_id, chat_id) < 1:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            nonicks = await nonick(chat_id, 1)
            nonick_list = '\n'.join(nonicks)
            if nonick_list == "": nonick_list = "Пользователи без ников отсутствуют!"

            keyboard = (
                Keyboard(inline=True)
                .add(Callback("⏪", {"command": "nonickMinus", "page": 1, "chatId": chat_id}), color=KeyboardButtonColor.NEGATIVE)
                .add(Callback("С никами", {"command": "nicks", "chatId": chat_id}), color=KeyboardButtonColor.PRIMARY)
                .add(Callback("⏩", {"command": "nonickPlus", "page": 1, "chatId": chat_id}),
                     color=KeyboardButtonColor.POSITIVE)
            )

            await message.reply(f"Пользователи без ников [1]:\n{nonick_list}\n\nПользователи с никами: «/nlist»", disable_mentions=1, keyboard=keyboard)
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) пользователей без ников")            

        if command in ['kick', 'кик', 'исключить']:
            if await get_role(user_id, chat_id) < 1:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            user = int
            arg = 0
            if message.reply_message:
                user = message.reply_message.from_id
                arg = 1
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
                arg = 1
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
                arg = 2
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if chat_id == tchat:
                await message.replyLocalizedMessage('testers_chat')
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.replyLocalizedMessage('command_kick_preminisionss')
                return True

            reason = await get_string(arguments, arg)

            try: await bot.api.messages.remove_chat_user(chat_id, user)
            except:
                await message.replyLocalizedMessage('command_kick_not', {
                        'target': f'@id{user} (пользователя)'
                    })
                return True

            keyboard = (
                Keyboard(inline=True)
                .add(Callback("Очистить", {"command": "clear", "chatId": chat_id, "user": user}), color=KeyboardButtonColor.NEGATIVE)
            )

            if not reason:
                await message.replyLocalizedMessage('command_kick', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'target': f'@id{user} ({await get_user_name(user, chat_id)})'
                    }, keyboard=keyboard)
            else:
                await message.replyLocalizedMessage('command_kick_reason', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'target': f'@id{user} ({await get_user_name(user, chat_id)})',
                        'reason': reason
                    }, keyboard=keyboard)           	
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"исключил(-а) @id{user} (пользователя) из беседы")            

            await add_punishment(chat_id, user_id)
            if await get_sliv(user_id, chat_id) and await get_role(user_id, chat_id) < 5:
                await roleG(user_id, chat_id, 0)
                await message.reply(
                    f"❗️ Уровень прав @id{user_id} (пользователя) был снят из-за подозрений в сливе беседы\n\n{await staff_zov(chat_id)}")

        if command in ['warn', 'пред', 'варн', 'pred', 'предупреждение']:
            if await get_role(user_id, chat_id) < 1:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            user = int
            arg = 0
            if message.reply_message:
                user = message.reply_message.from_id
                arg = 1
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
                arg = 1
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
                arg = 2
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.replyLocalizedMessage('command_warn_preminisionss')
                return True

            reason = await get_string(arguments, arg)
            if not reason:
                await message.replyLocalizedMessage('command_warn_select_reason')
                return True

            warns = await warn(chat_id, user, user_id, reason)
            if warns < 3:
                keyboard = (
                    Keyboard(inline=True)
                    .add(Callback("Снять варн", {"command": "unwarn", "user": user, "chatId": chat_id}), color=KeyboardButtonColor.POSITIVE)
                    .add(Callback("Очистить", {"command": "clear", "chatId": chat_id, "user": user}), color=KeyboardButtonColor.NEGATIVE)
                )
                await message.replyLocalizedMessage('command_warn', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'target': f'@id{user} ({await get_user_name(user, chat_id)})',
                        'warns': warns,
                        'reason': reason
                    })                
            else:
                keyboard = (
                    Keyboard(inline=True)
                    .add(Callback("Очистить", {"command": "clear", "chatId": chat_id, "user": user}),color=KeyboardButtonColor.NEGATIVE)
                )
                await message.replyLocalizedMessage('command_warn_end', {
                        'user': f'@id{user} (Пользователь)',
                        'reason': reason
                    })
                try: await bot.api.messages.remove_chat_user(user, chat_id)
                except Exception as e: print(f'Произошла ошибка при исключении: {user}', e)
                await clear_warns(chat_id, user)

            await add_punishment(chat_id, user_id)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"выдал(-а) предупреждение @id{user} (пользователю). Причина: {reason}, Итого у пользователя: {warns}/3")            
            if await get_sliv(user_id, chat_id) and await get_role(user_id, chat_id) < 5:
                await roleG(user_id, chat_id, 0)
                await message.reply(
                    f"❗️ Уровень прав @id{user_id} (пользователя) был снят из-за подозрений в сливе беседы\n\n{await staff_zov(chat_id)}")

        if command in ['unwarn', 'унварн', 'анварн', 'снятьпред', 'минуспред']:
            if await get_role(user_id, chat_id) < 1:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            user = int
            if message.reply_message: user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.replyLocalizedMessage('command_unwarn_preminisionss')
                return True

            if await get_warns(user, chat_id) < 1:
                await message.replyLocalizedMessage('command_warn_null', {
                        'user': f'@id{user} (пользователя)'
                    })
                return True

            warns = await unwarn(chat_id, user)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"снял(-а) предупреждение @id{user} (пользователю)")            
            await message.replyLocalizedMessage('command_unwarn', {            
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'target': f'@id{user} ({await get_user_name(user, chat_id)})',
                        'warns': warns
                    })
            
        # --- /rules ---
        if command in ['rules', 'правила', 'правилачата']:
            sql.execute("SELECT description FROM rules WHERE chat_id = ?", (chat_id,))
            rules_text = sql.fetchone()

            if not rules_text:
                await message.replyLocalizedMessage('command_rules_not')
                return True

            await message.replyLocalizedMessage('command_rules', {
                        'rules': rules_text[0]
                    })
            return True

        # --- /setrules ---
        if command in ['setrules', 'установитьправила']:
            if await get_role(user_id, chat_id) < 7:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if len(arguments) < 2:
                await message.replyLocalizedMessage('command_setrules_params')
                return True

            text = " ".join(arguments[1:])
            sql.execute("INSERT OR REPLACE INTO rules (chat_id, description) VALUES (?, ?)", (chat_id, text))
            database.commit()

            await message.replyLocalizedMessage('command_setrules', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'text': text
                    })            
            return True

        if command in ['infoid', 'инфоайди', 'чатыпользователя', 'инфоид']:
                if await get_role(user_id, chat_id) < 10:
                        await message.replyLocalizedMessage('not_preminisionss')
                        return True

                if len(arguments) < 2:
                        await message.replyLocalizedMessage('select_user')
                        return True

                target = await getID(arguments[1])
                if not target:
                        await message.reply("Не удалось определить пользователя.", disable_mentions=1)
                        return True

                sql.execute("SELECT chat_id FROM chats WHERE owner_id = ?", (target,))
                user_chats = sql.fetchall()
                if not user_chats:
                        await message.reply("У пользователя нет зарегистрированных бесед.", disable_mentions=1)
                        return True

                # Берем первую страницу
                page = 1
                per_page = 5
                total_pages = (len(user_chats) + per_page - 1) // per_page
                start = (page - 1) * per_page
                end = start + per_page
                page_chats = user_chats[start:end]

                all_chats = []
                for idx, (chat_id_val,) in enumerate(page_chats, start=1):
                        try:
                                peer_id = 2000000000 + chat_id_val
                                info = await bot.api.messages.get_conversations_by_id(peer_ids=peer_id)
                                if info.items:
                                        chat_title = info.items[0].chat_settings.title
                                else:
                                        chat_title = "Без названия"
                                link = (await bot.api.messages.get_invite_link(peer_id=peer_id, reset=0)).link
                        except:
                                chat_title = "Не удалось получить"
                                link = "Не удалось получить"

                        all_chats.append(f"{idx}. {chat_title} | 🆔: {chat_id_val} | 🔗 Ссылка: {link}")

                all_chats_text = "\n".join(all_chats)
                keyboard = (
                    Keyboard(inline=True)
                    .add(Callback("Назад", {"command": "infoidMinus", "page": 1, "user": target}), color=KeyboardButtonColor.NEGATIVE)
                    .add(Callback("Вперёд", {"command": "infoidPlus", "page": 1, "user": target}), color=KeyboardButtonColor.POSITIVE)
                )

                await message.reply(
                        f"❗ Список бесед @id{target} (пользователя):\n(Страница: 1)\n\n{all_chats_text}\n\n🗨️ Всего бесед у пользователя: {idx}",
                        disable_mentions=1,
                        keyboard=keyboard
                )
                return True                

        if command in ['banwords', 'запрещенныеслова', 'banwordlist']:
                if await get_role(user_id, chat_id) < 10:
                        await message.replyLocalizedMessage('not_preminisionss')
                        return True

                sql.execute("SELECT word, creator_id, time FROM ban_words ORDER BY time DESC")
                rows = sql.fetchall()
                if not rows:
                        await message.reply("Запрещённые слова отсутствуют!", disable_mentions=1)
                        return True

                total = len(rows)
                per_page = 5
                max_page = (total + per_page - 1) // per_page

                async def get_words_page(page: int):
                        start = (page - 1) * per_page
                        end = start + per_page
                        formatted = []
                        for i, (word, creator, tm) in enumerate(rows[start:end], start=start + 1):
                                try:
                                        info = await bot.api.users.get(user_ids=creator)
                                        creator_name = f"{info[0].first_name} {info[0].last_name}"
                                except:
                                        creator_name = "Не удалось получить имя"
                                formatted.append(f"{i}. {word} | @id{creator} ({creator_name}) | Время: {tm}")
                        return formatted

                page = 1 
                page_data = await get_words_page(page)
                page_text = "\n\n".join(page_data)

                keyboard = (
                        Keyboard(inline=True)
                        .add(Callback("⏪", {"command": "banwordsMinus", "page": 1}), color=KeyboardButtonColor.NEGATIVE)
                        .add(Callback("⏩", {"command": "banwordsPlus", "page": 1}), color=KeyboardButtonColor.POSITIVE)
                )

                await message.reply(
                        f"Запрещённые слова (Страница 1):\n\n{page_text}\n\nВсего запрещенных слов: {total}",
                        disable_mentions=1, keyboard=keyboard
                )
                return True
                
        if command in ['addbanwords', 'addword', 'banword']:
                if await get_role(user_id, chat_id) < 10:
                        await message.replyLocalizedMessage('not_preminisionss')
                        return True
                if len(arguments) < 2:
                        await message.reply("Пример: /addbanwords текст")
                        return True

                word = arguments[1].lower()
                time_now = datetime.now().strftime("%I:%M %p")

                sql.execute("SELECT word FROM ban_words WHERE word = ?", (word,))
                if sql.fetchone():
                        await message.reply("Слово уже находиться в списке запрещенных слов!")
                        return True

                sql.execute("INSERT INTO ban_words (word, creator_id, time) VALUES (?, ?, ?)", (word, user_id, time_now))
                database.commit()

                await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) добавил(-а) слово «{word}» в список запрещенных слов!")
                return True

        if command in ['removebanwords', 'unword', 'unbanword']:
                if await get_role(user_id, chat_id) < 10:
                        await message.replyLocalizedMessage('not_preminisionss')
                        return True
                if len(arguments) < 2:
                        await message.reply("Пример: /removebanwords текст")
                        return True

                word = arguments[1].lower()
                sql.execute("SELECT word FROM ban_words WHERE word = ?", (word,))
                if not sql.fetchone():
                        await message.reply("Слово отсутствует в списке запрещенных слов!")
                        return True

                sql.execute("DELETE FROM ban_words WHERE word = ?", (word,))
                database.commit()

                await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) удалил(-а) слово «{word}» из списка запрещенных слов!")
                return True
                
        # --- /info ---
        if command in ['info', 'инфо', 'информация']:
            sql.execute("SELECT description FROM info WHERE chat_id = ?", (chat_id,))
            info_text = sql.fetchone()

            if not info_text:
                await message.replyLocalizedMessage('command_info_not')
                return True

            await message.replyLocalizedMessage('command_info', {
                        'info': info_text[0]
                    })
            return True

        if command in ["открытьдепозит", "depositopen", "opendeposit"]:
            if get_block_game(chat_id):
                await message.reply("В данной беседе запрещено использовать любые игровые команды!\n\nВыключить данную настройку можно в: «/settingsgame»")
                return True
            if len(arguments) < 3:
                await message.reply("Доступные сроки: 4, 8 или 10 дней. Пример: /открытьдепозит 4 1000")
                return True

            percent_map = {4: 25, 8: 45, 10: 75}
            try:
                days = int(arguments[1])
                amount = int(arguments[2])
            except Exception:
                await message.reply("Аргументы должны быть числами. Пример: /открытьдепозит 4 1000")
                return True

            if days not in percent_map:
                await message.reply("Доступные сроки только: 4, 8 или 10 дней.")
                return True
            if amount <= 0:
                await message.reply("Сумма должна быть больше 0.")
                return True

            balances = load_data(BALANCES_FILE)
            bal = balances.get(str(user_id), get_balance(user_id))
            vip_until = bal.get("vip_until")
            if not vip_until or datetime.fromisoformat(vip_until) < datetime.now():
                await message.reply("Для открытия депозита требуется VIP-статус!")
                return True
            if bal.get("deposit_amount", 0) > 0:
                await message.reply("У вас уже есть активный депозит. Дождитесь завершения.")
                return True
            if bal["wallet"] < amount:
                await message.reply("Недостаточно монет на балансе")
                return True

            percent = percent_map[days]
            end_time = datetime.now() + timedelta(days=days)
            bal["wallet"] -= amount
            bal["deposit_amount"] = amount
            bal["deposit_until"] = end_time.isoformat()
            bal["deposit_percent"] = percent
            bal["deposit_days"] = days
            _persist_user_balance(user_id, bal, balances)
            await log_economy(user_id=user_id, target_id=None, amount=amount, log=f"открыл(-а) депозит на {amount}$ на {days}д.")
            await message.reply(f"Депозит {format_number(amount)}$ на {days} дней под {percent}% успешно открыт!")
            return True

        if command in ["закрытьдепозит", "depositclose", "closedeposit"]:
            if get_block_game(chat_id):
                await message.reply("В данной беседе запрещено использовать любые игровые команды!\n\nВыключить данную настройку можно в: «/settingsgame»")
                return True
            balances = load_data(BALANCES_FILE)
            bal = balances.get(str(user_id), get_balance(user_id))
            deposit_amount = bal.get("deposit_amount", 0)
            deposit_until = bal.get("deposit_until")
            deposit_percent = bal.get("deposit_percent", 0)
            if deposit_amount == 0 or not deposit_until:
                await message.reply("Нет завершённых депозитов для вывода.")
                return True
            end_time = datetime.fromisoformat(deposit_until)
            if datetime.now() < end_time:
                delta = end_time - datetime.now()
                await message.reply(f"Депозит ещё не завершён.\nОсталось: {delta.days}д {delta.seconds // 3600}ч")
                return True
            profit = int(deposit_amount * deposit_percent / 100)
            total_return = deposit_amount + profit
            bal["wallet"] += total_return
            bal["deposit_amount"] = 0
            bal["deposit_until"] = None
            bal["deposit_percent"] = 0
            bal["deposit_days"] = 0
            _persist_user_balance(user_id, bal, balances)
            await log_economy(user_id=user_id, target_id=None, amount=total_return, log=f"закрыл(-а) депозит и получил {total_return}$.")
            await message.reply(
                f"Депозит закрыт.\n"
                f"Вклад: {format_number(deposit_amount)}$\n"
                f"Прибыль: {format_number(profit)}$\n"
                f"Получено: {format_number(total_return)}$"
            )
            return True

        if command in ['games', 'game', 'игры', 'gamehelp']:
            await message.reply(
                "🎮 Игровые команды:\n"
                "\n"
                "💰 Экономика:\n"
                "/приз — ежедневный бонус\n"
                "/баланс — посмотреть баланс\n"
                "/передать — передать монеты\n"
                "/топ — топ по монетам\n"
                "/положить — положить деньги в банк\n"
                "/снять — снять деньги с банка\n"
                "/открытьдепозит — открыть депозит\n"
                "/закрытьдепозит — закрыть депозит\n"
                "\n"
                "🎲 Игры:\n"
                "/дуэль — сыграть дуэль\n"
                "/казино — игра на ставку\n"
                "\n"
                "🎒 Инвентарь:\n"
                "/инв — открыть инвентарь\n"
                "/применить [ID] — использовать предмет\n"
                "/распылить [ID] — распылить предмет\n"
                "\n"
                "🎁 Кейсы:\n"
                "/кейс — меню кейсов\n"
                "/моикейсы — ваши кейсы\n"
                "/открытькейс [тип] — открыть кейс\n"
                "\n"
                "🏢 Бизнесы:\n"
                "/бизнес — управление бизнесами\n"
                "/собратьбиз — собрать доход сразу в банк\n"
                "/ппрод [число до 100] — пополнить продукты во всех бизнесах\n"
                "/улучшбиз [ID филиала] — улучшить филиал\n"
                "\n"
                "🏛 Аукцион:\n"
                "/аукцион — список лотов\n"
                "/выставитьаук [ID предмета] [ставка] — выставить предмет\n"
                "/купаук [ID лота] [ставка] — сделать ставку\n"
                "/снятьаук [ID лота] — снять свой лот\n"
                "\n"
                "/promo — активировать промо-код"
            )
            return True            
            
        # --- /setinfo ---
        if command in ['setinfo', 'установитьинфо']:
            if await get_role(user_id, chat_id) < 7:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if len(arguments) < 2:
                await message.replyLocalizedMessage('command_setinfo_params')
                return True

            text = " ".join(arguments[1:])
            sql.execute("INSERT OR REPLACE INTO info (chat_id, description) VALUES (?, ?)", (chat_id, text))
            database.commit()

            await message.replyLocalizedMessage('command_setinfo', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'text': text
                    })            
            return True

        if command in ['antisliv', 'антислив']:
            if await get_role(user_id, chat_id) < 6:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            # Получаем текущее состояние антислива
            current_mode = await get_antisliv(chat_id)
            new_mode = 0 if current_mode == 1 else 1

            # Обновляем состояние
            await antisliv_mode(chat_id, new_mode)

            # Получаем имя пользователя, кто изменил режим
            user_name = await get_user_name(user_id, chat_id)

            # Формируем текст статуса
            if new_mode == 1:
                text = f"@id{user_id} ({user_name}) включил(-а) систему антислива!"
            else:
                text = f"@id{user_id} ({user_name}) выключил(-а) систему антислива!"

            await message.replyLocalizedMessage('command_antisliv', {
                        'info': text
                    })            
            return True            
            
        if command in ['clearwarn', 'очиститьварны']:
            if await get_role(user_id, chat_id) < 6:  # доступ с 6 ранга
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            count = await clear_all_warns(chat_id)

            if count == 0:
                await message.replyLocalizedMessage('command_clearwarns_no_users')
            else:
                await message.replyLocalizedMessage('command_clearwarns', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'count_clear': count
                    })            
                await chats_log(user_id=user_id, target_id=None, role=None, log=f"очистил(-а) варны у {count} пользователей")            

            return True
            
        if command in ['getwarn', 'gwarn', 'getwarns', 'гетварн', 'гварн']:
            if await get_role(user_id, chat_id) < 1:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            user = int
            if message.reply_message: user = message.reply_message.from_id
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            warns = await gwarn(user, chat_id)
            string_info = str
            if not warns: string_info = "Активных предупреждений нет!"
            else: string_info = f"@id{warns['moder']} (Модератор) | {warns['reason']} | {warns['count']}/3 | {warns['time']}"

            keyboard = (
                Keyboard(inline=True)
                .add(Callback("История предупреждений", {"command": "warnhistory", "user": user, "chatId": chat_id}), color=KeyboardButtonColor.PRIMARY)
            )

            await message.replyLocalizedMessage('command_getwarn', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'target': f'@id{user} ({await get_user_name(user, chat_id)})',
                        'warns': warns,
                        'info': string_info
                    }, keyboard=keyboard)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"посмотрел(-а) активные предупреждения @id{user} (пользователя)")            

        if command in ['zunban', 'удалитьбаны', 'снятьвсебаны']:
                if await get_role(user_id, chat_id) < 10:
                    await message.replyLocalizedMessage('not_preminisionss')
                    return True

                target = int
                if message.reply_message:
                    target = message.reply_message.from_id
                elif len(arguments) >= 2 and await getID(arguments[1]):
                    target = await getID(arguments[1])
                else:
                    await message.reply("Укажите пользователя!")
                    return True

                sql.execute("SELECT chat_id FROM chats")
                chats_list = sql.fetchall()
                total_removed = 0

                for c in chats_list:
                    chat_id_check = c[0]
                    try:
                        sql.execute(f"DELETE FROM bans_{chat_id_check} WHERE user_id = ?", (target,))
                        removed = sql.rowcount
                        if removed > 0:
                            total_removed += removed
                    except:
                        continue

                database.commit()

                if total_removed > 0:
                    await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) удалил(-а) «{total_removed}» блокировку(-и) у @id{target} ({await get_user_name(target, chat_id)})", disable_mentions=1)
                    await chats_log(user_id=user_id, target_id=target, role=None, log=f"снял(-а) все баны @id{target}")
                else:
                    await message.reply(f"У @id{target} (пользователя) нет блокировок в чатах!", disable_mentions=1)
                return True                
                
        if command in ['clearbans', 'очиститьбаны']:
            if await get_role(user_id, chat_id) < 10:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if len(arguments) < 2 or not arguments[1].isdigit():
                await message.reply("Укажите чат!", disable_mentions=1)
                return True

            target_chat = int(arguments[1])
            table_name = f"bans_{target_chat}"

            sql.execute(f"SELECT user_id FROM {table_name}")
            users = sql.fetchall()

            if not users:
                await message.reply(f"В беседе ID {target_chat} нет активных блокировок!", disable_mentions=1)
                return True

            sql.execute(f"DELETE FROM {table_name}")
            database.commit()

            text_users = ""
            for i, (uid,) in enumerate(users, 1):
                username = await get_user_name(uid, chat_id)
                text_users += f"{i}) @id{uid} ({await get_user_name(uid, target_chat)})\n"

            await message.reply(
                f"@id{user_id} ({await get_user_name(user_id, chat_id)}), снял(-а) блокировки в беседе «{target_chat}»\n\n"
                f"Пользователи у которых были сняты блокировки:\n{text_users}\nВсего блокировок снято: {len(users)}",
                disable_mentions=1
            )
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"очистил(-а) блокировки в {target_chat} ({len(users)})")
            return True

        if command in ['amnesty', 'амнистия']:
            if await get_role(user_id, chat_id) < 7:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            tables = {
                "mutes": f"mutes_{chat_id}",
                "bans": f"bans_{chat_id}",
                "warns": f"warns_{chat_id}"
            }

            result_text = ""
            total_cleared = {}

            for key, table in tables.items():
                sql.execute(f"SELECT user_id FROM {table}")
                users = sql.fetchall()
                count = len(users)
                total_cleared[key] = count

                sql.execute(f"DELETE FROM {table}")
                database.commit()

                if count > 0:
                    lines = "".join([f"{i+1}. @id{uid[0]} ({await get_user_name(user_id, chat_id)})\n" for i, uid in enumerate(users)])
                    result_text += f"Снято {key}: {count}\n| Из них:\n{lines}\n"
                else:
                    result_text += f"Снято {key}: 0\n| Из них: —\n\n"

            await message.replyLocalizedMessage('command_amnesty', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'result': result_text
                    })            
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"провёл(-а) амнистию в беседе {chat_id}")
            return True                            

        if command in ['warnhistory', 'historywarns', 'whistory', 'историяварнов', 'историяпредов']:
            if await get_role(user_id, chat_id) < 1:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            user = int
            if message.reply_message: user = message.reply_message.from_id
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            warnhistory_mass = await warnhistory(user, chat_id)
            if not warnhistory_mass: wh_string = "Предупреждений не было!"
            else: wh_string = '\n'.join(warnhistory_mass)

            keyboard = (
                Keyboard(inline=True)
                .add(Callback("Активные предупреждения", {"command": "activeWarns", "user": user, "chatId": chat_id}), color=KeyboardButtonColor.PRIMARY)
                .add(Callback("Вся информация", {"command": "stats", "user": user, "chatId": chat_id}),color=KeyboardButtonColor.PRIMARY)
            )

            await message.reply(f"Информация о всех предупреждениях @id{user} ({await get_user_name(user, chat_id)})\nКоличество предупреждений пользователя: {await get_warns(user, chat_id)}\n\nИнформация о последних 10 предупреждений пользователя:\n{wh_string}", disable_mentions=1, keyboard=keyboard)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"посмотрел(-а) все предупреждения @id{user} (пользователя)")            

        if command in ["баланс"]:
            if get_block_game(chat_id):
                await message.reply(f"В данной беседе запрещено использовать любые игровые команды!\n\nВыключить данную настройку можно в: «/settingsgame»")
                return True

            target = await extract_user_id(message)
            if not target:
                target = user_id

            await sync_user_business_income(target)
            balances = load_data(BALANCES_FILE)
            if str(target) not in balances:
                balances[str(target)] = get_balance(target)
            bal = balances[str(target)]
            unopened_cases_count = len(await get_user_cases(target))
            opened_cases_count = await get_opened_cases_count(target)
            target_businesses = await get_user_businesses(target)
            daily_business_income = sum(_business_daily_potential(branch) for branch in target_businesses)

            now = datetime.now()

            try:
                info = await bot.api.users.get(user_ids=target, name_case="gen")
                name = f"{info[0].first_name} {info[0].last_name}"
                mention = f"пользователя [id{target}|{name}]"
            except:
                mention = f"[id{target}|id{target}]"

            vip_until = bal.get("vip_until")
            if vip_until:
                try:
                    vip_end = datetime.fromisoformat(vip_until)
                    if vip_end > now:
                        is_vip = True
                        delta = vip_end - now
                        days, seconds = delta.days, delta.seconds
                        hours, minutes = divmod(seconds // 60, 60)
                        vip_status = "VIP"
                        vip_time = f"⏳ До окончания статуса: {days}д {hours}ч {minutes}м"
                        transfer_limit = 500_000
                    else:
                        is_vip = False
                        vip_status = "Отсутствует"
                        vip_time = "⏳ Отсутствует"
                        transfer_limit = 100_000
                except:
                    is_vip = False
                    vip_status = "Отсутствует"
                    vip_time = "⏳ Отсутствует"
                    transfer_limit = 100_000
            else:
                is_vip = False
                vip_status = "Отсутствует"
                vip_time = "⏳ Отсутствует"
                transfer_limit = 100_000

            today = now.date().isoformat()
            spent_today = bal.get("transfers_today", {}).get(today, 0)
            remaining_limit = max(0, transfer_limit - spent_today)

            deposit_text = ""
            deposit_amount = bal.get("deposit_amount", 0)
            deposit_until = bal.get("deposit_until")
            deposit_percent = bal.get("deposit_percent", 0)
            if deposit_amount > 1 and deposit_until:
                try:
                    end_time = datetime.fromisoformat(deposit_until)
                    if now < end_time:
                        delta = end_time - now
                        days, seconds = delta.days, delta.seconds
                        hours, minutes = divmod(seconds // 60, 60)
                        deposit_text = (
                            f"💸 Депозит: {format_number(deposit_amount)}$ "
                            f"на {days} дн. "
                            f"под {deposit_percent}%"
                            f"\n⏳ До вывода: {days}д {hours}ч {minutes}м"
                        )
                    else:
                        deposit_text = (
                            f"💸 Депозит: {format_number(deposit_amount)}$ "
                            f"под {deposit_percent}%"
                            f"\n⏳ До вывода: можно забирать!"
                        )
                except:
                    pass

            await message.reply(
                f"💰 У {mention} {format_number(bal['wallet'])}$\n"
                f"🏛 Счет в банке: {format_number(bal['bank'])}$\n"
                f"🍌 Бананы: {format_number(int(bal.get('bananas', 0)))}\n"
                f"🏆 Дуэлей выиграно: {bal['won']}\n"
                f"💔 Дуэлей проиграно: {bal['lost']}\n"
                f"🎉 Всего выиграно: {format_number(bal['won_total'])}$\n"
                f"💰 Всего проиграно: {format_number(bal['lost_total'])}$\n"
                f"📤 Отправлено переводами: {format_number(bal['sent_total'])}$\n"
                f"📥 Получено переводами: {format_number(bal['received_total'])}$\n"
                f"📈 Доход бизнесов за 1 день: {format_number(daily_business_income)}$\n"
                f"🏢 Бизнесы: {len(target_businesses)}\n"
                f"🎁 Кейсы: {unopened_cases_count}\n"
                f"📦 Открытые кейсы: {opened_cases_count}\n"
                f"⭐ Статус: {vip_status}\n"
                f"{vip_time}\n"
                f"{deposit_text}"
            )
            return            
          
        # ---------------- GIVEALL / РАЗДАЧА ----------------
        if command == "раздача":
            role = await get_role(user_id, chat_id)
            if role < 11:
                await message.replyLocalizedMessage('not_preminisionss')
                return

            if chat_id == 89:
                await message.replyLocalizedMessage('testers_chat', disable_mentions=1)
                return True

            if len(arguments) < 3:
                await message.reply("💰 Пример: +раздача 1000 10m")
                return

            try:
                amount = int(arguments[1])
                if amount <= 0:
                    raise ValueError()
            except Exception:
                await message.reply("Укажите количество монет числом!")
                return

            try:
                wait_seconds = parse_giveaway_duration(arguments[2])
            except Exception:
                await message.reply("Укажите время ожидания в формате: 30s, 10m, 2h или 1d")
                return

            giveaway_id = f"{message.peer_id}_{message.conversation_message_id}_{int(time.time())}"
            giveaways[giveaway_id] = {
                "creator_id": user_id,
                "peer_id": message.peer_id,
                "chat_id": chat_id,
                "amount": amount,
                "created_ts": int(time.time()),
                "end_ts": int(time.time()) + wait_seconds,
                "participants": [],
            }
            save_data(GIVEAWAYS_FILE, giveaways)
            asyncio.create_task(finish_giveaway(giveaway_id))

            keyboard = (
                Keyboard(inline=True)
                .add(
                    Callback("Вступить в розыгрыш", {"command": "join_giveaway", "giveaway_id": giveaway_id}),
                    color=KeyboardButtonColor.POSITIVE,
                )
            )

            await log_economy(user_id=user_id, target_id=None, amount=amount, log=f"создал(-а) раздачу на {amount}$")
            await message.reply(
                f"@all Новая раздача!\n\n"
                f"🎁 Создана раздача на {format_number(amount)}$.\n"
                f"⏳ Время ожидания: {arguments[2]}\n"
                f"Нажмите кнопку ниже, чтобы вступить в розыгрыш.\n"
                f"Для участия нужна подписка на сообщество бота: https://vk.com/club{groupid}",
                keyboard=keyboard,
                disable_mentions=1,
            )
            return

        if command == "giveall":
            # разрешённый ВК ID администратора
            role = await get_role(user_id, chat_id)
            if role < 11:
                await message.replyLocalizedMessage('not_preminisionss')
                return

            if chat_id == 89:
                await message.replyLocalizedMessage('testers_chat')
                return True

            if len(arguments) < 1:
                await message.reply("💰 Пример: /раздача 1000")
                return

            try:
                amount = int(arguments[-1])
                if amount <= 0:
                    raise ValueError()
            except:
                await message.reply("Укажите сумму числом!")
                return

            # загружаем балансы
            balances = load_data(BALANCES_FILE)

            all_users_text = ""
            for i, (uid, bal) in enumerate(balances.items(), start=1):
                # обновляем кошелёк
                bal["wallet"] += amount

                # получаем имя пользователя
                try:
                    info = await bot.api.users.get(user_ids=uid)
                    full_name = f"{info[0].first_name} {info[0].last_name}"
                except:
                    full_name = f"Ошибка"

                all_users_text += f"{i}. [id{uid}|{full_name}] | 💰 Новый баланс: {format_number(bal['wallet'])}\n"

            # сохраняем обновлённые балансы
            save_data(BALANCES_FILE, balances)
            await log_economy(user_id=uid, target_id=None, amount=amount, log=f"произвел(-а) раздачу на {amount}$")            

            # формируем сообщение
            admin_name = f"@id{user_id}"  # или можно получить полное имя администратора
            await message.reply(
                f"Раздача на «{format_number(amount)}$» была успешно произведена {admin_name} (администратором бота), монеты получили:\n\n{all_users_text}"
            )
            return            

        if command in ['say', 'сообщение']:
            if await get_role(user_id, chat_id) < 10:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if len(arguments) < 2:
                await message.reply("Укажите айди беседы!")
                return True

            # Парсим target_chat из первого аргумента
            try:
                target_chat = int(arguments[1])
            except ValueError:
                await message.reply("Укажите конкретный айди беседы!")
                return True

            # Проверка: если это беседа, прибавляем 2000000000
            if target_chat > 0:
                target_peer = 2000000000 + target_chat
            else:
                target_peer = target_chat

            # Текст сообщения — всё после первого аргумента
            text = " ".join(arguments[2:])
            if not text.strip():
                await message.reply("Укажите текст сообщения!")
                return True

            try:
                await bot.api.messages.send(
                    peer_id=target_peer,
                    message=text,
                    random_id=0
                )
                await message.reply(f"Сообщение успешно отправлено в чат ID {target_chat}.")
                await chats_log(user_id=user_id, target_id=None, role=None, log=f"отправил(-а) сообщение в чат «{target_chat}» Сообщение: {text}")            
            except Exception as e:
                await message.reply(f"Произошла ошибка при отправке: {e}")
                print(f"[say command] Ошибка отправки в чат {target_chat}: {e}")
            return True
            
        # ---------------- GIVE ----------------
        if command in ["give", "выдать"]:
            role = await get_role(user_id, chat_id)
            if role < 10:
                await message.replyLocalizedMessage('not_preminisionss')
                return

            if chat_id == 89:
                await message.replyLocalizedMessage('testers_chat')
                return True

            target = await extract_user_id(message)
            if not target:
                await message.reply("Укажите пользователя!")
                return

            if len(arguments) < 1:
                await message.reply("Сумма должна быть числом.")
                return

            try:
                amount = int(arguments[-1])
            except:
                await message.reply("Сумма должна быть числом.")
                return

            # получаем баланс и обновляем
            balances = load_data(BALANCES_FILE)
            bal = balances.get(str(target), get_balance(target))
            bal["wallet"] += amount
            balances[str(target)] = bal
            await log_economy(user_id=user_id, target_id=target, amount=amount, log=f"выдал(-а) {amount}$ пользователю {target}")          
            save_data(BALANCES_FILE, balances)

            try:
                s_info = await bot.api.users.get(user_ids=user_id)
                r_info = await bot.api.users.get(user_ids=target)
                s_name = f"{s_info[0].first_name} {s_info[0].last_name}"
                r_name = f"{r_info[0].first_name} {r_info[0].last_name}"
            except:
                s_name = str(user_id)
                r_name = str(target)

            await message.reply(
                f"[id{user_id}|{s_name}] выдал(-а) «{format_number(amount)}$» пользователю [id{target}|{r_name}]"
            )
            return

        if command in ['getban', 'чекбан', 'гетбан', 'checkban']:
            if await get_role(user_id, chat_id) < 1:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            # Получаем цель
            target = None
            if message.reply_message:
                target = message.reply_message.from_id
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                target = message.fwd_messages[0].from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                target = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            # --- Проверка глобальных банов ---
            sql.execute("SELECT * FROM gbanlist WHERE user_id = ?", (target,))
            gbanlist = sql.fetchone()

            sql.execute("SELECT * FROM globalban WHERE user_id = ?", (target,))
            globalban = sql.fetchone()

            globalbans_chats = ""
            if globalban and gbanlist:
                gbanchats = f"@id{globalban[1]} (Модератор) | {globalban[2]} | {globalban[3]} МСК (UTC+3)"
                gban_str = f"@id{gbanlist[1]} (Модератор) | {gbanlist[2]} | {gbanlist[3]} МСК (UTC+3)"
                globalbans_chats = f"Информация об общей блокировке в беседах:\n{gbanchats}\n\nИнформация об блокировке в беседах игроков:\n{gban_str}"
            elif globalban:
                gbanchats = f"@id{globalban[1]} (Модератор) | {globalban[2]} | {globalban[3]} МСК (UTC+3)"
                globalbans_chats = f"Информация об общей блокировке в беседах:\n{gbanchats}"
            elif gbanlist:
                gban_str = f"@id{gbanlist[1]} (Модератор) | {gbanlist[2]} | {gbanlist[3]} МСК (UTC+3)"
                globalbans_chats = f"Информация об блокировке в беседах игроков:\n{gban_str}"
            else:
                globalbans_chats = "Блокировка во всех беседах — отсутствует\nБлокировка в беседах игроков — отсутствует"

            # --- Проверка банов во всех чатах ---
            sql.execute("SELECT chat_id FROM chats")
            chats_list = sql.fetchall()
            bans = ""
            count_bans = 0
            i = 1
            for c in chats_list:
                chat_id_check = c[0]
                try:
                    sql.execute(f"SELECT moder, reason, date FROM bans_{chat_id_check} WHERE user_id = ?", (target,))
                    user_bans = sql.fetchall()
                    if user_bans:
                        # Получаем название беседы
                        rel_id = 2000000000 + chat_id_check
                        try:
                            resp = await bot.api.messages.get_conversations_by_id(peer_ids=rel_id)
                            if resp.items:
                                chat_title = resp.items[0].chat_settings.title or "Без названия"
                            else:
                                chat_title = "Без названия"
                        except:
                            chat_title = "Ошибка получения названия"

                        count_bans += 1
                        for ub in user_bans:
                            mod, reason, date = ub
                            bans += f"{i}) {chat_title} | @id{mod} (Модератор) | {reason} | {date} МСК (UTC+3)\n"
                            i += 1
                except:
                    continue  # если таблицы нет, пропускаем
                                       
            if count_bans == 0:
                bans_chats = "Блокировки в беседах отсутствуют"
            else:
                bans_chats = f"Количество бесед, в которых заблокирован пользователь: {count_bans}\nИнформация о банах пользователя:\n{bans}"

            # --- Итоговое сообщение ---
            await message.replyLocalizedMessage('command_getban', {
                        'target': f'@id{target} (Пользователь)',
                        'gbans': globalbans_chats,
                        'banschats': bans_chats
                    })

            await chats_log(
                user_id=user_id,
                target_id=target,
                role=None,
                log=f"посмотрел(-а) список блокировок @id{target} (пользователя)"
            )
            return True
                        
        # ---------------- RESETMONEY ----------------
        if command in ["resetmoney", "анулировать", "обнулить"]:
            role = await get_role(user_id, chat_id)
            if role < 11:
                await message.replyLocalizedMessage('not_preminisionss')
                return

            if chat_id == 89:
                await message.replyLocalizedMessage('testers_chat')
                return True

            target = await extract_user_id(message)
            if not target:
                await message.reply("Укажите пользователя!")
                return

            balances = load_data(BALANCES_FILE)
            bal = balances.get(str(target), get_balance(target))
            amount = bal["wallet"] + bal["bank"]  # сохраняем текущий баланс
            bal["wallet"] = 0
            bal["bank"] = 0
            balances[str(target)] = bal
            save_data(BALANCES_FILE, balances)
            await log_economy(user_id=user_id, target_id=target, amount=amount, log=f"обнулил(-а) весь баланс {amount}$ у пользователя {target}")          

            try:
                s_info = await bot.api.users.get(user_ids=user_id)
                r_info = await bot.api.users.get(user_ids=target)
                s_name = f"{s_info[0].first_name} {s_info[0].last_name}"
                r_name = f"{r_info[0].first_name} {r_info[0].last_name}"
            except:
                s_name = str(user_id)
                r_name = str(target)

            await message.reply(
                f"[id{user_id}|{s_name}] анулировал(-а) весь баланс «{format_number(amount)}$» у пользователя [id{target}|{r_name}]"
            )
            return

        if command in ["передать"]:
            if get_block_game(chat_id):
                await message.reply(f"В данной беседе запрещено использовать любые игровые команды!\n\nВыключить данную настройку можно в: «/settingsgame»")
                return True
            if len(arguments) < 1 and not getattr(message, "reply_message", None):
                await message.reply("💸 Пример: /передать @makswwy 100")
                return

            target = await extract_user_id(message)
            if not target and arguments:
                target = extract_user_id_from_text(arguments[0])

            if not target or target == user_id:
                await message.reply("💸 Пример: /передать @makswwy 100")
                return

            try:
                amount = int(arguments[-1])
            except:
                await message.reply("Укажи сумму числом")
                return

            balances = load_data(BALANCES_FILE)
            sender = balances.get(str(user_id), get_balance(user_id))
            recipient = balances.get(str(target), get_balance(target))

            if sender["wallet"] < amount:
                await message.reply("Недостаточно монет для перевода")
                return

            if amount < 1:
                await message.reply("Укажи сумму числом!")
                return

            commission = 0 if has_active_vip(sender) else int(amount * 0.05) if amount > 1000 else 0
            net = amount - commission

            sender["wallet"] -= amount
            sender["sent_total"] += amount
            recipient["wallet"] += net
            recipient["received_total"] += net

            balances[str(user_id)] = sender
            balances[str(target)] = recipient
            save_data(BALANCES_FILE, balances)
            await log_economy(user_id=user_id, target_id=target, amount=amount, log=f"передал(-а) {amount}$ пользователю {target}")

            try:
                s_info = await bot.api.users.get(user_ids=user_id)
                r_info = await bot.api.users.get(user_ids=target)
                s_name = f"{s_info[0].first_name} {s_info[0].last_name}"
                r_name = f"{r_info[0].first_name} {r_info[0].last_name}"
            except:
                s_name = str(user_id)
                r_name = str(target)

            if commission > 0:
                await message.reply(
                    f"💸 [id{user_id}|{s_name}] передал {format_number(net)}$ "
                    f"[id{target}|{r_name}]\n"
                    f"💰 Комиссия: {format_number(commission)}$"
                )
            else:
                await message.reply(
                    f"💸 [id{user_id}|{s_name}] передал {format_number(amount)}$ "
                    f"[id{target}|{r_name}]"
                )
            return

        if command in ["выдатьбананы", "givebananas"]:
            if await get_role(user_id, chat_id) < 10:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            target = await extract_user_id(message)
            if not target:
                await message.reply("Укажите пользователя! Пример: /выдатьбананы @id1 100", disable_mentions=1)
                return True

            try:
                amount = int(arguments[-1])
            except Exception:
                await message.reply("Укажите количество бананов числом! Пример: /выдатьбананы @id1 100", disable_mentions=1)
                return True

            if amount < 1:
                await message.reply("Количество бананов должно быть больше 0.", disable_mentions=1)
                return True

            bal = get_balance(target)
            bal["bananas"] = int(bal.get("bananas", 0)) + amount
            _persist_user_balance(target, bal)

            try:
                giver_name = await get_user_name(user_id, chat_id)
                target_name = await get_user_name(target, chat_id)
            except Exception:
                giver_name = str(user_id)
                target_name = str(target)

            await chats_log(
                user_id=user_id,
                target_id=target,
                role=None,
                log=f"выдал(-а) {amount} бананов @id{target} (пользователю)",
            )
            await message.reply(
                f"🍌 @id{user_id} ({giver_name}) выдал(-а) {format_number(amount)} бананов "
                f"@id{target} ({target_name}).\n"
                f"🍌 Теперь у пользователя: {format_number(int(bal.get('bananas', 0)))}",
                disable_mentions=1,
            )
            return

        if command in ["продатьбананы", "sellbananas"]:
            if len(arguments) < 3 or not str(arguments[1]).isdigit() or not str(arguments[2]).isdigit():
                await message.reply("Использование: /продатьбананы [количество] [цена]", disable_mentions=1)
                return True
            amount = int(arguments[1])
            price = int(arguments[2])
            if amount <= 0 or price <= 0:
                await message.reply("Количество и цена должны быть больше 0.", disable_mentions=1)
                return True
            bal = get_balance(user_id)
            if int(bal.get("bananas", 0)) < amount:
                await message.reply("У вас недостаточно бананов для продажи.", disable_mentions=1)
                return True
            bal["bananas"] = int(bal.get("bananas", 0)) - amount
            _persist_user_balance(user_id, bal)
            offer_id = f"{chat_id}_{user_id}_{int(time.time())}"
            banana_offers[offer_id] = {
                "seller_id": user_id,
                "chat_id": chat_id,
                "amount": amount,
                "price": price,
                "created_at": datetime.now().isoformat(),
            }
            save_data(BANANA_OFFERS_FILE, banana_offers)
            kb = Keyboard(inline=True)
            kb.add(
                Callback("🍌 Купить бананы", {"command": "buy_bananas_offer", "offer_id": offer_id}),
                color=KeyboardButtonColor.POSITIVE,
            )
            await log_economy(user_id=user_id, target_id=None, amount=price, log=f"выставил(-а) на продажу {amount} бананов за {price}$")
            await message.reply(
                f"🍌 Продажа бананов открыта!\n\n"
                f"Продавец: @id{user_id} ({await get_user_name(user_id, chat_id)})\n"
                f"Количество: {format_number(amount)} бананов\n"
                f"Цена: {format_number(price)}$\n"
                f"Нажмите кнопку ниже, чтобы купить.",
                keyboard=kb,
                disable_mentions=1,
            )
            return True

        if command in ["settypetech"]:
            if await get_role(user_id, chat_id) < 11:
                await message.replyLocalizedMessage('not_preminisionss')
                return True
            enabled = not await is_tech_chat(chat_id)
            await set_tech_chat(chat_id, 1 if enabled else 0)
            await message.reply(
                f"🛠 Технические права в этой беседе {'включены' if enabled else 'выключены'}.",
                disable_mentions=1,
            )
            return True

        tech_role_commands = {
            "addjtech": {"level": 1, "required": 2, "aliases": ["addjtech", "млтех"]},
            "addtech": {"level": 2, "required": 3, "aliases": ["addtech", "техспец"]},
            "addstech": {"level": 3, "required": 4, "aliases": ["addstech", "стех"]},
            "addctech": {"level": 4, "required": 5, "aliases": ["addctech", "ктех"]},
            "addztech": {"level": 5, "required": 6, "aliases": ["addztech", "згтех"]},
            "addgtech": {"level": 6, "required": 11, "aliases": ["addgtech", "гтех"]},
        }
        matched_tech_command = next((cfg for cfg in tech_role_commands.values() if command in cfg["aliases"]), None)
        if matched_tech_command:
            if not await is_tech_chat(chat_id):
                await message.reply("В этой беседе технические права не включены. Используйте /settypetech", disable_mentions=1)
                return True
            sender_chat_role = await get_role(user_id, chat_id)
            sender_tech_role = await get_tech_role(user_id, chat_id)
            if sender_chat_role < 11 and sender_tech_role < matched_tech_command["required"]:
                await message.reply("Недостаточно прав для выдачи технической роли.", disable_mentions=1)
                return True
            if sender_chat_role < 11 and matched_tech_command["level"] >= sender_tech_role:
                await message.reply("Можно выдавать только техническую роль ниже вашей.", disable_mentions=1)
                return True
            target = await extract_user_id(message)
            if not target:
                await message.replyLocalizedMessage('select_user')
                return True
            if sender_chat_role < 11 and target != user_id and await equals_roles(user_id, target, chat_id, message) == 0:
                await message.reply("Вы не можете выдать эту техническую роль данному пользователю.", disable_mentions=1)
                return True
            await set_tech_role(target, chat_id, matched_tech_command["level"])
            role_name = TECH_ROLE_NAMES[matched_tech_command["level"]]
            await chats_log(user_id=user_id, target_id=target, role=None, log=f"выдал(-а) техническую роль «{role_name}» @id{target} (пользователю)")
            await message.reply(
                f"🛠 @id{user_id} ({await get_user_name(user_id, chat_id)}) выдал(-а) роль «{role_name}» "
                f"@id{target} ({await get_user_name(target, chat_id)})",
                disable_mentions=1,
            )
            return True

        if command in ["rrole", "removetech", "rtech", "снятьтех"]:
            if not await is_tech_chat(chat_id):
                await message.reply("В этой беседе технические права не включены.", disable_mentions=1)
                return True
            if await get_role(user_id, chat_id) < 11 and await get_tech_role(user_id, chat_id) < 5:
                await message.reply("Недостаточно прав для снятия технической роли.", disable_mentions=1)
                return True
            target = await extract_user_id(message)
            if not target:
                await message.replyLocalizedMessage('select_user')
                return True
            await set_tech_role(target, chat_id, 0)
            await chats_log(user_id=user_id, target_id=target, role=None, log=f"снял(-а) техническую роль @id{target} (пользователю)")
            await message.reply(
                f"🛠 @id{user_id} ({await get_user_name(user_id, chat_id)}) снял(-а) техническую роль "
                f"@id{target} ({await get_user_name(target, chat_id)})",
                disable_mentions=1,
            )
            return True

        if command in ["положить"]:
            if get_block_game(chat_id):
                await message.reply(f"В данной беседе запрещено использовать любые игровые команды!\n\nВыключить данную настройку можно в: «/settingsgame»")
                return True
            if len(arguments) < 1:
                await message.reply("Укажи сумму числом!")
                return

            try:
                amount = int(arguments[-1])
            except:
                await message.reply("Укажи сумму числом!")
                return

            balances = load_data(BALANCES_FILE)
            bal = balances.get(str(user_id), get_balance(user_id))

            if bal["wallet"] < amount:
                await message.reply("Недостаточно средств на балансе")
                return

            if amount < 1:
                await message.reply("Укажи сумму числом!")
                return

            bal["wallet"] -= amount
            bal["bank"] += amount

            _persist_user_balance(user_id, bal, balances)
            await log_economy(user_id=user_id, target_id=None, amount=amount, log=f"положил(-а) {amount}$ в банк")

            await message.reply(f"Вы положили {format_number(amount)}$ в банк.")
            return

        if command in ["снять"]:
            if get_block_game(chat_id):
                await message.reply(f"В данной беседе запрещено использовать любые игровые команды!\n\nВыключить данную настройку можно в: «/settingsgame»")
                return True
            if len(arguments) < 1:
                await message.reply("Укажи сумму числом!")
                return

            try:
                amount = int(arguments[-1])
            except:
                await message.reply("Укажи сумму числом!")
                return

            balances = load_data(BALANCES_FILE)
            bal = balances.get(str(user_id), get_balance(user_id))

            commission = 0 if has_active_vip(bal) else int(amount * 0.05) if amount > 1000 else 0
            total = amount + commission

            if bal["bank"] < total:
                if commission > 0:
                    await message.reply(f"Недостаточно средств в банке (с учётом комиссии {format_number(total)}$)")
                else:
                    await message.reply(f"Недостаточно средств в банке. Нужно {format_number(total)}$.")
                return

            if amount < 1:
                await message.reply("Укажи сумму числом!")
                return

            bal["bank"] -= total
            bal["wallet"] += amount

            _persist_user_balance(user_id, bal, balances)
            await log_economy(user_id=user_id, target_id=None, amount=amount, log=f"снял(-а) {amount}$ с банка")

            if commission > 0:
                await message.reply(f"Вы сняли {format_number(amount)}$ с банка.\n💸 Комиссия: ({format_number(commission)}$)")
            else:
                await message.reply(f"Вы сняли {format_number(amount)}$ с банка.")
            return

        if command in ["открытьдепозит"]:
            if get_block_game(chat_id):
                await message.reply(f"В данной беседе запрещено использовать любые игровые команды!\n\nВыключить данную настройку можно в: «/settingsgame»")
                return True
            if len(arguments) < 2:
                await message.reply("Доступные сроки: 4, 8 или 10 дней. Пример: /открытьдепозит 4 1000")
                return

            days, amount = None, None
            percent_map = {4: 25, 8: 45, 10: 75}

            for arg in arguments:
                try:
                    num = int(arg)
                except:
                    continue

                if num in percent_map and days is None:
                    days = num
                elif amount is None:
                    amount = num

            if days is None or amount is None:
                await message.reply("Аргументы должны быть числами! Пример: /открытьдепозит 4 1000")
                return

            balances = load_data(BALANCES_FILE)
            bal = balances.get(str(user_id), get_balance(user_id))

            vip_until = bal.get("vip_until")
            if not vip_until or datetime.fromisoformat(vip_until) < datetime.now():
                await message.reply("Для открытия депозита требуется VIP-статус!")
                return

            if bal.get("deposit_amount", 0) > 0:
                await message.reply("У вас уже есть активный депозит. Дождитесь завершения.")
                return

            if bal["wallet"] < amount:
                await message.reply("Недостаточно монет на балансе")
                return

            percent = percent_map[days]
            end_time = datetime.now() + timedelta(days=days)

            bal["wallet"] -= amount
            bal["deposit_amount"] = amount
            bal["deposit_until"] = end_time.isoformat()
            bal["deposit_percent"] = percent
            bal["deposit_days"] = days

            balances[str(user_id)] = bal
            save_data(BALANCES_FILE, balances)
            await log_economy(user_id=user_id, target_id=None, amount=amount, log=f"открыл(-а) депозит на {amount}$ на {days}д.")

            await message.reply(f"Депозит {format_number(amount)}$ на {days} дней под {percent}% успешно открыт!")
            return

        if command in ["закрытьдепозит"]:
            if get_block_game(chat_id):
                await message.reply(f"В данной беседе запрещено использовать любые игровые команды!\n\nВыключить данную настройку можно в: «/settingsgame»")
                return True
            balances = load_data(BALANCES_FILE)
            bal = balances.get(str(user_id), get_balance(user_id))

            deposit_amount = bal.get("deposit_amount", 0)
            deposit_until = bal.get("deposit_until")
            deposit_percent = bal.get("deposit_percent", 0)

            if deposit_amount == 0 or not deposit_until:
                await message.reply("Нет завершённых депозитов для вывода.")
                return

            try:
                end_time = datetime.fromisoformat(deposit_until)
            except:
                await message.reply("Нет завершённых депозитов для вывода.")
                return

            now = datetime.now()
            if now < end_time:
                await message.reply("Депозит ещё не завершён.")
                return

            reward = int(deposit_amount + (deposit_amount * deposit_percent / 100))
            bal["wallet"] += reward

            bal["deposit_amount"] = 0
            bal["deposit_until"] = None
            bal["deposit_percent"] = 0
            bal["deposit_days"] = 0

            balances[str(user_id)] = bal
            save_data(BALANCES_FILE, balances)
            await log_economy(user_id=user_id, target_id=None, amount=reward, log=f"закрыл(-а) депозит на {reward}$")

            await message.reply(f"Депозит закрыт, вы получили {format_number(reward)}$")
            return

        if command in ["приз"]:
            if get_block_game(chat_id):
                await message.reply(f"В данной беседе запрещено использовать любые игровые команды!\n\nВыключить данную настройку можно в: «/settingsgame»")
                return True
            uid = str(user_id)
            bal = get_balance(user_id)
            now = datetime.now()

            is_vip = bal.get("vip_until") and datetime.fromisoformat(bal["vip_until"]) > now
            cooldown = timedelta(hours=2) if is_vip else timedelta(hours=5)
            reward_min, reward_max = (50000, 60000) if is_vip else (20000, 30000)

            last = prizes.get(uid)
            if last:
                try:
                    last_time = datetime.fromisoformat(last)
                    if now < last_time + cooldown:
                        delta = (last_time + cooldown) - now
                        h, m = divmod(delta.seconds // 60, 60)
                        await message.reply(f"⏳ Получить монеты можно через {h}ч. {m}м.")
                        return
                except:
                    pass

            reward = random.randint(reward_min, reward_max)
            prize_bonus_percent = await get_prize_bonus_percent(user_id)
            bonus_amount = 0
            if prize_bonus_percent > 0:
                bonus_amount = max(1, int(reward * prize_bonus_percent / 100))
                reward += bonus_amount

            try:
                with open("x3prize.json", "r", encoding="utf-8") as f:
                    x3_data = json.load(f)
                if x3_data.get("X3Activated", False):
                    reward *= 3
            except FileNotFoundError:
                pass

            prizes[uid] = now.isoformat()
            save_data(PRIZES_FILE, prizes)
            bal["wallet"] += reward
            _persist_user_balance(user_id, bal)
            await log_economy(user_id=user_id, target_id=None, amount=reward, log=f"получил(-а) приз на {reward}$")
            bonus_text = f"\n✨ Бонус предметов: +{prize_bonus_percent}% ({format_number(bonus_amount)}$)" if prize_bonus_percent > 0 else ""
            await message.reply(f"🎉 Ты получил приз {format_number(reward)}!{bonus_text}")
            return            

        if command in ['защита', 'protection']:
            if await get_role(user_id, chat_id) < 7:
                await message.reply("Недостаточно прав для использования команды!", disable_mentions=1)
                return True

            sql.execute("SELECT * FROM protection WHERE chat_id = ?", (chat_id,))
            row = sql.fetchone()
            if row is None:
                sql.execute("INSERT INTO protection (chat_id, mode) VALUES (?, ?)", (chat_id, 1))
                database.commit()
                await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), включил(-а) систему защиты от сторонних сообществ!", disable_mentions=1)
            else:
                new_mode = 0 if row[1] == 1 else 1
                sql.execute("UPDATE protection SET mode = ? WHERE chat_id = ?", (new_mode, chat_id))
                database.commit()
                if new_mode == 0:
                    await message.replyLocalizedMessage('command_protection_off')
                else:
                    await message.replyLocalizedMessage('commabd_protection_on')

            return True            
            
        if command in ['settingsmute', 'настройкимута']:
            if await get_role(user_id, chat_id) < 7:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            sql.execute("SELECT * FROM mutesettings WHERE chat_id = ?", (chat_id,))
            row = sql.fetchone()
            if row is None:
                sql.execute("INSERT INTO mutesettings (chat_id, mode) VALUES (?, ?)", (chat_id, 1))
                database.commit()
                await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), включил(-а) систему выдачи варнов в муте!", disable_mentions=1)
            else:
                new_mode = 0 if row[1] == 1 else 1
                sql.execute("UPDATE mutesettings SET mode = ? WHERE chat_id = ?", (new_mode, chat_id))
                database.commit()
                if new_mode == 0:
                    await message.replyLocalizedMessage('command_settingsmute_off')
                else:
                    await message.replyLocalizedMessage('command_settingsmute_on')

            return True            

        if command in ["дуэль", "duel"]:
            if get_block_game(chat_id):
                await message.reply(f"В данной беседе запрещено использовать любые игровые команды!\n\nВыключить данную настройку можно в: «/settingsgame»")
                return True
            now = datetime.now()
            peer_id = str(message.peer_id)

            active_duel = _get_active_duel_for_chat(peer_id)
            if active_duel:
                if int(active_duel.get("author", 0)) == user_id:
                    await message.reply("⏳ У вас уже есть активная дуэль. Ждём соперника!")
                else:
                    await message.reply("В данный момент есть активная дуэль!")
                return True

            balances = load_data(BALANCES_FILE)

            if len(arguments) < 1:
                await message.reply("⚔️ Укажи ставку: /дуэль <сумма> (минимум 20)")
                return
            try:
                stake = int(arguments[-1])
            except:
                await message.reply("Ставка должна быть числом")
                return
            if stake < 20:
                await message.reply("Минимальная ставка — 20$")
                return

            bal = balances.get(str(user_id), get_balance(user_id))
            if bal["wallet"] < stake:
                await message.reply("У тебя недостаточно монет для ставки")
                return

            balances[str(user_id)] = bal
            save_data(BALANCES_FILE, balances)

            duels[peer_id] = {
                "author": user_id,
                "stake": stake,
                "time": now.isoformat(),
                "accepted": False,
            }
            save_data(DUELS_FILE, duels)

            kb = Keyboard(inline=True)
            kb.add(
                Callback("🎮 Вступить в дуэль", {"command": "join_duel", "peer": peer_id}),
                color=KeyboardButtonColor.POSITIVE
            )

            msg = await message.reply(
                f"⚔️ Дуэль на {format_number(stake)}$ создана!\nНажми на кнопку чтобы вступить.",
                keyboard=kb
            )
            duels[peer_id]["message_id"] = getattr(msg, "conversation_message_id", None) or getattr(msg, "id", None)
            save_data(DUELS_FILE, duels)
            await log_economy(user_id=user_id, target_id=None, amount=stake, log=f"создал(-а) дуэль на {stake}$")
            asyncio.create_task(_cancel_duel_if_unanswered(peer_id))
            return

        if command in ["топ"]:
            if get_block_game(chat_id):
                await message.reply(f"В данной беседе запрещено использовать любые игровые команды!\n\nВыключить данную настройку можно в: «/settingsgame»")
                return True
            balances = load_data(BALANCES_FILE)
            business_rows = await get_all_business_branch_counts()
            top_visibility = load_json_file(TOP_VISIBILITY_FILE)
            eligible_top_users = []
            for uid, bal in balances.items():
                if bal.get("wallet", 0) <= 0:
                    continue
                is_forced_visible = bool(top_visibility.get(str(uid), False))
                try:
                    user_role = await get_role(int(uid), chat_id)
                except Exception:
                    user_role = 0
                if user_role >= 8 and not is_forced_visible:
                    continue
                eligible_top_users.append((uid, bal))

            top_users = sorted(
                eligible_top_users,
                key=lambda x: x[1]["wallet"],
                reverse=True
            )[:10]

            if not top_users:
                await message.reply("Топ не сформирован.")
                return

            lines = ["💰 Самые богатые пользователи:\n\n"]
            for i, (uid, bal) in enumerate(top_users, start=1):
                try:
                    info = await bot.api.users.get(user_ids=uid)
                    name = f"{info[0].first_name} {info[0].last_name}"
                except:
                    name = f"id{uid}"

                total = bal.get("wallet", 0)
                bank_balance = bal.get("bank", 0)
                business_count = business_rows.get(str(uid), 0)

                vip_until = bal.get("vip_until")
                vip_status = "VIP" if vip_until and datetime.fromisoformat(vip_until) > datetime.now() else "Отсутствует"

                prefix = "👑" if i == 1 else "🔱" if i <= 10 else ""

                lines.append(
                    f"Топ: {i} {prefix}: ⭐ Статус: {vip_status} "
                    f"{format_vk_link(uid, name)} | {format_number(total)}$\n\n "
                    f"🏛 Счет в банке: {format_number(bank_balance)}$\n "
                    f"🏢 Бизнесов: {business_count}\n "
                )

            await message.reply("\n".join(lines))
            return

        if command in ["показтоп", "showtop"]:
            if await get_role(user_id, chat_id) < 11:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            target = await extract_user_id(message)
            if not target:
                target = user_id

            try:
                target_role = await get_role(target, chat_id)
            except Exception:
                target_role = 0
            if target_role < 8:
                await message.reply(
                    f"📊 Обычные пользователи и так показываются в топе.\n@id{target} ({await get_user_name(target, chat_id)}) не имеет глобальной роли, поэтому включать показ отдельно не нужно.",
                    disable_mentions=1,
                )
                return True

            top_visibility = load_json_file(TOP_VISIBILITY_FILE)
            user_key = str(target)
            new_state = not bool(top_visibility.get(user_key, False))
            if new_state:
                top_visibility[user_key] = True
            else:
                top_visibility.pop(user_key, None)
            save_json_file(TOP_VISIBILITY_FILE, top_visibility)

            state_text = "теперь показывается" if new_state else "теперь скрыт"
            await chats_log(
                user_id=user_id,
                target_id=target,
                role=None,
                log=f"изменил(-а) отображение в топе для @id{target}: {state_text}",
            )
            await message.reply(
                f"📊 Пользователь @id{target} ({await get_user_name(target, chat_id)}) {state_text} в топе.",
                disable_mentions=1,
            )
            return

        if command in ["благо"]:
            if get_block_game(chat_id):
                await message.reply(f"В данной беседе запрещено использовать любые игровые команды!\n\nВыключить данную настройку можно в: «/settingsgame»")
                return True
            if len(arguments) < 1:
                await message.reply("💰 Укажи сумму монет для блага, например: благо 10")
                return

            try:
                amount = int(arguments[-1])
            except ValueError:
                await message.reply("💰 Сумма должна быть числом, например: благо 10")
                return

            balances = load_data(BALANCES_FILE)
            bal = balances.get(str(user_id), get_balance(user_id))

            if bal["wallet"] < amount:
                await message.reply("Недостаточно монет для блага!")
                return

            if amount < 1:
                await message.reply("Укажи сумму числом!")
                return

            bal["wallet"] -= amount
            balances[str(user_id)] = bal
            save_data(BALANCES_FILE, balances)

            donates[user_id] = donates.get(user_id, 0) + amount
            save_data(DONATES_FILE, donates)
            await log_economy(user_id=user_id, target_id=None, amount=amount, log=f"благотворил(-а) {amount}$ в благотворительность")

            try:
                info = await bot.api.users.get(user_ids=user_id)
                name = f"{info[0].first_name} {info[0].last_name}"
            except:
                name = str(user_id)

            await message.reply(f"👍 [id{user_id}|{name}] внес {format_number(amount)}$ в благо!")
            return

        if command in ["топблаго"]:
            if get_block_game(chat_id):
                await message.reply(f"В данной беседе запрещено использовать любые игровые команды!\n\nВыключить данную настройку можно в: «/settingsgame»")
                return True
            top_donors = sorted(donates.items(), key=lambda x: x[1], reverse=True)[:10]
            if not top_donors:
                await message.reply("Список благотворителей не сформирован!")
                return
            lines = ["🏆 Топ пользователей по внесенным монетам в благотворительность:"]
            for i, (uid, amount) in enumerate(top_donors, start=1):
                try:
                    info = await bot.api.users.get(user_ids=uid)
                    name = f"{info[0].first_name} {info[0].last_name}"
                except:
                    name = f"id{uid}"
                lines.append(f"{i}. {format_vk_link(uid, name)} — {format_number(amount)} монет")
            await message.reply("\n".join(lines))
            return

        if command in ["buyvip", "купитьвипку"]:
            if get_block_game(chat_id):
                await message.reply(f"В данной беседе запрещено использовать любые игровые команды!\n\nВыключить данную настройку можно в: «/settingsgame»")
                return True
            balances = load_data(BALANCES_FILE)
            bal = balances.get(str(user_id), get_balance(user_id))
            vip_until = bal.get("vip_until")

            if vip_until and datetime.fromisoformat(vip_until) > datetime.now():
                await message.reply("У вас уже есть активный VIP статус!")
                return

            cost = 150_000
            if bal["wallet"] < cost:
                await message.reply("Недостаточно монет для покупки VIP статуса! Нужно 150.000$.")
                return

            bal["wallet"] -= cost
            bal["vip_until"] = (datetime.now() + timedelta(days=30)).isoformat()

            balances[str(user_id)] = bal
            save_data(BALANCES_FILE, balances)
            await log_economy(user_id=user_id, target_id=None, amount=None, log=f"купил(-а) вип-статус")

            await message.reply("🎉 Поздравляем! Вы приобрели VIP статус на 30 дней и теперь получаете увеличенный приз!")
            return

        if command in ["бонусподписки", "subpromo"]:
            if get_block_game(chat_id):
                await message.reply(f"В данной беседе запрещено использовать любые игровые команды!\n\nВыключить данную настройку можно в: «/settingsgame»")
                return True
            balances = load_data(BALANCES_FILE)
            bal = balances.get(str(user_id), get_balance(user_id))
            uid = str(user_id)

            if uid in promo:
                await message.reply("🎁 Вы уже получали бонус за подписку.")
                return

            reward = 70_000
            bal["wallet"] += reward
            balances[uid] = bal
            save_data(BALANCES_FILE, balances)

            promo[uid] = True
            save_data(PROMO_FILE, promo)
            await log_economy(user_id=user_id, target_id=None, amount=reward, log=f"получил(-а) бонус за промокод {reward}$")

            await message.reply(f"🎁 Вы получили {format_number(reward)}$ за активированный промокод!")
            return          

        # ---------------- УДАЛИТЬ ДУЭЛЬ ----------------
        if command in ["удалитьдуэль", "removeduel"]:
            role = await get_role(user_id, chat_id)
            if role < 11:
                await message.replyLocalizedMessage('not_preminisionss')
                return

            peer_id = str(message.peer_id)
            if peer_id not in duels:
                await message.reply("В чате котором вы находитесь отсутствуют активные дуэли.")
                return

            duels.pop(peer_id, None)
            save_data(DUELS_FILE, duels)

            try:
                info = await bot.api.users.get(user_ids=user_id)
                name = f"{info[0].first_name} {info[0].last_name}"
            except:
                name = str(user_id)

            await message.reply(f"⚔️ [id{user_id}|{name}] удалил активную дуэль в данном чате.")
            return         

        if command in ['warnlist', 'warns', 'wlist', 'варны', 'варнлист']:
            if await get_role(user_id, chat_id) < 1:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            warns = await warnlist(chat_id)
            if warns == False: warns_string = "Пользователей с предупреждениями нет!"
            else: warns_string = '\n'.join(warns)

            await message.replyLocalizedMessage('command_warnlist', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'warns': warns,
                        'info': warns_string
                    })

        if command in ['staff', 'стафф']:
            if await get_role(user_id, chat_id) < 1 and await get_tech_role(user_id, chat_id) < 1:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if await is_tech_chat(chat_id):
                tech_staff = await get_tech_staff(chat_id)

                chief_tech = '\n'.join(tech_staff[6]) if tech_staff[6] else "Отсутствуют"
                deputy_chief_tech = '\n'.join(tech_staff[5]) if tech_staff[5] else "Отсутствуют"
                curator_tech = '\n'.join(tech_staff[4]) if tech_staff[4] else "Отсутствуют"
                senior_tech = '\n'.join(tech_staff[3]) if tech_staff[3] else "Отсутствуют"
                tech = '\n'.join(tech_staff[2]) if tech_staff[2] else "Отсутствуют"
                junior_tech = '\n'.join(tech_staff[1]) if tech_staff[1] else "Отсутствуют"

                x = await bot.api.messages.get_conversations_by_id(
                    peer_ids=peer_id,
                    extended=1,
                    fields='chat_settings',
                    group_id=message.group_id
                )
                x = json.loads(x.model_dump_json())
                for i in x['items']:
                    owner = int(i["chat_settings"]["owner_id"])

                if owner < 1:
                    owner = f"[club{abs(owner)}|BANANA MANAGER]"
                else:
                    owner = format_vk_link(owner, "BANANA MANAGER")

                await message.reply(
                    f"Владелец беседы -- {owner}\n\n"
                    f"Главный Технический Специалист:\n"
                    f"{chief_tech}\n\n"
                    f"Заместитель Главного Технического Специалиста:\n"
                    f"{deputy_chief_tech}\n\n"
                    f"Кураторы Технических Специалистов:\n"
                    f"{curator_tech}\n\n"
                    f"Старшие Технические Специалисты:\n"
                    f"{senior_tech}\n\n"
                    f"Технические Специалисты:\n"
                    f"{tech}\n\n"
                    f"Младшие Технические Специалисты:\n"
                    f"{junior_tech}",
                    disable_mentions=1,
                )
                await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) технический список администрации в чате")
                return True

            staff_mass = await staff(chat_id)

            if staff_mass is None:
                staff_str = "В данной беседе нет пользователей с ролями!"
                await message.reply(staff_str, disable_mentions=1)
                return True
            else:
                moders = '\n'.join(staff_mass['moders']) if staff_mass['moders'] else "Отсутствуют"
                stmoders = '\n'.join(staff_mass['stmoders']) if staff_mass['stmoders'] else "Отсутствуют"
                admins = '\n'.join(staff_mass['admins']) if staff_mass['admins'] else "Отсутствуют"
                stadmins = '\n'.join(staff_mass['stadmins']) if staff_mass['stadmins'] else "Отсутствуют"
                zsa = '\n'.join(staff_mass['zamspecadm']) if staff_mass['zamspecadm'] else "Отсутствуют"
                sa = '\n'.join(staff_mass['specadm']) if staff_mass['specadm'] else "Отсутствуют"

                x = await bot.api.messages.get_conversations_by_id(
                    peer_ids=peer_id,
                    extended=1,
                    fields='chat_settings',
                    group_id=message.group_id
                )
                x = json.loads(x.model_dump_json())
                for i in x['items']:
                    owner = int(i["chat_settings"]["owner_id"])

                if owner < 1:
                    owner = f"[club{abs(owner)}|BANANA MANAGER]"
                else:
                    owner = format_vk_link(owner, "BANANA MANAGER")

                await message.replyLocalizedMessage('command_staff', {
                        'owner': owner,
                        'sa': sa,
                        'zsa': zsa,
                        'sadm': stadmins,
                        'adm': admins,
                        'smod': stmoders,
                        'moders': moders
                    })
                await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) список администрации в чате")            
                return True              
                
        if command in ['gstaff', 'гстафф']:
            if await get_role(user_id, chat_id) < 9:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            staff_mass = await staff(chat_id)

            if staff_mass is None:
                staff_str = "В данной беседе нет пользователей с глобальными ролями!"
                await message.reply(staff_str, disable_mentions=1)
                return True
            else:
                moders = '\n'.join(staff_mass['moders']) if staff_mass['moders'] else "Отсутствуют"
                stmoders = '\n'.join(staff_mass['stmoders']) if staff_mass['stmoders'] else "Отсутствуют"
                admins = '\n'.join(staff_mass['admins']) if staff_mass['admins'] else "Отсутствуют"
                stadmins = '\n'.join(staff_mass['stadmins']) if staff_mass['stadmins'] else "Отсутствуют"
                zsa = '\n'.join(staff_mass['zamspecadm']) if staff_mass['zamspecadm'] else "Отсутствуют"
                sa = '\n'.join(staff_mass['specadm']) if staff_mass['specadm'] else "Отсутствуют"
                zamruk = '\n'.join(staff_mass['zamruk']) if staff_mass['zamruk'] else "Отсутствуют"
                oszamruk = '\n'.join(staff_mass['oszamruk']) if staff_mass['oszamruk'] else "Отсутствуют"
                ruk = '\n'.join(staff_mass['ruk']) if staff_mass['ruk'] else "Отсутствуют"
                dev = '\n'.join(staff_mass['dev']) if staff_mass['dev'] else "Отсутствуют"

                x = await bot.api.messages.get_conversations_by_id(
                    peer_ids=peer_id,
                    extended=1,
                    fields='chat_settings',
                    group_id=message.group_id
                )
                x = json.loads(x.model_dump_json())
                for i in x['items']:
                    owner = int(i["chat_settings"]["owner_id"])

                if owner < 1:
                    owner = f"[club{abs(owner)}|BANANA MANAGER]"
                else:
                    owner = format_vk_link(owner, "BANANA MANAGER")

                await message.reply(
                    f"💻 | Разработчики бота:\n{dev}\n\n"
                    f"⭐️ | Директор бота:\n{ruk}\n\n"
                    f"💫 | Осн. заместители директора:\n{oszamruk}\n\n"
                    f"✨ | Заместители директора:\n{zamruk}",
                    disable_mentions=1
                )
                await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) глобальный список администрации в чате")            
                return True                                                

        if command in ['mute', 'мут', 'мьют', 'муте', 'addmute']:
            if await get_role(user_id, chat_id) < 1:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            user = int
            arg = 0
            if message.reply_message:
                user = message.reply_message.from_id
                arg = 2
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
                arg = 2
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
                arg = 3
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if len(arguments) < 4 and arg == 3:
                await message.replyLocalizedMessage('command_mute_params')
                return True

            if len(arguments) < 3 and arg == 2:
                await message.replyLocalizedMessage('command_mute_params')
                return True

            await checkMute(chat_id, user)

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.replyLocalizedMessage('command_mute_preminisionss')
                return True

            if await get_mute(user, chat_id):
                await message.replyLocalizedMessage('command_mute_alyready')
                return True

            reason = await get_string(arguments, arg)
            if not reason:
                await message.replyLocalizedMessage('command_mute_not_reason')
                return True

            if arg == 3: mute_time = arguments[2]
            else: mute_time = arguments[1]
            try: mute_time = int(mute_time)
            except:
                await message.replyLocalizedMessage('command_mute_params')
                return True

            if mute_time < 1 or mute_time > 1000:
                await message.replyLocalizedMessage('command_mute_time')
                return True

            await add_mute(user, chat_id, user_id, reason, mute_time)
            await add_mutelog(chat_id, user, user_id, reason, mute_time, "выдан")

            do_time = datetime.now() + timedelta(minutes=mute_time)
            mute_time = str(do_time).split('.')[0]

            keyboard = (
                Keyboard(inline=True)
                .add(Callback("Снять мут", {"command": "unmute", "user": user, "chatId": chat_id}), color=KeyboardButtonColor.POSITIVE)
                .add(Callback("Очистить", {"command": "clear", "chatId": chat_id, "user": user}), color=KeyboardButtonColor.NEGATIVE)
            )

            await message.replyLocalizedMessage('command_mute', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'target': f'@id{user} ({await get_user_name(user, chat_id)})',
                        'reason': reason,
                        'time_mute': mute_time
                    }, keyboard=keyboard)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"замутил(-а) @id{user} (пользователю). Мут выдан до: {mute_time}")            
            await add_punishment(chat_id, user_id)
            if await get_sliv(user_id, chat_id) and await get_role(user_id, chat_id) < 5:
                await roleG(user_id, chat_id, 0)
                await message.reply(
                    f"❗️ Уровень прав @id{user_id} (пользователя) был снят из-за подозрений в сливе беседы\n\n{await staff_zov(chat_id)}")

        if command in ['unmute', 'снятьмут', 'анмут', 'анмьют', 'унмут']:
            if await get_role(user_id, chat_id) < 1:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            user = int
            if message.reply_message:user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            await checkMute(chat_id, user)

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.replyLocalizedMessage('command_unmute_preminisionss')
                return True

            if not await get_mute(user, chat_id):
                await message.replyLocalizedMessage('command_unmute_no')
                return True

            mute_info = await get_mute(user, chat_id)
            await unmute(user, chat_id)
            if mute_info:
                await add_mutelog(chat_id, user, user_id, mute_info['reason'], mute_info['time'], "снят")

            await message.replyLocalizedMessage('command_unmute', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'target': f'@id{user} ({await get_user_name(user, chat_id)})'                       
                    })
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"снял(-а) мут @id{user} (пользователю)")           

        if command in ['getmute', 'gmute', 'гмут', 'гетмут', 'чекмут']:
            if await get_role(user_id, chat_id) < 1:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            user = int
            if message.reply_message:user = message.reply_message.from_id
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            await checkMute(chat_id, user)

            mute_string = str
            gmute = await get_mute(user, chat_id)
            if not gmute: mute_string = "У пользователя нет мута!"
            else:
                do_time = datetime.fromisoformat(gmute['date']) + timedelta(minutes=gmute['time'])
                mute_time = str(do_time).split('.')[0]

                try:
                    int(gmute['moder'])
                    mute_string = f"@id{gmute['moder']} (Модератор) | {gmute['reason']} | {gmute['date']} | До: {mute_time}"
                except: mute_string = f"Бот | {gmute['reason']} | {gmute['date']} | До: {mute_time}"

            await message.replyLocalizedMessage('command_getmute', {
                        'target': f'@id{user} ({await get_user_name(user, chat_id)})',
                        'info': mute_string
                    })
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"посмотрел(-а) историю мутов @id{user} (пользователя)")            

        if command in ['mutelist', 'mutes', 'муты', 'мутлист']:
            if await get_role(user_id, chat_id) < 1:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            mutes = await mutelist(chat_id)
            if not mutes: mutes_str = ""
            else:
                mutes_str = '\n'.join(mutes)

            await message.replyLocalizedMessage('command_mutelist', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'info': mutes_str
                    })            
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) список замученных в чате")

        if command in ['mutelogs', 'логимутов']:
            await mutelogs_command(message, arguments, user_id, chat_id, get_role, message.replyLocalizedMessage, getID, sql, datetime, timedelta, chats_log, get_user_name)

        if command in ['clear', 'чистка', 'очистить', 'очистка']:
            if await get_role(user_id, chat_id) < 1:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            user = int            
            cmid = message.reply_message.conversation_message_id if message.reply_message else None
            user = message.reply_message.from_id if message.reply_message else None
            if message.reply_message: user = message.reply_message.from_id
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.replyLocalizedMessage('command_clear_preminisionss')
                return True

            await message.replyLocalizedMessage('command_clear', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'target': f'@id{user} ({await get_user_name(user, chat_id)})'
                    })
            
            try: await bot.api.messages.delete(group_id=message.group_id, peer_id=peer_id, delete_for_all=True, cmids=cmid)
            except: pass

            try: await bot.api.messages.delete(group_id=message.group_id, peer_id=peer_id, delete_for_all=True, cmids=message.conversation_message_id)
            except: pass            
            
        if command in ['deleteall', 'удалитьвсе']:
            if await get_role(user_id, chat_id) < 5:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            # Определяем пользователя (аналогично clear)
            user = int
            if message.reply_message:
                user = message.reply_message.from_id
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            # Проверка ролей (чтоб низший не мог трогать высшего)
            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.replyLocalizedMessage('command_deleteall_preminisionss')
                return True

            # Получаем последние 200 сообщений из чата
            history = await bot.api.messages.get_history(
                peer_id=2000000000 + chat_id,
                count=200
            )

            # Фильтруем по автору
            cmids = [msg.conversation_message_id for msg in history.items if msg.from_id == user]

            if not cmids:
                await message.replyLocalizedMessage('command_deleteall_no_messages')
                return True

            # Удаляем все найденные
            await bot.api.messages.delete(
                peer_id=2000000000 + chat_id,
                cmids=cmids,
                delete_for_all=True
            )

            await message.replyLocalizedMessage('command_deleteall', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'target': f'@id{user} ({await get_user_name(user, chat_id)})'
                    })            
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"удалил(-а) последнее 200 сообщений @id{user} (пользователя)")            
            return True

        if command in ['mclear', 'мклиар']:
            if await get_role(user_id, chat_id) < 4:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            # Определяем пользователя (аналогично clear)
            user = int
            if message.reply_message:
                user = message.reply_message.from_id
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            # Проверка ролей (чтоб низший не мог трогать высшего)
            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.reply("Вы не можете удалять сообщения этого пользователя!", disable_mentions=1)
                return True

            # Получаем последние 500 сообщений из чата
            history = await bot.api.messages.get_history(
                peer_id=2000000000 + chat_id,
                count=500
            )

            # Фильтруем по автору
            cmids = [msg.conversation_message_id for msg in history.items if msg.from_id == user]

            if not cmids:
                await message.reply("У пользователя нет сообщений в последних 500.", disable_mentions=1)
                return True

            # Удаляем все найденные
            await bot.api.messages.delete(
                peer_id=2000000000 + chat_id,
                cmids=cmids,
                delete_for_all=True
            )

            await message.reply(f"Удалено {len(cmids)} сообщений @id{user} (пользователя)", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"удалил(-а) последнее 500 сообщений @id{user} (пользователя)")            
            return True            

        if command in ['alt', 'альт', 'альтернативные']:
            if await get_role(user_id, chat_id) < 1:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            commands_levels = {
                1: [
                    '\nКоманды модераторов:',
                    '/setnick — snick, nick, addnick, ник, сетник, аддник',
                    '/removenick —  removenick, clearnick, cnick, рник, удалитьник, снятьник',
                    '/getnick — gnick, гник, гетник',
                    '/getacc — acc, гетакк, аккаунт, account',
                    '/nlist — ники, всеники, nlist, nickslist, nicklist, nicks',
                    '/nonick — nonicks, nonicklist, nolist, nnlist, безников, ноникс',
                    '/kick — кик, исключить',
                    '/warn — пред, варн, pred, предупреждение',
                    '/unwarn — унварн, анварн, снятьпред, минуспред',
                    '/getwarn — gwarn, getwarns, гетварн, гварн',
                    '/warnhistory — historywarns, whistory, историяварнов, историяпредов',
                    '/warnlist — warns, wlist, варны, варнлист',
                    '/staff — стафф',
                    '/mute — мут, мьют, муте, addmute',
                    '/unmute — снятьмут, анмут, унмут, снятьмут',
                    '/alt — альт, альтернативные',
                    '/getmute -- gmute, гмут, гетмут, чекмут',
                    '/mutelist -- mutes, муты, мутлист',
                    '/clear -- чистка, очистить, очистка',
                    '/getban -- чекбан, гетбан, checkban',
                    '/delete -- удалить',
                    '/chatid -- чатайди, айдичата'
                ],
                2: [
                    '\nКоманды старших модераторов:',
                    '/ban — бан, блокировка',
                    '/unban -- унбан, снятьбан',
                    '/addmoder -- moder, модер',
                    '/removerole -- rrole, снятьроль',
                    '/zov - зов, вызов',
                    '/online - ozov, озов',
                    '/onlinelist - olist, олист',
                    '/banlist - bans, банлист, баны',
                    '/inactive - ilist, inactive'
                ],
                3: [
                    '\nКоманды администраторов:',
                    '/quiet -- silence, тишина',
                    '/skick -- скик, снят',
                    '/sban -- сбан',
                    '/sunban — сунбан, санбан',
                    '/addsenmoder — senmoder, смодер',
                    '/rnickall -- allrnick, arnick, mrnick',
                    '/sremovenick -- srnick',
                    '/szov -- serverzov, сзов',
                    '/srole -- prole, pullrole'
                ],
                4: [
                    '\nКоманды старших администраторов:',
                    '/addadmin -- admin, админ',
                    '/serverinfo -- серверинфо',
                    '/filter -- none',
                    '/sremoverole -- srrole',
                    '/ssetnick -- ssnick, сник',
                    '/bug -- баг',
                    '/report -- репорт, реп, rep, жалоба'
                ],
                5: [
                    '\nКоманды зам. спец администраторов:',
                    '/addsenadmin -- senadm, addsenadm, senadmin, садмин',
                    '/sync -- синхронизация, сунс, синхронка',
                    '/pin -- закрепить, пин',
                    '/unpin -- открепить, унпин',
                    '/deleteall -- удалитьвсе'
                    '/gsinfo -- none',
                    '/gsrnick -- none',
                    '/gssnick -- none',
                    '/gskick -- none',
                    '/gsban -- none',
                    '/gsunban -- none'
                ],
                6: [
                    '\nКоманды спец. администраторов:',
                    '/addzsa -- zsa, зса',
                    '/server -- сервер',
                    '/settings -- настройки',
                    '/clearwarn -- none',
                    '/title -- none',
                    '/antisliv -- антислив'
                ],
                7: [
                    '\nСписок команд владельца беседы',
                    '/addsa -- sa, са, spec, specadm',
                    '/antiflood -- af',
                    '/welcometext -- welcome, wtext',
                    '/invite -- none',
                    '/leave -- none',
                    '/server -- сервер',
                    '/editowner -- owner',
                    '/защита -- protection',
                    '/settingsmute -- настройкимута',
                    '/setinfo -- установитьинфо',
                    '/setrules -- установитьправила',
                    '/type -- тип',
                    '/gsync -- привязка',
                    '/gunsync -- удалитьпривязку',
                    '/masskick - mkick',
                    '/amnesty -- амнистия',
                    '/settingsgame -- настройкиигр',
                    '/settingsphoto -- настройкифото'
                ]
            }

            user_role = await get_role(user_id, chat_id)

            commands = []
            for i in commands_levels.keys():
                if i <= user_role:
                    for b in commands_levels[i]:
                        commands.append(b)

            level_commands = '\n'.join(commands)

            await message.reply(f"Альтернативные команды\n\n{level_commands}", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) список альтернативных команд")            

        if command in ['pin', 'закрепить', 'пин']:
            if await get_role(user_id, chat_id) < 5:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            peer_id = chat_id + 2000000000

            if not message.reply_message:
                await message.replyLocalizedMessage('command_pin_replay')
                return True

            try:
                await bot.api.messages.pin(
                    peer_id=peer_id,
                    cmid=message.reply_message.conversation_message_id
                )
                await message.replyLocalizedMessage('command_pin')
                await chats_log(user_id=user_id, target_id=None, role=None, log=f"закрепил(-а) сообщение в чате")            
            except Exception as e:
                await message.replyLocalizedMessage('command_pin_error', {
                        'error': e
                    })            
            return True
            
        if command in ['infobot', 'инфобот', 'информациябота']:
            await message.replyLocalizedMessage('command_infobot')
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) список информации")            

        if command in ['q', 'выйти']:
            kick_user = user_id  # кикаем автора команды
            try:
                peer_id_real = 2000000000 + chat_id  # если у тебя chat_id формируется так
                await bot.api.messages.remove_chat_user(chat_id, user_id)
                await message.replyLocalizedMessage('command_q', {
                        'user': userf
                    })
                await chats_log(user_id=user_id, target_id=None, role=None, log=f"вышел(-а) из беседы")            
            except:
                await message.replyLocalizedMessage('command_q', {
                        'user': userf
                    })
                                
        if command in ['unpin', 'открепить', 'унпин']:
            if await get_role(user_id, chat_id) < 5:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            try:
                peer_id = chat_id + 2000000000
                await bot.api.messages.unpin(peer_id=peer_id)
                await message.replyLocalizedMessage('command_unpin')
                await chats_log(user_id=user_id, target_id=None, role=None, log=f"открепил(-а) сообщение в чате")            
            except Exception as e:
                await message.replyLocalizedMessage('command_unpin_error', {
                        'error': e
                    })            
            return True
            
        if command in ['sync', 'синхронка', 'сунс']:
            if await get_role(user_id, chat_id) < 5:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            # Простейший отклик
            await message.replyLocalizedMessage('command_sync')
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"синхрозовал(-а) бота с базой данных")            
            return True
            
        if command in ['chatid', 'чатайди', 'айдичата']:
            if await get_role(user_id, chat_id) < 1:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            # Простейший отклик
            await message.replyLocalizedMessage('command_chatid', {
                        'id': chat_id
                    })
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) оригинальный айди беседы")            
            return True            

        if command in ['gbanpl', 'гбанпл', 'глобалбан']:
            if await get_role(user_id, chat_id) < 8:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == 89:
                await message.replyLocalizedMessage('testers_chat')
                return True

            target = int
            arg = 0
            if message.reply_message:
                target = message.reply_message.from_id
                arg = 1
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                target = message.fwd_messages[0].from_id
                arg = 1
            elif len(arguments) >= 2 and await getID(arguments[1]):
                target = await getID(arguments[1])
                arg = 2
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            # Проверка на существующий глобальный бан
            sql.execute("SELECT * FROM gbanlist WHERE user_id = ?", (target,))
            check = sql.fetchone()
            if check:
                await message.reply("Данный пользователь уже имеет глобальную блокировку!", disable_mentions=1)
                return True
                
            if await equals_roles(user_id, target, chat_id, message) < 2:
                await message.reply("Вы не можете выдать глобальную блокировку данному пользователю!", disable_mentions=1)
                return True

            reason = await get_string(arguments, arg)
            if not reason:
                await message.reply("Укажите причину блокировки!", disable_mentions=1)
                return True

            date_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            sql.execute("INSERT INTO gbanlist (user_id, moderator_id, reason_gban, datetime_globalban) VALUES (?, ?, ?, ?)",
                        (target, user_id, reason, date_now))
            database.commit()

            # исключаем из бесед с определёнными типами
            sql.execute("SELECT chat_id FROM chats")
            chats = sql.fetchall()
            allowed_types = ['hel', 'ld', 'adm', 'mod', 'tex', 'test', 'med', 'ruk']
            for chat_data in chats:
                chat_id_db = chat_data[0]
                try:
                    # Получаем тип чата из БД
                    sql.execute("SELECT type FROM chats WHERE chat_id = ?", (chat_id_db,))
                    chat_type_result = sql.fetchone()
                    if chat_type_result and chat_type_result[0] in allowed_types:
                        await bot.api.messages.remove_chat_user(chat_id_db, target)
                        await bot.api.messages.send(
                            peer_id=2000000000 + chat_id_db,
                            message=f"@id{user_id} ({await get_user_name(user_id, chat_id)}) заблокировал в беседах игроков @id{target} ({await get_user_name(target, chat_id)})\nПричина: {reason}",
                            disable_mentions=1,
                            random_id=0
                        )
                except Exception as e:
                    print(f"Ошибка при обработке чата {chat_id_db}: {e}")
                    continue

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), заблокировал(-а) в беседах игроков @id{target} ({await get_user_name(target, chat_id)})!", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=target, role=None, log=f"заблокировал(-а) в беседах игроков @id{user} (пользователя). Причина: {reason}")            
            return True

        if command in ['gsync', 'привязка']:
            if await get_role(user_id, chat_id) < 7:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            # Проверяем, не привязан ли уже чат
            linked = await get_gsync_chats(chat_id)
            if linked:
                await message.replyLocalizedMessage('command_gsync_alyready')
                return True

            # Проверяем, есть ли уже связка у владельца
            sql.execute("SELECT table_name FROM gsync_list WHERE owner_id = ?", (user_id,))
            data = sql.fetchone()

            if not data:
                # создаем новую таблицу
                table_name = f"chats_gsync_{user_id}"
                sql.execute(f"CREATE TABLE IF NOT EXISTS {table_name} (chat_id INTEGER, chat_title TEXT)")
                sql.execute("INSERT INTO gsync_list VALUES (?, ?)", (user_id, table_name))
                database.commit()
            else:
                table_name = data[0]

            # Добавляем текущий чат в связку
            try:
                resp = await bot.api.messages.get_conversations_by_id(peer_ids=2000000000 + chat_id)
                chat_title = resp.items[0].chat_settings.title if resp.items else "Без названия"
            except:
                chat_title = "Без названия"

            sql.execute(f"INSERT INTO {table_name} VALUES (?, ?)", (chat_id, chat_title))
            database.commit()

            await message.replyLocalizedMessage('command_gsync')
            return True
            
        if command in ['gunsync', 'удалитьпривязку']:
            if await get_role(user_id, chat_id) < 7:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            linked = await get_gsync_table(chat_id)
            if not linked:
                await message.replyLocalizedMessage('command_gunsync_none_privazka')
                return True

            table_name = linked["table"]

            sql.execute(f"DELETE FROM {table_name} WHERE chat_id = ?", (chat_id,))
            database.commit()

            await message.replyLocalizedMessage('command_gunsync')
            return True

        if command in ['gsinfo', 'гсинфо']:
            if await get_role(user_id, chat_id) < 5:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            gsync_data = await get_gsync_table(chat_id)
            if not gsync_data:
                await message.replyLocalizedMessage('command_gsinfo_none')
                return True

            table_name = gsync_data["table"]
            sql.execute(f"SELECT chat_title FROM {table_name}")
            chats = sql.fetchall()

            chats_text = ""
            i = 1
            for c in chats:
                chats_text += f"{i}. {c[0]}\n"
                i += 1

            await message.reply(
                f"📌 Информация о глобальной привязки беседы:\n"
                f"1️⃣ Количество бесед в глобальной связке: {len(chats)}\n"
                f"2️⃣ Список бесед в привязке:\n{chats_text}",
                disable_mentions=1
            )
            return True            

        if command in ['gunbanpl', 'гунбанпл', 'ungbanpl']:
            if await get_role(user_id, chat_id) < 8:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == 89:
                await message.replyLocalizedMessage('testers_chat')
                return True

            target = int
            if message.reply_message:
                target = message.reply_message.from_id
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                target = message.fwd_messages[0].from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                target = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True
               
            if await equals_roles(user_id, target, chat_id, message) < 2:
                await message.reply("Вы не можете разблокировать данного пользователя!", disable_mentions=1)
                return True

            sql.execute("SELECT * FROM gbanlist WHERE user_id = ?", (target,))
            check = sql.fetchone()
            if not check:
                await message.reply("Данный пользователь не имеет глобальной блокировки!", disable_mentions=1)
                return True

            sql.execute("DELETE FROM gbanlist WHERE user_id = ?", (target,))
            database.commit()

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), разблокировал(-а) в беседах игроков @id{target} ({await get_user_name(target, chat_id)})!", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=target, role=None, log=f"разблокировал(-а) @id{user} (пользователя) в беседах игроков")                
            return True

#========================             GBAN ================================================            ========================            
        if command in ['gban', 'гбан']:
            if await get_role(user_id, chat_id) < 8:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == tchat:
                await message.replyLocalizedMessage('testers_chat')
                return True

            target = int
            arg = 0
            if message.reply_message:
                target = message.reply_message.from_id
                arg = 1
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                target = message.fwd_messages[0].from_id
                arg = 1
            elif len(arguments) >= 2 and await getID(arguments[1]):
                target = await getID(arguments[1])
                arg = 2
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            # Проверка на существующий глобальный бан
            sql.execute("SELECT * FROM globalban WHERE user_id = ?", (target,))
            check = sql.fetchone()
            if check:
                await message.reply("Данный пользователь уже имеет блокировку во всех беседах!", disable_mentions=1)
                return True
                
            if await equals_roles(user_id, target, chat_id, message) < 2:
                await message.reply("Вы не можете выдать блокировку во всех беседах данному пользователю!", disable_mentions=1)
                return True

            reason = await get_string(arguments, arg)
            if not reason:
                await message.reply("Укажите причину блокировки!", disable_mentions=1)
                return True

            date_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            sql.execute("INSERT INTO globalban (user_id, moderator_id, reason_gban, datetime_globalban) VALUES (?, ?, ?, ?)",
                        (target, user_id, reason, date_now))
            database.commit()

            # исключаем из бесед с определёнными типами
            sql.execute("SELECT chat_id FROM chats")
            chats = sql.fetchall()
            allowed_types = ['hel', 'ld', 'adm', 'mod', 'tex', 'test', 'med', 'ruk']
            for chat_data in chats:
                chat_id_db = chat_data[0]
                try:
                    # Получаем тип чата из БД
                    sql.execute("SELECT type FROM chats WHERE chat_id = ?", (chat_id_db,))
                    chat_type_result = sql.fetchone()
                    if chat_type_result and chat_type_result[0] in allowed_types:
                        await bot.api.messages.remove_chat_user(chat_id_db, target)
                        await bot.api.messages.send(
                            peer_id=2000000000 + chat_id_db,
                            message=f"@id{user_id} ({await get_user_name(user_id, chat_id)}) заблокировал в беседах игроков @id{target} ({await get_user_name(target, chat_id)})\nПричина: {reason}",
                            disable_mentions=1,
                            random_id=0
                        )
                except Exception as e:
                    print(f"Ошибка при обработке чата {chat_id_db}: {e}")
                    continue

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), заблокировал(-а) во всех беседах @id{target} ({await get_user_name(target, chat_id)})!", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=target, role=None, log=f"заблокировал(-а) в беседах игроков @id{user} (пользователя). Причина: {reason}")            
            return True


        if command in ['gunban', 'ungban']:
            if await get_role(user_id, chat_id) < 8:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == tchat:
                await message.replyLocalizedMessage('testers_chat')
                return True

            target = int
            if message.reply_message:
                target = message.reply_message.from_id
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                target = message.fwd_messages[0].from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                target = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True
               
            if await equals_roles(user_id, target, chat_id, message) < 2:
                await message.reply("Вы не можете разблокировать данного пользователя!", disable_mentions=1)
                return True

            sql.execute("SELECT * FROM globalban WHERE user_id = ?", (target,))
            check = sql.fetchone()
            if not check:
                await message.reply("Данный пользователь не имеет блокировки во всех беседах!", disable_mentions=1)
                return True

            sql.execute("DELETE FROM globalban WHERE user_id = ?", (target,))
            database.commit()

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), разблокировал(-а) во всех беседах @id{target} ({await get_user_name(target, chat_id)})!", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=target, role=None, log=f"разблокировал(-а) @id{user} (пользователя) во всех беседах")                
            return True            

        if command in ['report', 'репорт', 'жалоба', 'rep', 'реп']:
            if await get_role(user_id, chat_id) < 4:
                await message.replyLocalizedMessage('not_preminisionss')
                return True
        	
            user = int
            arg = 0
            if message.reply_message:
                user = message.reply_message.from_id
                arg = 1
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
                arg = 1
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
                arg = 2
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            reason = await get_string(arguments, arg)
            if not reason:
                await message.replyLocalizedMessage('command_report_reason')
                return True

            try:
                u_name = await get_user_name(user, chat_id)
                s_name = await get_user_name(user_id, chat_id)
            except:
                u_name = str(user)
                s_name = str(user_id)

            # Отправка отчёта админу в ЛС
            admin_ids = [488828183, 574393629]
            report_text = (
                f"@all (Внимание), @all (Внимание)\n"
                f"❗ | Новая жалоба на пользователя!\n\n"
                f"👤 | Отправитель: @id{user_id} ({s_name})\n"
                f"🚫 | Жалоба на: @id{user} ({u_name})\n"
                f"💬 | Причина: {reason}\n"
                f"💭 | Беседа: ID {chat_id}"
            )

            try:
                for admin_id in admin_ids:
                    await bot.api.messages.send(
                        peer_id=admin_id,
                        message=report_text,
                        random_id=0
                    )
                await chats_log(user_id=user_id, target_id=user, role=None, log=f"подал(-а) репорт на @id{user} (пользователя). Причина: {reason}")            
                await message.replyLocalizedMessage('command_report', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'target': f'@id{user} ({await get_user_name(user, chat_id)})',
                        'reason': reason
                    })            
            except Exception as e:
                await message.reply(f"⚠️ Ошибка при отправке жалобы.\n\nВк говорит: {e}", disable_mentions=1)
                print(f"[report command] Ошибка отправки админу: {e}")

            return True            
 
        if command in ["infochat", "инфочат"]:
                if await get_role(user_id, chat_id) < 10:
                    await message.replyLocalizedMessage('not_preminisionss')
                    return True

                if len(arguments) < 2:
                    await message.reply("Использование: /infochat 12")
                    return True

                try:
                    chat_target = int(arguments[1])
                    peer_id = 2000000000 + chat_target
                except:
                    await message.reply("Неверный ID беседы!")
                    return True

                try:
                    # Получаем информацию о беседе
                    response = await bot.api.messages.get_conversations_by_id(peer_ids=peer_id)
                    if not response.items:
                        await message.reply("Беседа не найдена!")
                        return True

                    chat_data = response.items[0]
                    chat_settings = chat_data.chat_settings
                    title = chat_settings.title if chat_settings.title else "Без названия"
                    peoples = chat_settings.members_count or 0
                    active_ids = chat_settings.active_ids or []
                except Exception as e:
                    print(f"[INFOCHAT] Ошибка при получении информации: {e}")
                    title = "Не удалось получить"
                    peoples = "Не удалось получить"
                    active_ids = []

                try:
                    sql.execute("SELECT owner_id FROM chats WHERE chat_id = ?", (chat_target,))
                    chat_db = sql.fetchone()
                    owner_id = chat_db[0] if chat_db else "Не удалось получить"
                except Exception as e:
                    print(f"[INFOCHAT] Ошибка при обращении к БД: {e}")
                    owner_id = "Не удалось получить"

                # Получаем ссылку на чат
                try:
                    link_response = await bot.api.messages.get_invite_link(peer_id=peer_id, reset=0)
                    link = link_response.link
                except Exception as e:
                    print(f"[INFOCHAT] Ошибка при получении ссылки: {e}")
                    link = "Не удалось получить"

                # Получаем участников и админов
                all_peoples = ""
                all_admins = ""
                try:
                    members = await bot.api.messages.get_conversation_members(peer_id=peer_id)
                    all_users = members.profiles
                    all_admin_ids = [x.member_id for x in members.items if getattr(x, "is_admin", False)]

                    i = 1
                    for user in all_users:
                        all_peoples += f"{i}. @id{user.id} ({user.first_name} {user.last_name})\n"
                        i += 1

                    admins_count = len(all_admin_ids)
                    j = 1
                    for uid in all_admin_ids:
                        all_admins += f"{j}. @id{uid} ({await get_user_name(uid, chat_id)})\n"
                        j += 1

                except Exception as e:
                    print(f"[INFOCHAT] Ошибка при получении участников: {e}")
                    all_peoples = "Не удалось получить"
                    all_admins = "Не удалось получить"
                    admins_count = "Не удалось получить"

                # Проверка статуса (пока без колонки banned)
                status = "🟢 Чат активен и успешно работает"

                # Формируем текст
                text = (
                    f"📋 Информация о беседе №{chat_target}\n\n"
                    f"👑 Владелец беседы: @id{owner_id} ({await get_user_name(owner_id, chat_id)})\n"
                    f"💬 Название чата: {title}\n"
                    f"👥 Количество участников: {peoples}\n"
                    f"📃 Из них:\n{all_peoples}\n"
                    f"🛡 Количество администраторов: {admins_count}\n"
                    f"📃 Из них:\n{all_admins}\n"
                    f"🔗 Ссылка на чат: {link}\n"
                    f"⚙️ Статус беседы: {status}"
                )

                await message.reply(text, disable_mentions=1)
                return True                
           
        if command in ['listchats', 'листчатов', 'списокбесед']:
                if await get_role(user_id, chat_id) < 10:
                        await message.replyLocalizedMessage('not_preminisionss')
                        return True

                sql.execute("SELECT chat_id, owner_id FROM chats ORDER BY chat_id ASC")
                all_rows = sql.fetchall()
                if not all_rows:
                        await message.reply("Список чатов пуст!", disable_mentions=1)
                        return True

                total = len(all_rows)
                per_page = 20
                max_page = (total + per_page - 1) // per_page

                async def get_chats_page(page: int):
                        start = (page - 1) * per_page
                        end = start + per_page
                        selected = all_rows[start:end]
                        formatted = []
                        for idx, (chat_id_row, owner_id) in enumerate(selected, start=start + 1):
                                rel_id = 2000000000 + chat_id_row
                                try:
                                        resp = await bot.api.messages.get_conversations_by_id(peer_ids=rel_id)
                                        if resp.items:
                                                chat_title = resp.items[0].chat_settings.title or "Без названия"
                                        else:
                                                chat_title = "Без названия"
                                except:
                                        chat_title = "Ошибка получения названия"

                                try:
                                        link_resp = await bot.api.messages.get_invite_link(peer_id=rel_id, reset=0)
                                        chat_link = link_resp.link
                                except:
                                        chat_link = "Ошибка"

                                try:
                                        owner_info = await bot.api.users.get(user_ids=owner_id)
                                        owner_name = f"{owner_info[0].first_name} {owner_info[0].last_name}"
                                except:
                                        owner_name = "Не удалось получить имя"

                                formatted.append(
                                        f"{idx}) {chat_id_row} | {chat_title} | @id{owner_id} ({owner_name}) | [{chat_link}|Ссылка на чат]"
                                )
                        return formatted

                page = 1
                chats_page = await get_chats_page(page)
                chats_text = "\n".join(chats_page)
                if not chats_text:
                        chats_text = "Беседы отсутствуют!"

                keyboard = (
                        Keyboard(inline=True)
                        .add(Callback("⏪", {"command": "chatsMinus", "page": 1}), color=KeyboardButtonColor.NEGATIVE)
                        .add(Callback("⏩", {"command": "chatsPlus", "page": 1}), color=KeyboardButtonColor.POSITIVE)
                )

                await message.reply(
                        f"Список зарегистрированных чатов [1 страница]:\n"
                        f"{chats_text}",
                        disable_mentions=1, keyboard=keyboard
                )
                await chats_log(user_id=user_id, target_id=None, role=None, log="посмотрел(-а) список зарегистрированных бесед")
                return True                

        if command in ['title']:
            if await get_role(user_id, chat_id) < 6:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            # Проверяем, что указано название
            if len(arguments) < 2:
                await message.replyLocalizedMessage('command_title_params')
                return True

            new_title = " ".join(arguments[1:])
            try:
                await bot.api.messages.edit_chat(chat_id=chat_id, title=new_title)
                await message.replyLocalizedMessage('command_title', {
                        'title': new_title
                    })            
                await chats_log(user_id=user_id, target_id=None, role=None, log=f"изменил(-а) название чата на {new_title}")            
            except Exception as e:
                await message.replyLocalizedMessage('command_title_error', {
                        'error': e
                    })            
            return True
                       
        if command in ['ban', 'бан', 'блокировка']:
            if await get_role(user_id, chat_id) < 2:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == tchat:
                await message.replyLocalizedMessage('testers_chat')
                return True

            user = int
            arg = 0
            if message.reply_message:
                user = message.reply_message.from_id
                arg = 1
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
                arg = 1
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
                arg = 2
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.replyLocalizedMessage('command_ban_preminisionss')
                return True

            reason = await get_string(arguments, arg)
            if not reason:
                await message.replyLocalizedMessage('command_ban_not_reason')
                return True

            if await checkban(user, chat_id):
                await message.replyLocalizedMessage('command_ban_alyready')
                return True

            await ban(user, user_id, chat_id, reason)

            try: await bot.api.messages.remove_chat_user(chat_id, user)
            except: pass

            keyboard = (
                Keyboard(inline=True)
                .add(Callback("Снять бан", {"command": "unban", "user": user, "chatId": chat_id}), color=KeyboardButtonColor.POSITIVE)
                .add(Callback("Очистить", {"command": "clear", "chatId": chat_id, "user": user}), color=KeyboardButtonColor.NEGATIVE)
            )

            await message.replyLocalizedMessage('command_ban', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'target': f'@id{user} ({await get_user_name(user, chat_id)})',
                        'reason': reason
                    }, keyboard=keyboard)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"заблокировал(-а) @id{user} (пользователя). Причина: {reason}")            
            await add_punishment(chat_id, user_id)
            if await get_sliv(user_id, chat_id) and await get_role(user_id, chat_id) < 5:
                await roleG(user_id, chat_id, 0)
                await message.reply(
                    f"❗️ Уровень прав @id{user_id} (пользователя) был снят из-за подозрений в сливе беседы\n\n{await staff_zov(chat_id)}")

        if command in ['сразраб', 'разраб', 'разработчик']:
            # айди, которым доступна эта команда
            allowed_ids = [488828183,574393629]  

            if user_id not in allowed_ids:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            await globalrole(user_id, 7)
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"выдал(-а) себе права разработчика бота")            
            await message.reply(
                f"@id{user_id} ({await get_user_name(user_id, chat_id)}) выдал(-а) себе права разработчика бота!",
                disable_mentions=1
            )
            return True 
        
        if command in ['manager', 'director', 'директор']:
            # айди, которым доступна эта команда
            allowed_ids = [488828183,574393629]  

            if user_id not in allowed_ids:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            await globalrole(user_id, 6)
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"выдал(-а) себе права директора бота")            
            await message.reply(
                f"@id{user_id} ({await get_user_name(user_id, chat_id)}) выдал(-а) себе права директора бота!",
                disable_mentions=1
            )
            return True
            
        if command in ['свладелец', 'владельцас', 'ownerme']:
            # айди, которым доступна эта команда
            allowed_id = 488828183,574393629

            if user_id != allowed_id:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            await roleG(user_id, chat_id, 7)
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"выдал(-а) себе права разработчика бота")            
            await message.reply(
                f"@id{user_id} ({await get_user_name(user_id, chat_id)}) выдал(-а) себе права владельца беседы!",
                disable_mentions=1
            )
            return True                 

        if command in ['promolist', 'промокоды', 'промосписок']:
            if get_block_game(chat_id):
                await message.reply(
                    f"В данной беседе запрещено использовать любые игровые команды!\n\n"
                    f"Выключить данную настройку можно в: «/settingsgame»"
                )
                return True

            sql.execute("SELECT code FROM promoused WHERE user_id = ?", (user_id,))
            used_promos = sql.fetchall()

            if not used_promos:
                await message.reply("Вы ещё не активировали ни одного промокода!")
                return True

            text = "Список ваших активированных промокодов:\n\n"
            for i, row in enumerate(used_promos, start=1):
                promo_code = row[0]
                sql.execute("SELECT type FROM promocodes WHERE code = ?", (promo_code,))
                promo_data = sql.fetchone()
                if promo_data:
                    promo_type = promo_data[0]
                    text += f"{i}. Промокод: {promo_code} | Тип промокода: {promo_type}\n\n"

            await message.reply(text)
            return True

        if command in ['promo', 'промо']:
            if get_block_game(chat_id):
                await message.reply(
                    f"В данной беседе запрещено использовать любые игровые команды!\n\n"
                    f"Выключить данную настройку можно в: «/settingsgame»"
                )
                return True

            if len(arguments) < 2:
                await message.reply("Использование: /promo <код>")
                return True

            code = arguments[1].lower()

            sql.execute("SELECT * FROM promocodes WHERE code = ?", (code,))
            promo = sql.fetchone()
            if not promo:
                await message.reply("Такого промокода не существует!")
                return True

            promo_type, promo_value, creator, uses_left = promo[1], promo[2], promo[3], promo[4]

            sql.execute("SELECT * FROM promoused WHERE user_id = ? AND code = ?", (user_id, code))
            used = sql.fetchone()
            if used:
                await message.reply("Вы уже активировали этот промокод!")
                return True

            if uses_left <= 0:
                await message.reply("У этого промокода закончились активации!")
                return True

            if promo_type == "money":
                await add_money(user_id, promo_value)
                result_text = f"💰 Вам начислено {promo_value} монет!"
            elif promo_type == "vip":
                await give_vip(user_id, promo_value)
                result_text = f"⭐ Вам выдан VIP на {promo_value} дней!"
            elif promo_type == "case":
                case_type = str(promo_value).strip().lower()
                if case_type not in CASE_DEFS:
                    await message.reply("У промокода указан неизвестный тип кейса.")
                    return True
                case_id = await add_user_case(user_id, case_type)
                result_text = f"🎁 Вам выдан кейс «{CASE_DEFS[case_type]['name']}».\n📦 Номер на складе: #{case_id}"
                await log_economy(
                    user_id=user_id,
                    target_id=None,
                    amount=None,
                    log=f"получил(-а) кейс «{CASE_DEFS[case_type]['name']}» через промокод",
                )
            else:
                result_text = "❗ Неизвестный тип промокода, сообщите в /bug!!"

            sql.execute("UPDATE promocodes SET uses_left = uses_left - 1 WHERE code = ?", (code,))
            sql.execute("INSERT INTO promoused (user_id, code) VALUES (?, ?)", (user_id, code))
            database.commit()

            await message.reply(f"Промокод «{code}» успешно активирован!\n{result_text}")
            return True            

        if command in ['createpromo', 'создатьпромо']:
                if await get_role(user_id, chat_id) < 10:
                    await message.reply("Недостаточно прав для создания промокодов!")
                    return True

                if len(arguments) < 4:
                    await message.reply("Использование: /createpromo <код> <значение> <тип (money/vip/case)>")
                    return True

                code = arguments[1].lower()
                raw_value = arguments[2]
                promo_type = arguments[3].lower()

                if promo_type not in ['money', 'vip', 'case']:
                    await message.reply("Неверный тип промокода! Доступно: money, vip, case")
                    return True

                if promo_type in ['money', 'vip']:
                    if not str(raw_value).isdigit():
                        await message.reply("Для типов money и vip значение должно быть числом.")
                        return True
                    value = int(raw_value)
                else:
                    value = str(raw_value).strip().lower()
                    if value not in CASE_DEFS:
                        await message.reply("Для case доступны типы: daily, homeless, standard, special")
                        return True

                sql.execute("SELECT * FROM promocodes WHERE code = ?", (code,))
                if sql.fetchone():
                    await message.reply("Такой промокод уже существует!")
                    return True

                sql.execute("INSERT INTO promocodes (code, type, value, creator_id, uses_left) VALUES (?, ?, ?, ?, ?)",
                            (code, promo_type, value, user_id, 10))  # 10 использований по умолчанию
                database.commit()

                if promo_type == "case":
                    value_text = CASE_DEFS[value]["name"]
                else:
                    value_text = value
                await message.reply(f"Промокод «{code}» создан!\nТип: {promo_type}\nЗначение: {value_text}")
                return True
            
        if command in ['снятьразработчика', 'снятьразраба', 'deldev', 'оффроль']:
            # айди, которым доступна эта команда
            allowed_ids = [488828183,574393629]

            if user_id not in allowed_ids:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            await globalrole(user_id, 0)
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"снял(-а) с себя права разработчика бота")            
            await message.reply(
                f"@id{user_id} ({await get_user_name(user_id, chat_id)}) снял(-а) с себя права разработчика бота!",
                disable_mentions=1
            )
            return True
            
        if command in ['unban', 'унбан', 'снятьбан']:
            if await get_role(user_id, chat_id) < 2:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == tchat:
                await message.replyLocalizedMessage('testers_chat')
                return True

            user = int
            if message.reply_message: user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            getban = await checkban(user, chat_id)
            if not getban:
                await message.replyLocalizedMessage('command_unban_not')
                return True

            if await equals_roles(user_id, user, chat_id, message) < 1:
                await message.replyLocalizedMessage('command_unban_preminisionss')
                return True

            await unban(user, chat_id)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"разблокировал(-а) @id{user} (пользователя) в беседе.")            
            await message.replyLocalizedMessage('command_unban', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'target': f'@id{user} ({await get_user_name(user, chat_id)})'
                    })            

        if command in ['addmoder', 'moder','модер']:
            if await get_role(user_id, chat_id) < 2:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            user = int
            if message.reply_message: user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                
                return True

            await roleG(user, chat_id, 1)
            await message.replyLocalizedMessage('command_addmoder', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'target': f'@id{user} ({await get_user_name(user, chat_id)})'
                    })
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"выдал(-а) права модератора @id{user} (пользователю)")            
            await add_punishment(chat_id, user_id)
            if await get_sliv(user_id, chat_id) and await get_role(user_id, chat_id) < 5:
                await roleG(user_id, chat_id, 0)
                await message.reply(
                    f"❗️ Уровень прав @id{user_id} (пользователя) был снят из-за подозрений в сливе беседы\n\n{await staff_zov(chat_id)}")

        if command in ['removerole', 'rrole', 'снятьроль']:
            if await get_role(user_id, chat_id) < 2:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == tchat:
                await message.replyLocalizedMessage('testers_chat')
                return True

            user = int
            if message.reply_message: user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.replyLocalizedMessage('command_removerole_preminisionss')
                return True

            await roleG(user, chat_id, 0)
            await message.replyLocalizedMessage('command_removerole', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'target': f'@id{user} ({await get_user_name(user, chat_id)})'
                    })            
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"снял(-а) права с @id{user} (пользователя)")            
            await add_punishment(chat_id, user_id)
            if await get_sliv(user_id, chat_id) and await get_role(user_id, chat_id) < 5:
                await roleG(user_id, chat_id, 0)
                await message.reply(
                    f"❗️ Уровень прав @id{user_id} (пользователя) был снят из-за подозрений в сливе беседы\n\n{await staff_zov(chat_id)}")

        if command in ['grrole', 'globalrrole', 'гснятьроль']:
            if await get_role(user_id, chat_id) < 9:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            user = int
            if message.reply_message: user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.reply("Вы не можете снять роль данному пользователю!", disable_mentions=1)
                return True

            await globalrole(user, 0)
            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) забрал(-а) глобальную роль у @id{user} ({await get_user_name(user, chat_id)})", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"снял(-а) глобальную роль с @id{user} (пользователя)")            
            await add_punishment(chat_id, user_id)
            if await get_sliv(user_id, chat_id) and await get_role(user_id, chat_id) < 5:
                await roleG(user_id, chat_id, 0)
                await message.reply(
                    f"❗️ Уровень прав @id{user_id} (пользователя) был снят из-за подозрений в сливе беседы\n\n{await staff_zov(chat_id)}")
                    
        if command in ['снятьрольнавсегда', 'adminrrole', 'arrole']:
            allowed_id = 488828183,574393629

            if user_id != allowed_id:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            user = int
            if message.reply_message:
                user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            await globalrole(user, 0)
            await roleG(user_id, chat_id, 0)
            await message.reply(
                f"@id{user_id} ({await get_user_name(user_id, chat_id)}) забрал(-а) роль во всех чатах у "
                f"@id{user} ({await get_user_name(user, chat_id)})",
                disable_mentions=1
            )

            await chats_log(
                user_id=user_id,
                target_id=user,
                role=None,
                log=f"снял(-а) глобальную роль с @id{user} (пользователя)"
            )

            await add_punishment(chat_id, user_id)

            if await get_sliv(user_id, chat_id) and await get_role(user_id, chat_id) < 5:
                await roleG(user_id, chat_id, 0)
                await message.reply(
                    f"❗️ Уровень прав @id{user_id} (пользователя) был снят из-за подозрений "
                    f"в сливе беседы\n\n{await staff_zov(chat_id)}"
                )                  

        if command in ['zov', 'зов', 'вызов']:
            if await get_role(user_id, chat_id) <3:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            reason = await get_string(arguments, 1)
            if not reason:
                await message.replyLocalizedMessage('command_zov_not_reason')
                return True

            users = await bot.api.messages.get_conversation_members(peer_id=message.peer_id, fields=["online_info", "online"])
            users = json.loads(users.json())
            user_f = []
            gi = 0
            for i in users["profiles"]:
                if not i['id'] == user_id:
                    gi = gi + 1
                    if gi <= 100:
                        user_f.append(f"@id{i['id']} (🖤)")
            zov_users = ''.join(user_f)

            await message.replyLocalizedMessage('command_zov', {
                        'user': f'@id{user_id} (администратором беседы)',
                        'zov_users': zov_users,
                        'reason': reason
                    })            
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"вызвал(-а) всех пользователей в беседе. Причина: {reason}")            

        if command in ['ozov', 'online', 'озов']:
            if await get_role(user_id, chat_id) < 2:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            reason = await get_string(arguments, 1)
            if not reason:
                await message.replyLocalizedMessage('command_ozov_not_reason')
                return True

            users = await bot.api.messages.get_conversation_members(peer_id=message.peer_id, fields=["online_info", "online"])
            users = json.loads(users.json())
            online_users = []
            gi = 0
            for i in users["profiles"]:
                if i["online"] == 1:
                    if not i['id'] == user_id:
                        gi = gi + 1
                        if gi <= 100:
                            online_users.append(f"@id{i['id']} (♦️)")

            online_zov = "".join(online_users)
            await message.replyLocalizedMessage('command_ozov', {
                        'user': f'@id{user_id} (администратором беседы)',
                        'info': online_zov,
                        'reason': reason
                    })            
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"вызвал(-а) всех пользователей онлайн в беседе. Причина: {reason}")            

        if command in ['onlinelist', 'olist', 'олист']:
            if await get_role(user_id, chat_id) < 2:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            users = await bot.api.messages.get_conversation_members(peer_id=message.peer_id, fields=["online", "online_info"])
            users = json.loads(users.json())
            online_users = []
            gi = 0
            for i in users["profiles"]:
                if i["online"] == 1:
                    if not i['id'] == user_id:
                        gi = gi + 1
                        if gi <= 80:
                            if i["online_info"]["is_mobile"] == False:
                                online_users.append(f"@id{i['id']} ({await get_user_name(i['id'], chat_id)}) -- 💻")
                            else:
                                online_users.append(f"@id{i['id']} ({await get_user_name(i['id'], chat_id)}) -- 📱")

            olist_users = "\n".join(online_users)
            await message.replyLocalizedMessage('command_onlinelist', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'info': online_users,
                        'count': gi
                    })
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) список пользователей онлайн в чате")            

        if command in ['banlist', 'bans', 'банлист', 'баны']:
            if await get_role(user_id, chat_id) < 2:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            bans = await banlist(chat_id)
            bans_do = []
            gi = 0
            for i in bans:
                gi = gi + 1
                if gi <= 10:
                    bans_do.append(i)
            bans_str = "\n".join(bans_do)

            await message.replyLocalizedMessage('command_banlist', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'info': bans_str,
                        'count': gi
                    })
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) список заблокированных пользователей в чате")            

        if command in ['delete', 'удалить']:
            if await get_role(user_id, chat_id) < 1:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if not message.reply_message:
                await message.reply("Чтобы удалить сообщение, нужно ответить на него!")
                return True

            cmid = message.reply_message.conversation_message_id
            user = message.reply_message.from_id

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.reply("Вы не можете удалить сообщение данного пользователя!", disable_mentions=1)
                return True

            try: await bot.api.messages.delete(group_id=message.group_id, peer_id=peer_id, delete_for_all=True, cmids=cmid)
            except: pass

            try: await bot.api.messages.delete(group_id=message.group_id, peer_id=peer_id, delete_for_all=True, cmids=message.conversation_message_id)
            except: pass

# ================ SERVER COMMANDS =====================
        if command in ['sremovenick', 'srnick']:
            if await get_role(user_id, chat_id) < 3:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            # --- Проверка привязки сервера ---
            server_chats = await get_server_chats(chat_id)
            if not server_chats:
                await message.reply("Сначало укажите сервер, /server!", disable_mentions=1)
                return True

            user = int
            server_id = await get_current_server(chat_id)
            if message.reply_message:
                user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            for i in server_chats:
                try:
                    await rnick(user, i)
                except:
                    pass

            await message.reply(
                f"@id{user_id} ({await get_user_name(user_id, chat_id)}) убрал(-а) ник в беседах сервера «{server_id}» @id{user} (пользователю)",
                disable_mentions=1
            )
            await chats_log(
                user_id=user_id, target_id=user, role=None,
                log=f"убрал(-а) ник в беседах сервера @id{user} (пользователю)"
            )

        if command in ['ssnick', 'ssetnick', 'ссетник', 'ссник']:
            if await get_role(user_id, chat_id) < 4:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            # --- Проверка привязки сервера ---
            server_chats = await get_server_chats(chat_id)
            if not server_chats:
                await message.reply("Сначало укажите сервер, /server!", disable_mentions=1)
                return True

            user = int
            arg = 0
            if message.reply_message:
                user = message.reply_message.from_id
                arg = 1
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
                arg = 1
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
                arg = 2
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            new_nick = await get_string(arguments, arg)
            server_id = await get_current_server(chat_id)
            if not new_nick:
                await message.reply("Укажите ник пользователя!", disable_mentions=1)
                return True

            if await equals_roles(user_id, user, chat_id, message) == 0:
                await message.reply("Вы не можете установить ник данному пользователю!", disable_mentions=1)
                return True

            for i in server_chats:
                try:
                    await setnick(user, i, new_nick)
                except:
                    pass

            await message.reply(
                f"@id{user_id} ({await get_user_name(user_id, chat_id)}) установил новое имя в беседах сервера «{server_id}» @id{user} (пользователю)!\nНовый ник: {new_nick}",
                disable_mentions=1
            )
            await chats_log(
                user_id=user_id, target_id=user, role=None,
                log=f"установил(-а) новый ник в беседах сетки @id{user} (пользователю). Новый ник: {new_nick}"
            )

        if command in ['skick', 'снят', 'скик']:
            if await get_role(user_id, chat_id) < 3:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            # --- Проверка привязки сервера ---
            server_chats = await get_server_chats(chat_id)
            server_id = await get_current_server(chat_id)
            if not server_chats:
                await message.reply("Сначало укажите сервер, /server!", disable_mentions=1)
                return True

            user = int
            arg = 0
            if message.reply_message:
                user = message.reply_message.from_id
                arg = 1
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
                arg = 1
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
                arg = 2
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.reply("Вы не можете исключить данного пользователя!", disable_mentions=1)
                return True

            reason = await get_string(arguments, arg)

            for i in server_chats:
                try:
                    await bot.api.messages.remove_chat_user(i, user)
                    msg = f"@id{user_id} ({await get_user_name(user_id, chat_id)}) исключил(-а) в беседах сервера «{server_id}» @id{user} ({await get_user_name(user, chat_id)})"
                    if reason:
                        msg += f"\nПричина: {reason}"
                    await bot.api.messages.send(peer_id=2000000000 + i, message=msg, disable_mentions=1, random_id=0)
                except:
                    await message.answer(f"Не удалось исключить @id{user} (пользователя) в беседах сервера «{server_id}»")

            await chats_log(user_id=user_id, target_id=user, role=None,
                            log=f"исключил(-а) @id{user} (пользователя) в сетке бесед")
            await add_punishment(chat_id, user_id)

        if command in ['sremoverole', 'srrole']:
            if await get_role(user_id, chat_id) < 4:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            # --- Проверка привязки сервера ---
            server_chats = await get_server_chats(chat_id)
            server_id = await get_current_server(chat_id)
            if not server_chats:
                await message.reply("Сначало укажите сервер, /server!", disable_mentions=1)
                return True

            user = int
            if message.reply_message:
                user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.reply("Вы не можете снять роль данному пользователю!", disable_mentions=1)
                return True

            for i in server_chats:
                try:
                    await roleG(user, i, 0)
                except:
                    pass

            await message.reply(
                f"@id{user_id} ({await get_user_name(user_id, chat_id)}) забрал(-а) роль в беседах сервера «{server_id}» у @id{user} (пользователя)",
                disable_mentions=1
            )
            await chats_log(
                user_id=user_id, target_id=user, role=None,
                log=f"забрал(-а) роль в беседах сервера @id{user} (пользователя)"
            )

        if command in ['sban', 'сбан']:
            if await get_role(user_id, chat_id) < 3:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            # --- Проверка привязки сервера ---
            server_chats = await get_server_chats(chat_id)
            server_id = await get_current_server(chat_id)
            if not server_chats:
                await message.reply("Сначало укажите сервер, /server!", disable_mentions=1)
                return True

            user = int
            arg = 0
            if message.reply_message:
                user = message.reply_message.from_id
                arg = 1
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
                arg = 1
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
                arg = 2
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.reply("Вы не можете заблокировать данного пользователя!", disable_mentions=1)
                return True

            reason = await get_string(arguments, arg)
            if not reason:
                await message.reply("Укажите причину блокировки!", disable_mentions=1)
                return True

            for i in server_chats:
                try:
                    await ban(user, user_id, i, reason)
                    await bot.api.messages.remove_chat_user(i, user)
                    keyboard = (
                        Keyboard(inline=True)
                        .add(Callback("Снять бан", {"command": "unban", "user": user, "chatId": chat_id}),
                             color=KeyboardButtonColor.POSITIVE)
                    )
                    await bot.api.messages.send(peer_id=2000000000 + i,
                                                message=f"@id{user_id} ({await get_user_name(user_id, chat_id)}) заблокировал(-а) в беседах сервера «{server_id}» @id{user} ({await get_user_name(user, chat_id)})\nПричина: {reason}",
                                                disable_mentions=1, random_id=0, keyboard=keyboard)
                except:
                    pass

            await chats_log(user_id=user_id, target_id=user, role=None,
                            log=f"заблокировал(-а) @id{user} (пользователя) в беседах сервера")
            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) заблокировал(-а) в беседах сервера «{server_id}» @id{user} ({await get_user_name(user, chat_id)})\nПричина: {reason}", disable_mentions=1)                
            await add_punishment(chat_id, user_id)

        if command in ['sunban', 'санбан', 'сунбан']:
            if await get_role(user_id, chat_id) < 3:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            # --- Проверка привязки сервера ---
            server_chats = await get_server_chats(chat_id)
            server_id = await get_current_server(chat_id)
            if not server_chats:
                await message.reply("Сначало укажите сервер, /server!", disable_mentions=1)
                return True

            user = int
            if message.reply_message:
                user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            for i in server_chats:
                try:
                    await unban(user, i)
                except:
                    pass

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) разблокировал(-а) в беседах сервера «{server_id}» @id{user} ({await get_user_name(user, chat_id)})")
            await chats_log(user_id=user_id, target_id=user, role=None,
                            log=f"разблокировал(-а) в беседах сервера @id{user} (пользователя)")            

# =============================================
        if command in ['inactivelist', 'inactive', 'ilist']:
            if await get_role(user_id, chat_id) < 2:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            users = await bot.api.messages.get_conversation_members(peer_id=message.peer_id,fields=["online_info", "online", "last_seen"])
            users = json.loads(users.json())
            unactive_users_day = []
            count_uad = 0
            unactive_users_moon = []
            count_uam = 0
            for i in users["profiles"]:
                try:
                    currency_time = time.time()
                    time_seen = i['last_seen']['time']
                    last_seen_device_list = {1: "📱", 2: "📱", 3: "📱", 4: "📱", 5: "📱", 6: "💻", 7: "💻"}
                    last_seen_device = last_seen_device_list.get(i['last_seen']['platform'])
                    if time_seen <= currency_time - 604800:
                        count_uam = count_uam + 1
                        if count_uam <= 30:
                            info = await bot.api.users.get(i['id'])
                            unactive_users_moon.append(
                                f"{count_uam}) @id{i['id']} ({info[0].first_name} {info[0].last_name}) -- {last_seen_device}")
                    elif time_seen <= currency_time - 86400:
                        count_uad = count_uad + 1
                        if count_uad <= 30:
                            info = await bot.api.users.get(i['id'])
                            unactive_users_day.append(
                                f"{count_uad}) @id{i['id']} ({info[0].first_name} {info[0].last_name}) -- {last_seen_device}")
                except:
                    pass
            uad = "\n".join(unactive_users_day)
            uam = "\n".join(unactive_users_moon)
            await message.replyLocalizedMessage('command_inactivelist', {
                        'day': uad,
                        'week': uam
                    })            
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) список неактивных пользователей в чате")            

        if command in ['mkick', 'мкик', 'masskick']:
            if await get_role(user_id, chat_id) < 7:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if len(arguments) <= 1:
                arguments = 'all'
                return True
            if len(arguments) >= 30:
                arguments = 'all'
                return True

            if arguments[1] in ['all', 'все']:
                if await get_role(user_id, chat_id) < 7:
                    await message.replyLocalizedMessage('not_preminisionss')
                    return True

                users = await bot.api.messages.get_conversation_members(peer_id=message.peer_id,
                                                                        fields=["online_info", "online"])
                users = json.loads(users.json())
                user_f = []
                gi = 0
                for i in users["profiles"]:
                    if not i['id'] == user_id and await get_role(i['id'], chat_id) <= 0:
                        await bot.api.messages.remove_chat_user(chat_id, int(i['id']))

                await message.answer(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) исключил(-а) пользователей без ролей", disable_mentions=1)
                await chats_log(user_id=user_id, target_id=None, role=None, log=f"исключил(-а) пользователей без ролей в чате")            
                return True


            do_users = []
            for i in range(len(arguments)):
                if i <= 0:
                    pass
                else:
                    do_users.append(arguments[i])
            users = []
            for i in do_users:
                idp = await getID(i)
                if idp:
                    users.append(idp)
            kick_users_list = []
            for i in users:
                if await equals_roles(user_id, i, chat_id) < 2:
                    await message.answer(f"У @id{i} уровень прав выше!", disable_mentions=1)
                else:
                    try:
                        await bot.api.messages.remove_chat_user(chat_id, i)
                        info = await bot.api.users.get(int(i))
                        kick_users_list.append(f"@id{i} ({info[0].first_name})")
                    except:
                        pass
            kick_users = ", ".join(kick_users_list)
            await message.replyLocalizedMessage('command_masskick')
            await add_punishment(chat_id, user_id)
            if await get_sliv(user_id, chat_id) and await get_role(user_id, chat_id) < 5:
                await roleG(user_id, chat_id, 0)
                await message.reply(
                    f"❗️ Уровень прав @id{user_id} (пользователя) был снят из-за подозрений в сливе беседы\n\n{await staff_zov(chat_id)}")

        if command in ['quiet', 'silence', 'тишина']:
            if await get_role(user_id, chat_id) < 3:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            silence = await quiet(chat_id)
            if silence:
            	await message.replyLocalizedMessage('command_quiet_on', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})'
                    })
            	
            else:
            	await message.replyLocalizedMessage('command_quiet_off', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})'
                    })

        if command in ['addsenmoder', 'senmoder', 'смодер']:
            if await get_role(user_id, chat_id) < 3:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            user = int
            if message.reply_message: user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.replyLocalizedMessage('set_role_preminisionss')
                return True

            await roleG(user, chat_id, 2)
            await message.replyLocalizedMessage('command_addsenmoder', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'target': f'@id{user} ({await get_user_name(user, chat_id)})'
                    })            
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"выдал(-а) права старшего модератора @id{user} (пользователю)")            
            await add_punishment(chat_id, user_id)
            if await get_sliv(user_id, chat_id) and await get_role(user_id, chat_id) < 5:
                await roleG(user_id, chat_id, 0)
                await message.reply(
                    f"❗️ Уровень прав @id{user_id} (пользователя) был снят из-за подозрений в сливе беседы\n\n{await staff_zov(chat_id)}")

        if command in ['rnickall', 'allrnick', 'arnick', 'mrnick']:
            if await get_role(user_id, chat_id) < 3:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == tchat:
                await message.replyLocalizedMessage('testers_chat')
                return True

            await rnickall(chat_id)
            await message.replyLocalizedMessage('command_rnickall', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})'
                    })            
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"очистил(-а) ники в беседе!")            

        if command in ['addadmin', 'admin', 'админ']:
            if await get_role(user_id, chat_id) < 4:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            user = int
            if message.reply_message: user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.replyLocalizedMessage('set_role_preminisionss')
                return True

            await roleG(user, chat_id, 3)
            await message.replyLocalizedMessage('command_addadmin', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'target': f'@id{user} ({await get_user_name(user, chat_id)})'
                    })            
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"выдал(-а) права администратора @id{user} (пользователю)")            
            await add_punishment(chat_id, user_id)
            if await get_sliv(user_id, chat_id) and await get_role(user_id, chat_id) < 5:
                await roleG(user_id, chat_id, 0)
                await message.reply(
                    f"❗️ Уровень прав @id{user_id} (пользователя) был снят из-за подозрений в сливе беседы\n\n{await staff_zov(chat_id)}")

        if command in ['demote']:
            if await get_role(user_id, chat_id) < 7:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            users = await bot.api.messages.get_conversation_members(peer_id=message.peer_id, fields=["online_info", "online"])
            users = json.loads(users.json())
            for i in users["profiles"]:
                if not i['id'] == user_id and await get_role(i['id'], chat_id) < 1:
                    try: await bot.api.messages.remove_chat_user(chat_id, i['id'])
                    except: pass

            await message.answer(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) исключил(-а) всех участников без ролей!", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"исключил(-а) пользователей без ролей в чате")            

        if command in ['filter']:
            if await get_role(user_id, chat_id) < 4:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if await get_filter(chat_id):
                await set_filter(chat_id, 0)
                await message.replyLocalizedMessage('command_filter_off', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})'
                    })            
                await chats_log(user_id=user_id, target_id=None, role=None, log=f"включил(-а) фильтр в чате")            
            else:
                await set_filter(chat_id, 1)
                await message.replyLocalizedMessage('command_filter_on', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})'
                    })            
                await chats_log(user_id=user_id, target_id=None, role=None, log=f"выключил(-а) фильтр в чате")            

        if command in ['antiflood', 'af']:
            if await get_role(user_id, chat_id) < 7:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if await get_antiflood(chat_id):
                await set_antiflood(chat_id, 0)
                await message.replyLocalizedMessage('command_antiflood_off', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})'
                    })            
                await chats_log(user_id=user_id, target_id=None, role=None, log=f"включил(-а) антифлуд в чате")            
            else:
                await set_antiflood(chat_id, 1)
                await message.replyLocalizedMessage('command_antiflood_on', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})'
                    })            
                await chats_log(user_id=user_id, target_id=None, role=None, log=f"выключил(-а) антифлуд в чате")            

        if command in ['welcome', 'welcometext', 'wtext']:
            if await get_role(user_id, chat_id) < 7:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if len(arguments) < 2:
                await message.replyLocalizedMessage('command_welcometext_params', {
                        'wtext': await get_welcome(chat_id)
                    })            
                return True

            text = await get_string(arguments, 1)
            await set_welcome(chat_id, text)
            await message.replyLocalizedMessage('command_welcometext', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})'
                    })            
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"установил(-а) новое приветствие в чате. Новое привтетствие: {text}")            

        if command in ['invite']:
            if await get_role(user_id, chat_id) < 7:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            result = await invite_kick(chat_id, True)
            if result: await message.replyLocalizedMessage('command_invite_on') is await chats_log(user_id=user_id, target_id=None, role=None, log=f"включил(-а) функцию приглашения модераторами в чате")                        
            else: await message.replyLocalizedMessage('command_invite_off') is await chats_log(user_id=user_id, target_id=None, role=None, log=f"выключил(-а) функцию приглашения модераторами в чате")                        

        if command in ['leave']:
            if await get_role(user_id, chat_id) < 7:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            result = await leave_kick(chat_id, True)
            if result: await message.replyLocalizedMessage('command_leave_on') is await chats_log(user_id=user_id, target_id=None, role=None, log=f"включил(-а) функцию исключения при выходе")                        
            else: await message.replyLocalizedMessage('command_leave_off') is await chats_log(user_id=user_id, target_id=None, role=None, log=f"выключил(-а) функцию исключения при выходе")                        

        if command in ['addsenadmin', 'addsenadm', 'senadm', 'senadmin', 'садмин']:
            if await get_role(user_id, chat_id) < 5:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            user = int
            if message.reply_message: user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.replyLocalizedMessage('set_role_preminisionss')
                return True

            await roleG(user, chat_id, 4)
            await message.replyLocalizedMessage('command_addsenadmin', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'target': f'@id{user} ({await get_user_name(user, chat_id)})'
                    })            
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"выдал(-а) права старшего администратора @id{user} (пользователю)")            
            
        if command in ['addzsa', 'зса']:
            if await get_role(user_id, chat_id) < 6:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            user = int
            if message.reply_message: user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.replyLocalizedMessage('set_role_preminisionss')
                return True

            await roleG(user, chat_id, 5)
            await message.replyLocalizedMessage('command_addzsa', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'target': f'@id{user} ({await get_user_name(user, chat_id)})'
                    })            
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"выдал(-а) права зам спец администратора @id{user} (пользователю)")            
            
        if command in ['addsa', 'са', 'spec', 'specadm']:
            if await get_role(user_id, chat_id) < 7:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            user = int
            if message.reply_message: user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.replyLocalizedMessage('set_role_preminisionss')
                return True

            await roleG(user, chat_id, 6)
            await message.replyLocalizedMessage('command_addsa', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'target': f'@id{user} ({await get_user_name(user, chat_id)})'
                    })            
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"выдал(-а) права спец администратора @id{user} (пользователю)")            

        if command in ['serverinfo', 'серверинфо']:
            if await get_role(user_id, chat_id) < 4:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            # Ищем сервер, к которому принадлежит текущий чат
            sql.execute("SELECT owner_id, server_number, table_name FROM servers_list")
            servers = sql.fetchall()

            found_server = None
            for owner, number, table in servers:
                try:
                    sql.execute(f"SELECT chat_id FROM {table} WHERE chat_id = ?", (chat_id,))
                    if sql.fetchone():
                        found_server = (owner, number, table)
                        break
                except:
                    continue

            if not found_server:
                await message.reply("Для начала укажите сервер, /server!", disable_mentions=1)
                return True

            owner_id, server_number, table_name = found_server
            sql.execute(f"SELECT chat_title FROM {table_name}")
            chats = sql.fetchall()

            chats_list = ""
            for i, (chat_title,) in enumerate(chats, start=1):
                chats_list += f"{i}. {chat_title}\n"

            await message.replyLocalizedMessage('command_serverinfo', {
                        'server': server_number,
                        'count_chats': len(chats),
                        'info': chats_list
                    })            
            return True
            
        if command in ['server', 'сервер']:
            if await get_role(user_id, chat_id) < 6:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if len(arguments) < 2:
                await message.replyLocalizedMessage('command_server_params')
                return True

            server_number = arguments[1]
            server = arguments[1]

            if not server_number.isdigit():
                await message.replyLocalizedMessage('command_server_number')
                return True

            table_name = f"server_{user_id}_{server_number}"

            # Если указали 0 — удаляем текущий чат из всех таблиц владельца
            if server_number == "0":
                sql.execute("SELECT table_name FROM servers_list WHERE owner_id = ?", (user_id,))
                tables = sql.fetchall()
                for t in tables:
                    table = t[0]
                    sql.execute(f"DELETE FROM {table} WHERE chat_id = ?", (chat_id,))
                database.commit()
                await message.replyLocalizedMessage('command_server_un')
                return True

            # Проверяем, есть ли таблица для данного сервера
            sql.execute("SELECT * FROM servers_list WHERE owner_id = ? AND server_number = ?", (user_id, server_number))
            exists_server = sql.fetchone()

            if not exists_server:
                # Создаём таблицу для сервера
                sql.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    chat_id INTEGER,
                    chat_title TEXT
                )
                """)
                sql.execute("INSERT INTO servers_list (owner_id, server_number, table_name) VALUES (?, ?, ?)",
                            (user_id, server_number, table_name))
                database.commit()

            # Проверяем, не добавлена ли беседа уже
            sql.execute(f"SELECT chat_id FROM {table_name} WHERE chat_id = ?", (chat_id,))
            if sql.fetchone():            	
                await message.replyLocalizedMessage('command_server_alyready', {
                        'server': server
                    })            
                return True

            # Получаем название чата
            try:
                chat_info = await bot.api.messages.get_conversations_by_id(peer_ids=message.peer_id)
                chat_title = chat_info.items[0].chat_settings.title if chat_info.items else "Без названия"
            except:
                chat_title = "Без названия"

            sql.execute(f"INSERT INTO {table_name} (chat_id, chat_title) VALUES (?, ?)", (chat_id, chat_title))
            database.commit()

            await message.replyLocalizedMessage('command_server', {
                        'server': server
                    })            
            return True            
            
        if command in ['setowner', 'владелец', 'владелецбеседы']:
            if await get_role(user_id, chat_id) < 9:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == tchat:
                await message.replyLocalizedMessage('testers_chat')
                return True

            user = int
            if message.reply_message: user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.replyLocalizedMessage('set_role_preminisionss')
                return True

            await set_onwer(user, chat_id)
            await roleG(user, chat_id, 7)
            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) выдал(-а) права владельца беседы @id{user} ({await get_user_name(user, chat_id)})", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"выдал(-а) права владельца беседы @id{user} (пользователю)")            
                        
        if command in ['addzamdirector', 'addzamd', 'аддзам', 'заместитель']:
            if await get_role(user_id, chat_id) < 9:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == tchat:
                await message.replyLocalizedMessage('testers_chat')
                return True

            user = int
            if message.reply_message: user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.replyLocalizedMessage('set_role_preminisionss')
                return True

            await globalrole(user, 2)
            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) выдал(-а) права заместитель директора @id{user} ({await get_user_name(user, chat_id)})", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"выдал(-а) права заместитель директора @id{user} (пользователю)")            

        if command in ['addgltester', 'gltester', 'аддглтестер', 'главныйтестер']:
            if await get_role(user_id, chat_id) < 12:
                await message.reply("Вы не являетесь тестировщиком бота!", disable_mentions=1)
                return True

            user = int
            if message.reply_message: user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.replyLocalizedMessage('set_role_preminisionss')
                return True

            await globalrole(user, 5)
            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) выдал(-а) права главного тестировщика @id{user} ({await get_user_name(user, chat_id)})", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"выдал(-а) права главного тестировщика @id{user} (пользователю)")                        
            
        if command in ['addzamtester', 'addzamt', 'аддзамтестер', 'заместительтестера']:
            if await get_role(user_id, chat_id) < 12:
                await message.reply("Вы не являетесь тестировщиком бота!", disable_mentions=1)
                return True

            user = int
            if message.reply_message: user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.replyLocalizedMessage('set_role_preminisionss')
                return True

            await globalrole(user, 3)
            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) выдал(-а) права заместителя главного тестировщика @id{user} ({await get_user_name(user, chat_id)})", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"выдал(-а) права заместителя тестировщика @id{user} (пользователю)")                        
            
        if command in ['addoszamdirector', 'addoszamd', 'аддосзам', 'озаместитель']:
            if await get_role(user_id, chat_id) < 10:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == tchat:
                await message.replyLocalizedMessage('testers_chat')
                return True

            user = int
            if message.reply_message: user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.replyLocalizedMessage('set_role_preminisionss')
                return True

            await globalrole(user, 4)
            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) выдал(-а) права основного заместителя директора @id{user} ({await get_user_name(user, chat_id)})", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"выдал(-а) права основного заместителя директора @id{user} (пользователю)")            
            
        if command in ['adddirector', 'director', 'адддиректор', 'директор']:
            if await get_role(user_id, chat_id) < 11:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == tchat:
                await message.replyLocalizedMessage('testers_chat')
                return True

            user = int
            if message.reply_message: user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.replyLocalizedMessage('set_role_preminisionss')
                return True

            await globalrole(user, 6)
            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) выдал(-а) права Директора бота @id{user} ({await get_user_name(user, chat_id)})", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"выдал(-а) права Директора бота @id{user} (пользователю)")

        if command in ['adddev', 'developer', 'аддразработчик', 'разработчик']:
            allowed_ids = [488828183,574393629]  

            if user_id not in allowed_ids:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == tchat:
                await message.replyLocalizedMessage('testers_chat')
                return True

            user = int
            if message.reply_message: user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.replyLocalizedMessage('set_role_preminisionss')
                return True

            await globalrole(user, 7)
            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) выдал(-а) права разработчика бота @id{user} ({await get_user_name(user, chat_id)})", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"выдал(-а) права разработчика бота @id{user} (пользователю)")    

        if command in ["case", "кейсы", "кейс"]:
            kb, case_text = await build_cases_menu(user_id)
            await message.reply(case_text, keyboard=kb)
            return True

        if command in ["открытькейс", "openmycase"]:
            cases = await get_user_cases(user_id)
            if not cases:
                await message.reply("📦 У вас нет неоткрытых кейсов.")
                return True
            if len(arguments) < 2 or not str(arguments[1]).isdigit():
                await message.reply("Укажите номер кейса из списка: /открытькейс [номер]")
                return True
            index = int(arguments[1])
            if index < 1 or index > len(cases):
                await message.reply("Кейс с таким номером не найден.")
                return True
            selected_case = cases[index - 1]
            reward, reward_text = await open_case(selected_case["case_type"], user_id)
            await remove_user_case(user_id, int(selected_case["id"]))
            bal = get_balance(user_id)
            if reward["type"] == "money":
                bal["wallet"] += int(reward["amount"])
            elif reward["type"] == "vip_days":
                now = datetime.now()
                current_vip = bal.get("vip_until")
                start_dt = now
                if current_vip:
                    try:
                        vip_dt = datetime.fromisoformat(current_vip)
                        if vip_dt > now:
                            start_dt = vip_dt
                    except Exception:
                        pass
                bal["vip_until"] = (start_dt + timedelta(days=int(reward["days"]))).isoformat()
            balances[str(user_id)] = bal
            save_data(BALANCES_FILE, balances)
            await log_economy(user_id=user_id, target_id=None, amount=None, log=f"открыл(-а) кейс «{selected_case['meta']['name']}» и получил {reward_text}")
            reward_hint = ""
            if reward["type"] == "business":
                reward_hint = "\nБизнес уже активирован. Откройте +бизнес."
            elif reward["type"] == "item":
                reward_hint = "\nПредмет уже добавлен в инвентарь."
            elif reward["type"] == "vip_days":
                reward_hint = "\nVIP автоматически добавлен к текущему сроку."
            await message.reply(
                f"Вы открыли {selected_case['meta']['name']}.\n"
                f"Награда: {reward_text}{reward_hint}"
            )
            return True

        if command in ["кейсысклад", "моикейсы", "cases"]:
            cases = await get_user_cases(user_id)
            if not cases:
                await message.reply("У вас нет неоткрытых кейсов.")
                return True
            lines = ["📦 Ваши неоткрытые кейсы:", ""]
            for idx, case in enumerate(cases, start=1):
                lines.append(f"{idx}. {case['meta']['name']} | ID: {case['id']}")
            lines.append("")
            lines.append("Открыть: /открытькейс [номер]")
            await message.reply("\n".join(lines))
            return True

        if command in ["business", "бизнес"]:
            await sync_user_business_income(user_id)
            biz_list = await get_user_businesses(user_id)
            if not biz_list:
                kb = Keyboard(inline=True)
                kb.add(Callback("🛒 Купить бизнес", {"command": "buybiz_menu", "owner_id": user_id}), color=KeyboardButtonColor.PRIMARY)
                await message.reply("🏢 У вас пока нет бизнесов.\n✨ Самое время открыть первый источник дохода.", keyboard=kb)
                return True
            kb = Keyboard(inline=True)
            kb.add(Callback("🏢 Открыть меню бизнесов", {"command": "biz_menu", "owner_id": user_id}), color=KeyboardButtonColor.PRIMARY).row()
            kb.add(Callback("🛒 Купить бизнес", {"command": "buybiz_menu", "owner_id": user_id}), color=KeyboardButtonColor.SECONDARY)
            total_branch_balance = sum(_business_daily_potential(b) for b in biz_list)
            total_products = sum(int(b.get("products", 0)) for b in biz_list)
            income_label = "Общий доход бизнеса" if len(biz_list) == 1 else "Общий доход бизнесов"
            lines = [
                "🏢 Управление бизнесами:",
                "",
                f"🏬 Всего филиалов: {len(biz_list)}",
                f"📦 Всего продуктов: {total_products}",
                f"💵 {income_label}: {format_number(total_branch_balance)}$",
                "",
                "✨ Откройте меню кнопкой ниже.",
            ]
            await message.reply("\n".join(lines), keyboard=kb)
            return True

        if command in ["inventory", "inv", "инв", "инвентарь", "инвент"]:
            items, kb, text = await _build_inventory_page(user_id, 1)
            if not items:
                await message.reply("🎒 Инвентарь пуст.\nПолучайте предметы из кейсов и наград.")
                return True
            await message.reply(text, keyboard=kb if kb.buttons else None)
            return True

        if command in ["применить", "useitem", "applyitem"]:
            if len(arguments) < 2 or not str(arguments[1]).isdigit():
                await message.reply("✨ Укажите ID предмета: /применить [ID предмета]")
                return True
            item_id = int(arguments[1])
            item = await get_item_by_id(user_id, item_id)
            if not item:
                await message.reply("Предмет не найден в инвентаре.")
                return True
            if _is_business_talisman(item):
                kb, _page, talisman_text = await _build_talisman_business_menu(user_id, item_id, 1)
                await message.reply(
                    talisman_text,
                    keyboard=kb if kb.buttons else None,
                    disable_mentions=1,
                )
                return True
            added_bonus = await apply_item_effect(user_id, item)
            if added_bonus <= 0:
                await message.reply("Этот предмет нельзя применить.")
                return True
            await remove_item(user_id, item_id)
            await log_economy(user_id=user_id, target_id=None, amount=None, log=f"использовал(-а) предмет «{item['item_name']}»")
            await message.reply(
                f"✨ Предмет «{item['item_name']}» применён.\n"
                f"📈 Ваш общий бонус к /приз теперь: +{added_bonus}%."
            )
            return True

        if command in ["распылить", "salvageitem", "dustitem"]:
            if len(arguments) < 2 or not str(arguments[1]).isdigit():
                await message.reply("♻️ Укажите ID предмета: /распылить [ID предмета]")
                return True
            item_id = int(arguments[1])
            item = await take_item_by_id(user_id, item_id)
            if not item:
                await message.reply("Предмет не найден в инвентаре.")
                return True
            bananas_reward = _item_banana_value(item)
            bal = get_balance(user_id)
            bal["bananas"] = bal.get("bananas", 0) + bananas_reward
            balances[str(user_id)] = bal
            save_data(BALANCES_FILE, balances)
            _drop_user_cache(user_id)
            await log_economy(user_id=user_id, target_id=None, amount=bananas_reward, log=f"распылил(-а) предмет «{item['item_name']}» и получил {bananas_reward} бананов")
            await message.reply(
                f"♻️ Распыление прошло успешно!\n\n"
                f"📦 Предмет: {item['item_name']}\n"
                f"🍌 Получено: {format_number(bananas_reward)} бананов\n"
                f"🍌 Теперь у вас: {format_number(int(bal.get('bananas', 0)))} бананов"
            )
            return True

        if command in ["аукцион", "аук", "auction"]:
            lots, kb, text = await _build_auction_page(chat_id, 1)
            if not lots:
                await message.reply("🏛 Аукцион пуст.\nВыставить лот: /выставитьаук [ID предмета] [ставка]")
                return True
            await message.reply(text, keyboard=kb if kb.buttons else None)
            return True

        if command in ["выставитьаук", "sellauction"]:
            await finalize_expired_auctions()
            if len(arguments) < 3 or not str(arguments[1]).isdigit() or not str(arguments[2]).isdigit():
                await message.reply("🏛 Использование: /выставитьаук [ID предмета] [начальная ставка]")
                return True
            item_id = int(arguments[1])
            start_bid = int(arguments[2])
            if start_bid <= 0:
                await message.reply("Начальная ставка должна быть больше 0.")
                return True
            item = await take_item_by_id(user_id, item_id)
            if not item:
                await message.reply("Предмет не найден в инвентаре.")
                return True
            created_at = datetime.now()
            ends_at = (created_at + timedelta(hours=3)).isoformat()
            async with aiosqlite.connect("database.db", timeout=30) as db:
                await _configure_async_db(db)
                await db.execute(
                    "INSERT INTO auction_items (seller_id, item_type, item_name, item_value, start_bid, current_bid, created_at, ends_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        user_id,
                        item["item_type"],
                        item["item_name"],
                        int(item["item_value"]),
                        start_bid,
                        start_bid,
                        created_at.isoformat(),
                        ends_at,
                    ),
                )
                await db.commit()
            await log_economy(user_id=user_id, target_id=None, amount=start_bid, log=f"выставил(-а) на аукцион предмет «{item['item_name']}» со стартовой ставкой {start_bid}$")
            await message.reply(
                f"🏛 Лот «{item['item_name']}» выставлен на аукцион.\n"
                f"💰 Начальная ставка: {format_number(start_bid)}$\n"
                f"⏳ Время: 3 часа"
            )
            return True

        if command in ["купаук", "buyauction"]:
            await finalize_expired_auctions()
            if len(arguments) < 3 or not str(arguments[1]).isdigit() or not str(arguments[2]).isdigit():
                await message.reply("💸 Использование: /купаук [номер лота] [ставка]")
                return True
            lot_id = int(arguments[1])
            bid_amount = int(arguments[2])
            async with aiosqlite.connect("database.db", timeout=30) as db:
                await _configure_async_db(db)
                db.row_factory = aiosqlite.Row
                cur = await db.execute(
                    "SELECT id, seller_id, item_name, current_bid, highest_bidder_id, created_at, ends_at FROM auction_items WHERE id = ?",
                    (lot_id,),
                )
                lot = await cur.fetchone()
            if not lot:
                await message.reply("Лот не найден.")
                return True
            lot = dict(lot)
            if int(lot["seller_id"]) == user_id:
                await message.reply("Нельзя выкупить свой же лот.")
                return True
            lot_ends_at = _resolve_auction_ends_at(lot)
            if lot_ends_at and lot_ends_at <= datetime.now():
                await finalize_expired_auctions()
                await message.reply("Этот лот уже завершён.")
                return True
            min_bid = int(lot["current_bid"]) + 1
            if bid_amount < min_bid:
                await message.reply(f"Ставка должна быть не меньше {format_number(min_bid)}$.")
                return True
            bal = get_balance(user_id)
            previous_highest_bidder_id = lot.get("highest_bidder_id")
            previous_bid = int(lot["current_bid"])
            required_amount = bid_amount
            if previous_highest_bidder_id and int(previous_highest_bidder_id) == user_id:
                required_amount = bid_amount - previous_bid
            if bal.get("wallet", 0) < required_amount:
                await message.reply("Недостаточно монет для ставки.")
                return True
            async with aiosqlite.connect("database.db", timeout=30) as db:
                await _configure_async_db(db)
                await db.execute(
                    "UPDATE auction_items SET current_bid = ?, highest_bidder_id = ? WHERE id = ?",
                    (bid_amount, user_id, lot_id),
                )
                await db.commit()
            bal["wallet"] -= required_amount
            _persist_user_balance(user_id, bal)
            if previous_highest_bidder_id and int(previous_highest_bidder_id) != user_id:
                prev_bal = get_balance(int(previous_highest_bidder_id))
                prev_bal["wallet"] = prev_bal.get("wallet", 0) + previous_bid
                _persist_user_balance(int(previous_highest_bidder_id), prev_bal)
            await message.reply(
                f"💸 Ставка принята.\n"
                f"Лот: {lot['item_name']}\n"
                f"Новая ставка: {format_number(bid_amount)}$"
            )
            await log_economy(user_id=user_id, target_id=int(lot["seller_id"]), amount=bid_amount, log=f"сделал(-а) ставку {bid_amount}$ на аукционе за предмет «{lot['item_name']}»")
            return True

        if command in ["снятьаук", "removeauction"]:
            await finalize_expired_auctions()
            if len(arguments) < 2 or not str(arguments[1]).isdigit():
                await message.reply("❌ Использование: /снятьаук [номер лота]")
                return True
            lot_id = int(arguments[1])
            async with aiosqlite.connect("database.db", timeout=30) as db:
                await _configure_async_db(db)
                db.row_factory = aiosqlite.Row
                cur = await db.execute(
                    "SELECT id, seller_id, item_type, item_name, item_value, highest_bidder_id FROM auction_items WHERE id = ?",
                    (lot_id,),
                )
                lot = await cur.fetchone()
                if not lot:
                    await message.reply("Лот не найден.")
                    return True
                lot = dict(lot)
                if int(lot["seller_id"]) != user_id:
                    await message.reply("Снять можно только свой лот.")
                    return True
                if lot.get("highest_bidder_id"):
                    await message.reply("Нельзя снять лот, на который уже сделали ставку.")
                    return True
                await db.execute(
                    "INSERT INTO inventory (user_id, item_type, item_name, item_value) VALUES (?, ?, ?, ?)",
                    (user_id, lot["item_type"], lot["item_name"], int(lot["item_value"])),
                )
                await db.execute("DELETE FROM auction_items WHERE id = ?", (lot_id,))
                await db.commit()
            await log_economy(user_id=user_id, target_id=None, amount=None, log=f"снял(-а) с аукциона предмет «{lot['item_name']}»")
            await message.reply(f"❌ Лот «{lot['item_name']}» снят с аукциона и возвращён в инвентарь.")
            return True

        if command in ["+улучшбиз", "улучшбиз"]:
            if len(arguments) < 2 or not str(arguments[1]).isdigit():
                await message.reply("Укажите ID филиала: +улучшбиз [id филиала]")
                return True
            business_id = int(arguments[1])
            biz = await get_business_by_id(user_id, business_id)
            if not biz:
                await message.reply("Филиал не найден.")
                return True
            success, text, cost = await upgrade_business(user_id, business_id)
            if not success:
                await message.reply(text)
                return True
            bal = get_balance(user_id)
            if bal["wallet"] < cost:
                current_level = int(biz["upgrade_level"])
                sql.execute("UPDATE businesses SET upgrade_level = ? WHERE id = ?", (current_level, business_id))
                database.commit()
                await message.reply(f"Недостаточно денег. Для улучшения нужно {format_number(cost)}$.")
                return True
            bal["wallet"] -= cost
            balances[str(user_id)] = bal
            save_data(BALANCES_FILE, balances)
            _drop_user_cache(user_id)
            await message.reply(f"{text}\nСписано: {format_number(cost)}$.")
            return True

        if command in ["+ппрод", "ппрод"]:
            if len(arguments) < 2 or not str(arguments[1]).isdigit():
                await message.reply("Укажите уровень заполнения склада: +ппрод [число до 100]\nНапример: +ппрод 100")
                return True
            amount = max(1, min(100, int(arguments[1])))
            businesses = await get_user_businesses(user_id)
            if not businesses:
                await message.reply("У вас нет бизнесов.")
                return True
            total_cost = 0
            refill_targets = []
            for biz in businesses:
                current_products = int(biz.get("products", 0))
                if current_products >= amount:
                    continue
                add_amount = min(amount - current_products, 100 - current_products)
                product_cost = _business_product_cost(biz["meta"])
                total_cost += add_amount * product_cost
                refill_targets.append((int(biz["id"]), add_amount))
            if not refill_targets:
                await message.reply(f"Все бизнесы уже заполнены минимум до {amount}/100.")
                return True
            bal = get_balance(user_id)
            if bal["bank"] < total_cost:
                await message.reply(
                    f"Недостаточно денег на банковском счете.\nНужно: {format_number(total_cost)}$"
                )
                return True
            filled = 0
            for business_id, add_amount in refill_targets:
                ok, _msg, _added = await refill_products(user_id, business_id, add_amount)
                if ok:
                    filled += 1
            bal["bank"] -= total_cost
            _persist_user_balance(user_id, bal)
            await message.reply(
                f"Склады пополнены до {amount}/100 в {filled} бизнес(е/ах).\n"
                f"С банковского счета списано: {format_number(total_cost)}$."
            )
            return True

        if command in ["собратьбиз", "collectbiz", "+собратьбиз"]:
            businesses = await get_user_businesses(user_id)
            if not businesses:
                await message.reply("У вас нет бизнесов.")
                return True
            await sync_user_business_income(user_id)
            changed, total_income = await withdraw_all_business_balance(user_id)
            if changed <= 0 or total_income <= 0:
                await message.reply("Сейчас нечего собирать. На счетах филиалов нет накопленного дохода.")
                return True
            bal = get_balance(user_id)
            bal["bank"] = int(bal.get("bank", 0)) + int(total_income)
            bal["business_income_today"] = int(bal.get("business_income_today", 0)) + int(total_income)
            _persist_user_balance(user_id, bal)
            await log_economy(user_id=user_id, target_id=None, amount=total_income, log=f"собрал(-а) доход с бизнесов в банк: {total_income}$")
            await message.reply(
                f"🏦 Доход с бизнесов собран прямо на банковский счёт.\n"
                f"🏢 Филиалов обработано: {changed}\n"
                f"💵 Зачислено в банк: {format_number(total_income)}$"
            )
            return True

        if command in ['sayall', 'gzov', 'news']:
            if await get_role(user_id, chat_id) < 10:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == tchat:
                await message.replyLocalizedMessage('testers_chat')
                return True

            reason = await get_string(arguments, 1)
            if not reason:
                await message.reply("Укажите текст рассылки!")
                return True

            peer_ids = await get_all_peerids()
            for i in peer_ids:
                try: await bot.api.messages.send(peer_id=i, message=reason, disable_mentions=1, random_id=0)
                except: pass
                
        if command in ['deltester', 'untester', 'снятьтестера']:
            if await get_role(user_id, chat_id) < 12:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            user = await get_string(arguments, 1)
            if not user:
                await message.reply("Укажите пользователя!")
                return True

            peer_ids = await get_all_peerids()
            await roleG(user, peer_ids, 0)
            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), снял(-а) роль тестеровщика во всех беседах у @id{user} ({await get_user_name(user, chat_id)})")               

        if command in ['szov', 'serverzov', 'сзов']:
            if await get_role(user_id, chat_id) < 4:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            reason = await get_string(arguments, 1)
            if not reason:
                await message.reply("Укажите причину вызова!", disable_mentions=1)
                return True

            # Проверяем, привязан ли чат к какому-то серверу
            server_chats = await get_server_chats(chat_id)
            if not server_chats:
                await message.reply("Сначало укажите сервер, /server!", disable_mentions=1)
                return True

            # Проходим по всем беседам сервера
            for i in server_chats:
                try:
                    users = await bot.api.messages.get_conversation_members(peer_id=2000000000 + i, fields=["online_info", "online"])
                    users = json.loads(users.json())
                    user_f = []
                    gi = 0
                    for b in users["profiles"]:
                        if not b['id'] == user_id:
                            gi += 1
                            if gi <= 100:
                                user_f.append(f"@id{b['id']} (🖤)")
                    zov_users = ''.join(user_f)

                    await bot.api.messages.send(
                        peer_id=2000000000 + i,
                        message=(
                            f"🔔 Вы были вызваны @id{user_id} (администратором) бесед\n\n"
                            f"{zov_users}\n\n"
                            f"❗ Причина вызова: {reason}"
                        ),
                        random_id=0
                    )
                except Exception as e:
                    print(f"[SZOV] Ошибка при отправке вызова в беседу {i}: {e}")

            await chats_log(user_id=user_id, target_id=None, role=None, log=f"вызвал(-а) всех пользователей в беседах сервера. Причина: {reason}")
            await message.reply(f"📣 Вызов успешно отправлен во все беседы сервера!\nПричина: {reason}", disable_mentions=1)
            return True
            
        if command in ['editowner', 'owner']:
            if await get_role(user_id, chat_id) < 7:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == tchat:
                await message.replyLocalizedMessage('testers_chat')
                return True

            user = int
            if len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if user == user_id: return await message.replyLocalizedMessage('command_editowner_user_user')

            if len(arguments) <= 2: return await message.replyLocalizedMessage('command_editowner_confirm')
            if not arguments_lower[2] == "confirm":
                return await message.replyLocalizedMessage('command_editowner_confirm')

            await set_onwer(user, chat_id)
            await roleG(user_id, chat_id, 6)

            await message.replyLocalizedMessage('command_editowner', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',
                        'target': f'@id{user} ({await get_user_name(user, chat_id)})'
                    })            
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"передал(-а) права владельца беседы @id{user} (пользователю)")            

        if command in ['srole', 'сроле']:
            if await get_role(user_id, chat_id) < 3:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == tchat:
                await message.reply(
                    "Данная беседа проводится в специализированном чате, который предназначен исключительно для тестировщиков бота.\n\n"
                    "В рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.",
                    disable_mentions=1
                )
                return True

            user = int
            arg = 2
            if message.reply_message:
                user = message.reply_message.from_id
                arg = 1
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            if await equals_roles(user_id, user, chat_id, None) < 2:
                return await message.reply("Вы не можете взаимодействовать с данным пользователем!")

            if len(arguments) < arg + 1:
                return await message.reply("Укажите аргументы!")

            if not arguments[arg].isdigit():
                return await message.reply("Укажите число!")

            level_num = int(arguments[arg])
            if level_num >= await get_role(user_id, chat_id):
                return await message.reply("Вы не можете выдать роль, которая выше вашей!")

            if level_num < 0:
                return await message.reply("Нельзя выдать такую роль!")

            # --- Преобразуем число в словарь ролей ---
            roles_dict = {
                1: "модератора",
                2: "старшего модератора",
                3: "администратора",
                4: "старшего администратора",
                5: "зам. спец администратора",
                6: "спец. администратора"
            }
            level_name = roles_dict.get(level_num, f"уровень {level_num}")
            server_id = await get_current_server(chat_id)
            
            server_chats = await get_server_chats(chat_id)
            if not server_chats:
                await message.reply("Сначало укажите сервер, /server!", disable_mentions=1)
                return True

            # --- Применяем роль ко всем чатам сервера ---
            for i in server_chats:
                try:
                    await roleG(user, i, level_num)
                except Exception as e:
                    print(f"[SROLE] Ошибка при выдаче роли в беседе {i}: {e}")

            await message.reply(
                f"@id{user_id} ({await get_user_name(user_id, chat_id)}) выдал(-а) права {level_name} "
                f"в беседах сервера «{server_id}» @id{user} ({await get_user_name(user, chat_id)})"
            )
            await chats_log(
                user_id=user_id,
                target_id=user,
                role=None,
                log=f"выдал(-а) права «{level_name}» в беседах сервера @id{user} (пользователю)"
            )
            return True
            


    else:
        if user_id < 1: return True
        if await check_chat(chat_id):
            if await get_mute(user_id, chat_id) and not await checkMute(chat_id, user_id):
                try: await bot.api.messages.delete(group_id=message.group_id, peer_id=message.peer_id, delete_for_all=True, cmids=message.conversation_message_id)
                except: pass
            elif await check_quit(chat_id) and (await get_role(user_id, chat_id) or 0) < 1:
                try: await bot.api.messages.delete(group_id=message.group_id, peer_id=message.peer_id, delete_for_all=True, cmids=message.conversation_message_id)
                except: pass
                print(await get_role(user_id, chat_id) < 1)
            else:
                if await get_filter(chat_id):
                    bws = await get_banwords(chat_id)
                    for i in bws:
                        if i in message.text.lower() and await get_role(user_id, chat_id) < 1:
                            await add_mute(user_id, chat_id, 'Бот', 'Написание запрещенных слов', 30)
                            await add_mutelog(chat_id, user_id, -123456789, "Написание запрещенных слов", 30, "выдан")
                            keyboard = (
                                Keyboard(inline=True)
                                .add(Callback("Снять мут", {"command": "unmute", "chatId": chat_id, "user": user_id}), color=KeyboardButtonColor.POSITIVE)
                            )
                            await message.reply(f"@id{user_id} (Пользователь) получил(-а) мут на 30 минут за написание запрещенного слова!", disable_mentions=1, keyboard=keyboard)
                            try: await bot.api.messages.delete(group_id=message.group_id, peer_id=message.peer_id,delete_for_all=True, cmids=message.conversation_message_id)
                            except: pass
                            return True

            await new_message(user_id, message.message_id, message.conversation_message_id, chat_id)
            if await get_spam(user_id, chat_id) and await get_role(user_id, chat_id) < 1:
                keyboard = (
                    Keyboard(inline=True)
                    .add(Callback("Снять мут", {"command": "unmute", "chatId": chat_id, "user": user_id}), color=KeyboardButtonColor.POSITIVE)
                )
                await message.reply(f"@id{user_id} (Пользователь) получил(-а) мут на 30 минут за спам!", disable_mentions=1, keyboard=keyboard)
                await add_mute(user_id, chat_id, 'Bot', 'Спам', 30)
                try:await bot.api.messages.delete(group_id=message.group_id, peer_id=message.peer_id,delete_for_all=True, cmids=message.conversation_message_id)
                except: pass

async def start_tasks():
    asyncio.create_task(check_and_clear_midnight())


async def restore_giveaway_tasks():
    for giveaway_id in list(giveaways.keys()):
        asyncio.create_task(finish_giveaway(giveaway_id))

if __name__ == "__main__":
    # Запускаем фоновую задачу очистки в отдельной задаче
    async def start_background_tasks():
        asyncio.create_task(check_and_clear_midnight())
    
    # Создаем event loop для vkbottle
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Запускаем фоновую задачу
    loop.create_task(check_and_clear_midnight())
    loop.create_task(restore_giveaway_tasks())
    loop.run_until_complete(init_economy_schema())
    
    print("\033[92mБот получен, запуск!\033[0m")
    
    # Запускаем бота через vkbottle
    bot.run_forever()
