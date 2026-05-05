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
from functools import lru_cache
import aiosqlite

from vkbottle.bot import Bot, Message, rules
from vkbottle import Keyboard, Callback, KeyboardButtonColor, Text, GroupEventType, GroupTypes, User
import sqlite3
import sys
import inspect
import logging

import pytz
from utils.db import init_economy_schema
from utils.case_system import CASE_DEFS, get_daily_remaining, open_case
from utils.business import (
    BUSINESSES_CATALOG,
    UPGRADE_BONUSES,
    UPGRADE_COSTS,
    add_business,
    collect_income,
    get_business_by_id,
    get_user_businesses,
    refill_products,
    upgrade_business,
)
from utils.inventory import (
    add_item,
    apply_item_effect,
    get_inventory,
    get_item_by_id,
    get_prize_bonus_percent,
    remove_item,
)

# Сколько на страницу
MAX_LOGS=20
MAX_LOGS=20

# настройка отсылки сообщений в ЛС
p_message = 'Бот не принимает личные сообщения. Обратитесь к @makswwy / @letsgggoo'

with open("config.json", "r") as js:
    open_file = json.load(js)

config = open_file

# конфиг.жс

bot = Bot(token=open_file['bot-token'])
bot.labeler.vbml_ignore_case = True
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
PRIZES_FILE = "prizes.json"
DONATES_FILE = "donates.json"
PROMO_FILE = "promo.json"
    
MUTELIST_PER_PAGE = 20

def has_mute_access_sync(user_id: int, chat_id: int) -> bool:
    """Синхронная проверка прав: staff(userId,chatId) in (admin,owner,sr.administrator)\n       или managers(userId).rang in (sa,zsa)"""
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
for f in [BALANCES_FILE, DUELS_FILE, PRIZES_FILE, DONATES_FILE, PROMO_FILE]:
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
prizes = load_data(PRIZES_FILE)
donates = load_data(DONATES_FILE)
promo = load_data(PROMO_FILE)

for uid in list(balances.keys()):
    if "bananas" not in balances[uid]:
        balances[uid]["bananas"] = 0
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
            "bananas": 0,
            "won": 0,
            "lost": 0,
            "won_total": 0,
            "lost_total": 0,
            "received_total": 0,
            "sent_total": 0,
            "vip_until": None,
            "donated": 0
        }
    if "bananas" not in balances[uid]:
        balances[uid]["bananas"] = 0
    return balances[uid]


_cache_balances = {}
_cache_businesses = {}
log = logging.getLogger("bot")


def _cached_user_balance(user_id: int):
    if user_id not in _cache_balances:
        _cache_balances[user_id] = get_balance(user_id)
    return _cache_balances[user_id]


def _drop_user_cache(user_id: int):
    _cache_balances.pop(user_id, None)
    _cache_businesses.pop(user_id, None)


def _daily_remaining_text(delta: Optional[timedelta]) -> str:
    if not delta:
        return "доступен"
    total_minutes = max(1, int(delta.total_seconds() // 60))
    h, m = divmod(total_minutes, 60)
    return f"{h}ч {m}м"


def _business_keys_ordered():
    return list(BUSINESSES_CATALOG.keys())


async def build_cases_menu(user_id: int):
    bal = _cached_user_balance(user_id)
    remaining = await get_daily_remaining(user_id)
    kb = Keyboard(inline=True)
    lines = [
        "Выберите кейс:",
        "",
    ]

    if remaining is None:
        kb.add(
            Callback("Ежедневный кейс", {"command": "open_case", "case_type": "daily", "owner_id": user_id}),
            color=KeyboardButtonColor.POSITIVE,
        ).row()
        lines.append("Ежедневный кейс - бесплатно")
    else:
        lines.append(f"Ежедневный кейс - снова доступен через {_daily_remaining_text(remaining)}")

    kb.add(
        Callback("Кейс бомжа", {"command": "open_case", "case_type": "homeless", "owner_id": user_id}),
        color=KeyboardButtonColor.PRIMARY,
    ).row()
    lines.append(f"Кейс бомжа - {format_number(CASE_DEFS['homeless']['money_cost'])}$")

    kb.add(
        Callback("Стандартный кейс", {"command": "open_case", "case_type": "standard", "owner_id": user_id}),
        color=KeyboardButtonColor.PRIMARY,
    ).row()
    lines.append(f"Стандартный кейс - {format_number(CASE_DEFS['standard']['money_cost'])}$")

    if bal.get("bananas", 0) >= CASE_DEFS["special"]["banana_cost"]:
        kb.add(
            Callback("Особый кейс", {"command": "open_case", "case_type": "special", "owner_id": user_id}),
            color=KeyboardButtonColor.POSITIVE,
        ).row()
        lines.append(f"Особый кейс - {CASE_DEFS['special']['banana_cost']} бананов")

    return kb, "\n".join(lines)

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

database = sqlite3.connect('database.db')
sql = database.cursor()
async def check_chat(chat_id=int):
    sql.execute(f"SELECT * FROM chats WHERE chat_id = {chat_id}")
    if sql.fetchone() == None: return False
    else: return True
    
sql.execute("""\nCREATE TABLE IF NOT EXISTS gbanlist (\n    user_id BIGINT NOT NULL,\n    moderator_id BIGINT NOT NULL,\n    reason_gban TEXT NOT NULL,\n    datetime_globalban TEXT NOT NULL\n)\n""")
database.commit()

# Таблица для списка глобальных связок
sql.execute("""\nCREATE TABLE IF NOT EXISTS gsync_list (\n    owner_id INTEGER,\n    table_name TEXT\n)\n""")
database.commit()

sql.execute("""\nCREATE TABLE IF NOT EXISTS promocodes (\n    code TEXT PRIMARY KEY,\n    type TEXT,\n    value INTEGER,\n    creator_id INTEGER,\n    uses_left INTEGER\n)\n""")
database.commit()

sql.execute("""\nCREATE TABLE IF NOT EXISTS promoused (\n    user_id INTEGER,\n    code TEXT\n)\n""")
database.commit()

sql.execute("""\nCREATE TABLE IF NOT EXISTS globalban (\n    user_id BIGINT NOT NULL,\n    moderator_id BIGINT NOT NULL,\n    reason_gban TEXT NOT NULL,\n    datetime_globalban TEXT NOT NULL\n)\n""")
database.commit()

sql.execute("""CREATE TABLE IF NOT EXISTS rules (\n    chat_id INTEGER PRIMARY KEY,\n    description TEXT\n)""")
database.commit()

sql.execute("""CREATE TABLE IF NOT EXISTS info (\n    chat_id INTEGER PRIMARY KEY,\n    description TEXT\n)""")
database.commit()

sql.execute("""CREATE TABLE IF NOT EXISTS antisliv (\n    chat_id INTEGER PRIMARY KEY,\n    mode INTEGER DEFAULT 0\n)""")
database.commit()

sql.execute("""\nCREATE TABLE IF NOT EXISTS blacklist (\n    user_id BIGINT NOT NULL,\n    moderator_id BIGINT NOT NULL,\n    reason_gban TEXT NOT NULL,\n    datetime_globalban TEXT NOT NULL\n)\n""")
database.commit()

sql.execute("""\nCREATE TABLE IF NOT EXISTS protection (\n    chat_id BIGINT NOT NULL PRIMARY KEY,\n    mode INT NOT NULL\n);\n""")

database.commit()

sql.execute("""\nCREATE TABLE IF NOT EXISTS mutesettings (\n    chat_id BIGINT NOT NULL PRIMARY KEY,\n    mode INT NOT NULL\n);\n""")

database.commit()

# Создание таблицы economy, если не существует
sql.execute("""\nCREATE TABLE IF NOT EXISTS economy (\n    user_id INTEGER,\n    target_id INTEGER,\n    amount INTEGER,\n    log TEXT\n)\n""")
database.commit()

# Создание таблицы logchats, если не существует
sql.execute("""\nCREATE TABLE IF NOT EXISTS logchats (\n    user_id INTEGER,\n    target_id INTEGER,\n    role INTEGER,\n    log TEXT\n)\n""")
database.commit()

# ======= сообщения за седня ==================
sql.execute("""\nCREATE TABLE IF NOT EXISTS messages_today (\n    user_id INTEGER,\n    chat_id INTEGER\n)\n""")
database.commit()

sql.execute("""\nCREATE TABLE IF NOT EXISTS banschats (\n    chat_id INTEGER PRIMARY KEY\n)\n""")
database.commit()

sql.execute("""\nCREATE TABLE IF NOT EXISTS bugsusers (\n    user_id INTEGER,\n    bug TEXT,\n    datetime TEXT,\n    bug_counts_user INTEGER\n)\n""")
database.commit()

# Таблица с регистрацией серверов
sql.execute("""\nCREATE TABLE IF NOT EXISTS servers_list (\n    owner_id INTEGER,\n    server_number TEXT,\n    table_name TEXT\n)\n""")
database.commit()

sql.execute("""\nCREATE TABLE IF NOT EXISTS server_links(\n    server_id INTEGER,\n    chat_id INTEGER,\n    chat_title TEXT\n)\n""")
database.commit()

sql.execute("""\nCREATE TABLE IF NOT EXISTS gamesettings (\n    chat_id BIGINT NOT NULL PRIMARY KEY,\n    mode INT NOT NULL\n);\n""")

database.commit()

sql.execute("""\nCREATE TABLE IF NOT EXISTS photosettings (\n    chat_id BIGINT NOT NULL PRIMARY KEY,\n    mode INT NOT NULL\n);\n""")

database.commit()

try:
    # Проверяем, есть ли старая таблица с неправильными колонками
    sql.execute("PRAGMA table_info(ban_words)")
    columns = [col[1] for col in sql.fetchall()]

    # Если нужных колонок нет — пересоздаём таблицу
    if "word" not in columns or "creator_id" not in columns or "time" not in columns:
        print("[INIT] Пересоздание таблицы ban_words...")
        sql.execute("DROP TABLE IF EXISTS ban_words")
        sql.execute("""\n        CREATE TABLE IF NOT EXISTS ban_words (\n            word TEXT NOT NULL,\n            creator_id INTEGER NOT NULL,\n            time TEXT NOT NULL\n        )\n        """)
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
      
async def get_role(user_id = int, chat_id = int):
    sql.execute(f"SELECT level FROM global_managers WHERE user_id = {user_id}")
    fetch = sql.fetchone()
    try:
        if fetch[0] == 2: return 9 # ЗР
        if fetch[0] == 3: return 10 # ЗГТ
        if fetch[0] == 4: return 11 # ОЗР
        if fetch[0] == 5: return 12 # ГТ      
        if fetch[0] == 6: return 13 # СР
        if fetch[0] == 7: return 14 # РБ
    except:
        sql.execute(f"SELECT owner_id FROM chats WHERE chat_id = {chat_id}")
        if sql.fetchall()[0][0] == user_id: return 7
        sql.execute(f"SELECT level FROM permissions_{chat_id} WHERE user_id = {user_id}")
        fetch = sql.fetchone()
        if fetch == None: return 0
        else: return fetch[0]

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
    sql.execute(f"SELECT user_id FROM nicks_{chat_id} WHERE nick = '{nick}'")
    fetch = sql.fetchone()
    if fetch == None: return False
    else: return fetch[0]

async def get_nick(user_id=int, chat_id=int):
    sql.execute(f"SELECT nick FROM nicks_{chat_id} WHERE user_id = {user_id}")
    fetch = sql.fetchone()
    if fetch == None: return False
    else: return fetch[0]

async def log_economy(user_id=None, target_id=None, amount=None, log=None):
    try:
        sql.execute(
            "INSERT INTO economy (user_id, target_id, amount, log) VALUES (?, ?, ?, ?)",
            (user_id, target_id, amount, log)
        )
        database.commit()
        print(f"[ECONOMY LOG] {user_id} -> {target_id} | {amount} | {log}")
    except Exception as e:
        print(f"[ECONOMY LOG ERROR] {e}")       
        
async def chats_log(user_id=None, target_id=None, role=None, log=None):
    try:
        sql.execute(
            "INSERT INTO logchats (user_id, target_id, role, log) VALUES (?, ?, ?, ?)",
            (user_id, target_id, role, log)
        )
        database.commit()
        print(f"[CHATS LOG] {user_id} -> {target_id} | {role} | {log}")
    except Exception as e:
        print(f"[CHATS LOG ERROR] {e}")       
        
async def add_message_today(user_id=None, chat_id=None):
    try:
        sql.execute(
            "INSERT INTO messages_today (user_id, chat_id) VALUES (?, ?)",
            (user_id, chat_id)
        )
        database.commit()
        return
    except Exception as e:
        print(f"[Ошибка при обработке сообщения] {e}")               

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
            if level == 1: moders.append(f'@id{user_id} ({await get_user_name(user_id, chat_id)})')
            elif level == 2: stmoders.append(f'@id{user_id} ({await get_user_name(user_id, chat_id)})')
            elif level == 3: admins.append(f'@id{user_id} ({await get_user_name(user_id, chat_id)})')
            elif level == 4: stadmins.append(f'@id{user_id} ({await get_user_name(user_id, chat_id)})')
            elif level == 5: zamspecadm.append(f'@id{user_id} ({await get_user_name(user_id, chat_id)})')
            elif level == 6: specadm.append(f'@id{user_id} ({await get_user_name(user_id, chat_id)})')
            elif level == 12: testers.append(f'@id{user_id} ({await get_user_name(user_id, chat_id)})')

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
        if level == 2: zamruk.append(f'@id{user_id} ({await get_user_name(user_id, None)})')
        elif level == 4: oszamruk.append(f'@id{user_id} ({await get_user_name(user_id, None)})')
        elif level == 6: ruk.append(f'@id{user_id} ({await get_user_name(user_id, None)})')
        elif level == 7: dev.append(f'@id{user_id} ({await get_user_name(user_id, None)})')
        elif level == 3: zamglt.append(f'@id{user_id} ({await get_user_name(user_id, None)})')
        elif level == 5: glt.append(f'@id{user_id} ({await get_user_name(user_id, None)})')

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
    """\n    Выдаёт или обновляет глобальную роль пользователя в таблице global_managers.\n\n    level:\n        0 - удаление роли\n        8 - zamruk\n        9 - oszamruk\n        10 - ruk\n        11 - dev\n    """
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
    for row in fetch:
        messages.append(f"None")

    return messages    

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
    if list_messages[0] - list_messages[2] < timedelta(seconds=2):
        return True
    return False

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
    """\n    Определяет, к какому серверу принадлежит чат, и возвращает список всех chat_id из этого сервера.\n    """
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
    """\n    Возвращает номер сервера, к которому привязан данный chat_id, или None, если не привязан.\n    """
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

def clear_table_daily():
    try:
        sql.execute("DELETE FROM messages_today")
        database.commit()
        print(f"Таблица messages_today очищена в {datetime.now()}")
    except Exception as e:
        print(f"Ошибка при очистке таблицы: {e}")

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

    # Проверка: если пользователь пытается применить команду на участника с более высоким рангом
    if sender_role < 7 and sender_role < target_role:
        await roleG(user_id_sender, chat_id, 0)
        await message.reply(
            f"❗️ Уровень прав @id{user_id_sender} (пользователя) был снят "
            f"из-за попытки использования команды на участника с более высоким рангом!"
        )
        return 0

    # Если всё нормально — возвращаем стандартные значения
    if sender_role > target_role:
        return 2
    elif sender_role == target_role:
        return 1
    else:
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
                    .add(Callback("Снять бан", payload=""), color=KeyboardButtonColor.POSITIVE)
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
                .add(Callback("Снять бан", payload=""), color=KeyboardButtonColor.POSITIVE)
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

    # Лог для каждой кнопки
    log_cmd = payload.get("log") or "нет лога"
    print(f"{user_id} использовал кнопку {command}. ВК выдало: {log_cmd}")
    if command == "open_case":
        case_type = str(payload.get("case_type", ""))
        if case_type not in CASE_DEFS:
            return True
        try:
            owner_id = int(payload.get("owner_id", 0) or 0)
            if owner_id and owner_id != user_id:
                await bot.api.messages.send_message_event_answer(
                    event_id=message.object.event_id,
                    peer_id=message.object.peer_id,
                    user_id=message.object.user_id,
                    event_data=json.dumps({"type": "show_snackbar", "text": "Это меню доступно только тому, кто вызвал команду"})
                )
                return True
            bal = _cached_user_balance(user_id)
            case_def = CASE_DEFS[case_type]
            if case_def["daily"]:
                remaining = await get_daily_remaining(user_id)
                if remaining:
                    await bot.api.messages.send_message_event_answer(
                        event_id=message.object.event_id,
                        peer_id=message.object.peer_id,
                        user_id=message.object.user_id,
                        event_data=json.dumps({"type": "show_snackbar", "text": f"Ежедневный кейс через {_daily_remaining_text(remaining)}"})
                    )
                    return True
            if case_def["money_cost"] > bal.get("wallet", 0):
                await bot.api.messages.send_message_event_answer(
                    event_id=message.object.event_id,
                    peer_id=message.object.peer_id,
                    user_id=message.object.user_id,
                    event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно валюты"})
                )
                return True
            if case_def["banana_cost"] > bal.get("bananas", 0):
                await bot.api.messages.send_message_event_answer(
                    event_id=message.object.event_id,
                    peer_id=message.object.peer_id,
                    user_id=message.object.user_id,
                    event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно бананов"})
                )
                return True

            if case_def["money_cost"]:
                bal["wallet"] -= case_def["money_cost"]
            if case_def["banana_cost"]:
                bal["bananas"] = max(0, bal.get("bananas", 0) - case_def["banana_cost"])

            reward, reward_text = await open_case(case_type, user_id)
            if reward["type"] == "money":
                bal["wallet"] += int(reward["amount"])
            elif reward["type"] == "vip_days":
                now = datetime.now()
                current_vip = bal.get("vip_until")
                start = now
                if current_vip:
                    try:
                        vip_dt = datetime.fromisoformat(current_vip)
                        if vip_dt > now:
                            start = vip_dt
                    except Exception:
                        pass
                bal["vip_until"] = (start + timedelta(days=int(reward["days"]))).isoformat()

            balances[str(user_id)] = bal
            save_data(BALANCES_FILE, balances)
            _drop_user_cache(user_id)
            await bot.api.messages.send(peer_id=message.object.peer_id, random_id=0, message=f"?? ????????: {reward_text}")
            log.info("Пользователь %s открыл %s и получил %s", user_id, case_def["name"], reward_text)
        except Exception as e:
            log.exception("Ошибка открытия кейса: %s", e)
        return True

    if command == "biz_show_branches":
        business_key = str(payload.get("business_key", ""))
        if not business_key:
            return True
        businesses = await get_user_businesses(user_id)
        branches = [b for b in businesses if b["business_key"] == business_key]
        if not branches:
            return True
        kb = Keyboard(inline=True)
        for branch in branches:
            kb.add(
                Callback(f'?????? #{branch["branch_no"]}', {"command": "biz_open", "business_id": branch["id"]}),
                color=KeyboardButtonColor.PRIMARY
            ).row()
        title = BUSINESSES_CATALOG.get(business_key, {"name": business_key})["name"]
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            random_id=0,
            keyboard=kb,
            message=f'??????: {title}\n???????? ??????:',
        )
        return True

    if command == "biz_open":
        business_id = int(payload.get("business_id", 0))
        biz = await get_business_by_id(user_id, business_id)
        if not biz:
            return True
        lvl = int(biz["upgrade_level"])
        upgrade_bonus = int(UPGRADE_BONUSES.get(lvl, 0) * 100)
        talisman_text = "Активирован (+500%)" if int(biz["talisman_active"]) else "Нет"
        keyboard = (
            Keyboard(inline=True)
            .add(Callback("Улучшить филиал", {"command": "biz_upgrade", "business_id": business_id}), color=KeyboardButtonColor.PRIMARY)
            .row()
            .add(Callback("Пополнить продукты", {"command": "biz_refill_prompt", "business_id": business_id}), color=KeyboardButtonColor.SECONDARY)
            .add(Callback("Собрать доход", {"command": "biz_collect", "business_id": business_id}), color=KeyboardButtonColor.POSITIVE)
        )
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            random_id=0,
            keyboard=keyboard,
            message=(
                f'🏢 Филиал вашего бизнеса #{biz["branch_no"]} [{biz["meta"]["name"]}]\n'
                f'💰 Баланс филиала: {format_number(int(biz["branch_balance"]))}\n'
                f'📦 Продукты: {int(biz["products"])}/100\n'
                f'🔧 Уровень улучшения: {lvl} (+{upgrade_bonus}%)\n'
                f"🪙 Талисман: {talisman_text}"
            ),
        )
        return True

    if command == "biz_upgrade":
        business_id = int(payload.get("business_id", 0))
        ok, msg_text, cost = await upgrade_business(user_id, business_id)
        if not ok:
            await bot.api.messages.send(peer_id=message.object.peer_id, random_id=0, message=msg_text)
            return True
        bal = _cached_user_balance(user_id)
        if bal.get("wallet", 0) < cost:
            await bot.api.messages.send(peer_id=message.object.peer_id, random_id=0, message=f"Недостаточно средств. Нужно {format_number(cost)}$")
            return True
        bal["wallet"] -= cost
        balances[str(user_id)] = bal
        save_data(BALANCES_FILE, balances)
        _drop_user_cache(user_id)
        await bot.api.messages.send(peer_id=message.object.peer_id, random_id=0, message=f"{msg_text} Списано {format_number(cost)}$.")
        return True

    if command == "biz_collect":
        business_id = int(payload.get("business_id", 0))
        ok, msg_text, amount = await collect_income(user_id, business_id)
        if not ok:
            await bot.api.messages.send(peer_id=message.object.peer_id, random_id=0, message=msg_text)
            return True
        bal = _cached_user_balance(user_id)
        bal["wallet"] += amount
        balances[str(user_id)] = bal
        save_data(BALANCES_FILE, balances)
        _drop_user_cache(user_id)
        await bot.api.messages.send(peer_id=message.object.peer_id, random_id=0, message=f"Доход собран: {format_number(amount)}$")
        return True

    if command == "biz_refill_prompt":
        business_id = int(payload.get("business_id", 0))
        kb = (
            Keyboard(inline=True)
            .add(Callback("+10", {"command": "biz_refill", "business_id": business_id, "amount": 10}), color=KeyboardButtonColor.PRIMARY)
            .add(Callback("+25", {"command": "biz_refill", "business_id": business_id, "amount": 25}), color=KeyboardButtonColor.PRIMARY)
            .add(Callback("+50", {"command": "biz_refill", "business_id": business_id, "amount": 50}), color=KeyboardButtonColor.PRIMARY)
        )
        await bot.api.messages.send(peer_id=message.object.peer_id, random_id=0, keyboard=kb, message="Выберите, сколько продуктов пополнить.")
        return True

    if command == "biz_refill":
        business_id = int(payload.get("business_id", 0))
        amount = int(payload.get("amount", 10))
        ok, msg_text, filled = await refill_products(user_id, business_id, amount)
        if not ok:
            await bot.api.messages.send(peer_id=message.object.peer_id, random_id=0, message=msg_text)
            return True
        cost = filled * 1000
        bal = _cached_user_balance(user_id)
        if bal.get("wallet", 0) < cost:
            await bot.api.messages.send(peer_id=message.object.peer_id, random_id=0, message=f"Недостаточно средств. Нужно {format_number(cost)}$")
            return True
        bal["wallet"] -= cost
        balances[str(user_id)] = bal
        save_data(BALANCES_FILE, balances)
        _drop_user_cache(user_id)
        await bot.api.messages.send(peer_id=message.object.peer_id, random_id=0, message=f"{msg_text} Списано {format_number(cost)}$.")
        return True

    if command == "inv_use_prompt":
        item_id = int(payload.get("item_id", 0))
        item = await get_item_by_id(user_id, item_id)
        if not item:
            return True
        kb = (
            Keyboard(inline=True)
            .add(Callback("Да, точно", {"command": "inv_use_confirm", "item_id": item_id}), color=KeyboardButtonColor.POSITIVE)
            .add(Callback("Нет, вернуться", {"command": "inv_back"}), color=KeyboardButtonColor.NEGATIVE)
        )
        await bot.api.messages.send(peer_id=message.object.peer_id, random_id=0, keyboard=kb, message=f'Вы точно хотите использовать:\n"{item["item_name"]}"?')
        return True

    if command == "inv_use_confirm":
        item_id = int(payload.get("item_id", 0))
        item = await get_item_by_id(user_id, item_id)
        if not item:
            return True
        if item["item_type"] == "business_talisman":
            businesses = await get_user_businesses(user_id)
            if businesses:
                async with aiosqlite.connect("database.db") as db:
                    await db.execute("UPDATE businesses SET talisman_active = 1 WHERE user_id = ?", (user_id,))
                    await db.commit()
        new_bonus = await apply_item_effect(user_id, item)
        await remove_item(user_id, item_id)
        await bot.api.messages.send(peer_id=message.object.peer_id, random_id=0, message=f"Предмет применен. Текущий бонус к /приз: +{new_bonus}%")
        return True

    if command == "inv_back":
        items = await get_inventory(user_id)
        if not items:
            await bot.api.messages.send(peer_id=message.object.peer_id, random_id=0, message="Инвентарь пуст.")
            return True
        lines = ["🎒 Инвентарь пользователя:\n"]
        kb = Keyboard(inline=True)
        idx = 1
        for item in items:
            lines.append(f"{idx}. {item['item_name']}")
            kb.add(Callback(f"Использовать {idx}", {"command": "inv_use_prompt", "item_id": item["id"]}), color=KeyboardButtonColor.PRIMARY).row()
            idx += 1
        await bot.api.messages.send(peer_id=message.object.peer_id, random_id=0, keyboard=kb, message="\n".join(lines))
        return True

    if command == "buy_business":
        key = str(payload.get("business_key", ""))
        if key not in BUSINESSES_CATALOG:
            return True
        info = BUSINESSES_CATALOG[key]
        bal = _cached_user_balance(user_id)
        if bal.get("wallet", 0) < int(info["price"]):
            await bot.api.messages.send(peer_id=message.object.peer_id, random_id=0, message="Недостаточно средств для покупки.")
            return True
        bal["wallet"] -= int(info["price"])
        balances[str(user_id)] = bal
        save_data(BALANCES_FILE, balances)
        _drop_user_cache(user_id)
        branch_no = await add_business(user_id, key)
        await bot.api.messages.send(peer_id=message.object.peer_id, random_id=0, message=f'Вы купили: {info["name"]} (филиал #{branch_no})')
        return True

    if command == "buybiz_menu":
        kb = Keyboard(inline=True)
        for key, info in BUSINESSES_CATALOG.items():
            kb.add(
                Callback(f'{info["name"]} — {format_number(int(info["price"]))}', {"command": "buy_business", "business_key": key}),
                color=KeyboardButtonColor.PRIMARY
            ).row()
        await bot.api.messages.send(peer_id=message.object.peer_id, random_id=0, keyboard=kb, message="🛒 Выберите бизнес для покупки:")
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
        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
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
        if await get_role(user_id, chat_id) < 13:
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
        if await get_role(user_id, chat_id) < 13:
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

        if await get_role(user_id, chat_id) <= await get_role(user, chat_id):
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
        if await get_role(user_id, chat_id) < 13:
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
        if await get_role(user_id, chat_id) < 13:
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
            print("[join_duel] Результат отправлен")

            duels.pop(peer, None)
            save_data(DUELS_FILE, duels)
            print(f"[join_duel] Дуэль {peer} удалена из списка")
            return True

        except Exception as e:
            print(f"[join_duel] Общая ошибка: {e}")
            return True
                           
    if command == "getban":
        target_user = payload.get("getban")
        if not target_user:
            return True

        # Проверяем роль того, кто нажал кнопку
        role = await get_role(user_id, chat_id)
        if role < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({
                    "type": "show_snackbar",
                    "text": "Недостаточно прав для просмотра информации о блокировках!"
                })
            )
            return True

        # Удаляем старое сообщение
        try:
            await bot.api.messages.delete(
                group_id=message.group_id,
                peer_id=message.object.peer_id,
                cmids=message.object.conversation_message_id,
                delete_for_all=True
            )
        except:
            pass

        # Отправляем /getban
        await on_chat_message(
            Message(
                text=f"/getban {target_user}",
                from_id=message.object.user_id,
                peer_id=message.object.peer_id,
                chat_id=message.object.peer_id - 2000000000,
                group_id=message.group_id,
                object=message.object,
                random_id=0
            )
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
        if await get_role(user_id, chat_id) < 9:
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

        if await get_role(user_id, chat_id) < 13:
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
        if await get_role(user_id, chat_id) < 9:
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
        if await get_role(user_id, chat_id) < 9:
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
        if await get_role(user_id, chat_id) < 9:
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
        if await get_role(user_id, chat_id) < 9:
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
        if await get_role(user_id, chat_id) < 9:
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
        if await get_role(user_id, chat_id) < 9:
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

        if await get_role(user_id, chat_id) < 13:
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
                '/addmoder -- moder',
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
                '/addsenmoder — senmoder',
                '/rnickall -- allrnick, arnick, mrnick',
                '/sremovenick -- srnick',
                '/szov -- serverzov, сзов',
                '/srole -- none',
                '/ssetnick -- ssnick, ссник'
            ],
            4: [
                '\nКоманды старших администраторов:',
                '/addadmin -- admin',
                '/serverinfo -- серверинфо',
                '/filter -- none',
                '/sremoverole -- srrole',
                '/bug -- баг',
                '/report -- реп, rep, жалоба'
            ],
            5: [
                '\nКоманды зам. спец. администраторов:',
                '/addsenadmin -- senadm, addsenadm, senadmin',
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
        await message.reply("Владелец беседы, не член уже BLACK MANAGER! Я не буду здесь работать.")
        return True

    # --- Проверка, зарегистрирован ли чат ---
    is_registered = await check_chat(chat_id)
    await add_message_today(user_id=user_id, chat_id=chat_id)

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
                    admin = "blackrussiamanagerbot"
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
        sql.execute("SELECT user_id, moderator_id, reason_gban FROM blacklist")
        blacklisted = sql.fetchall()

        if any(user_id == b[0] for b in blacklisted):
            users = ""
            i = 1
            for user_ban in blacklisted:
                user_ban_id, moderator, reason = user_ban
                users += f"\n{i}. @id{user_ban_id} ({await get_user_name(user_ban_id, chat_id)}) | " \
                         f"@id{moderator} (Модератор) | Причина: {reason}\n"
                i += 1

            chat_info = await bot.api.messages.get_conversations_by_id(peer_ids=message.peer_id)
            chat_title = chat_info.items[0].chat_settings.title if chat_info.items else "Неизвестная беседа"

            keyboard = (
                Keyboard(inline=True)
                .add(Callback("Исключить всех заблокированных", {"command": "kick_blacklisted", "chatId": chat_id}),
                     color=KeyboardButtonColor.NEGATIVE)
            )

            await message.reply(
                f"В чате «{chat_title}» находятся заблокированные пользователи.\n\n"
                f"❗ | Список всех пользователей в черном списке бота:\n{users}\n\n"
                f"Рекомендуем исключить пользователей из беседы, так как они нарушили правила использования бота.",
                disable_mentions=1,
                keyboard=keyboard
            )
            return True

    # --- Теперь обрабатываем команды (команды доступны всегда) ---
    try:
        command_identifier = arguments[0].strip()[0]
        command = arguments_lower[0][1:]
    except:
        command_identifier = " "
        command = " "

    if command_identifier in bot_identifiers:
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

                keyboard = (
                    Keyboard(inline=True)
                    .add(Callback("Снять бан", {}), color=KeyboardButtonColor.POSITIVE)
                )

                await message.reply(
                    f"@id{user_id} ({full_name}) заблокирован(-а) в беседах игроков!\n\n"
                    f"Информация о блокировке:\n@id{moderator_id} (Модератор) | {reason_gban} | {datetime_globalban}",
                    disable_mentions=1,
                    keyboard=keyboard
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

                keyboard = (
                    Keyboard(inline=True)
                    .add(Callback("Снять бан", {}), color=KeyboardButtonColor.POSITIVE)
                )

                await message.reply(
                    f"@id{user_id} ({full_name}) заблокирован(-а) во всех беседах!\n\n"
                    f"Информация о блокировке:\n@id{moderator_id} (Модератор) | {reason_gban} | {datetime_globalban}",
                    disable_mentions=1,
                    keyboard=keyboard
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

        if command in ["ping", "пинг"]:
            started = time.time()
            latency_ms = int((time.time() - started) * 1000)
            await message.reply(f"Пинг: {latency_ms} ms")
            return True

        if command in ["case", "?????", "????"]:
            kb, case_text = await build_cases_menu(user_id)
            await message.reply(case_text, keyboard=kb)
            return True

        if command in ["business", "??????"]:
            biz_list = await get_user_businesses(user_id)
            if not biz_list:
                kb = Keyboard(inline=True).add(Callback("?????? ??????", {"command": "buybiz_menu"}), color=KeyboardButtonColor.PRIMARY)
                await message.reply("? ??? ??? ????????.\n???????? ???? ?? ????? ??? ?????? ???????? /??????.", keyboard=kb)
                return True

            grouped = {}
            for b in biz_list:
                grouped.setdefault(b["business_key"], []).append(b)

            kb = Keyboard(inline=True)
            for key, branches in grouped.items():
                title = BUSINESSES_CATALOG.get(key, {"name": key})["name"]
                label = f"{title} x{len(branches)}" if len(branches) > 1 else title
                kb.add(Callback(label, {"command": "biz_show_branches", "business_key": key}), color=KeyboardButtonColor.PRIMARY).row()

            await message.reply("?? ???? ??????? (???????, ????? ??????? ???????):", keyboard=kb)
            return True

        if command in ["??????", "buybiz"]:
            keys = _business_keys_ordered()
            if len(arguments) >= 2 and str(arguments[1]).isdigit():
                business_no = int(arguments[1])
                if business_no < 1 or business_no > len(keys):
                    await message.reply("???????? ????? ???????.")
                    return True

                key = keys[business_no - 1]
                info = BUSINESSES_CATALOG[key]
                balances = load_data(BALANCES_FILE)
                bal = balances.get(str(user_id), get_balance(user_id))
                if bal.get("wallet", 0) < int(info["price"]):
                    await message.reply("???????????? ??????? ??? ??????? ???????.")
                    return True

                bal["wallet"] -= int(info["price"])
                balances[str(user_id)] = bal
                save_data(BALANCES_FILE, balances)
                _drop_user_cache(user_id)
                branch_no = await add_business(user_id, key)
                await message.reply(
                    f"???????????? ????? ??????: {info['name']}\n"
                    f"??????: #{branch_no}\n"
                    "??? ????????? ?????????? ????????? /??????."
                )
                return True

            kb = Keyboard(inline=True)
            lines = ["?? ???????? ?????? ??? ???????:"]
            for idx, key in enumerate(keys, start=1):
                info = BUSINESSES_CATALOG[key]
                lines.append(f"{idx}. {info['name']} ? {format_number(int(info['price']))}$")
                kb.add(Callback(f"{idx}", {"command": "buy_business", "business_key": key}), color=KeyboardButtonColor.PRIMARY)
                if idx % 5 == 0:
                    kb.row()
            await message.reply("\n".join(lines) + "\n\n???????: /?????? ?????", keyboard=kb)
            return True

        if command in ["ппрод", "prod", "restock"]:
            biz_list = await get_user_businesses(user_id)
            if not biz_list:
                await message.reply("У вас нет бизнесов для пополнения.")
                return True
            kb = Keyboard(inline=True)
            for b in biz_list:
                kb.add(
                    Callback(f'{b["meta"]["name"]} #{b["branch_no"]}', {"command": "biz_refill_prompt", "business_id": b["id"]}),
                    color=KeyboardButtonColor.PRIMARY
                ).row()
            await message.reply("Выберите бизнес для пополнения продуктов:", keyboard=kb)
            return True

        if command in ["инв", "inv", "inventory"]:
            items = await get_inventory(user_id)
            if not items:
                await message.reply("🎒 Инвентарь пуст.")
                return True
            lines = ["🎒 Инвентарь пользователя:\n"]
            kb = Keyboard(inline=True)
            idx = 1
            for item in items:
                lines.append(f"{idx}. {item['item_name']}")
                kb.add(Callback(f"Использовать {idx}", {"command": "inv_use_prompt", "item_id": item["id"]}), color=KeyboardButtonColor.PRIMARY).row()
                idx += 1
            await message.reply("\n".join(lines), keyboard=kb)
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
            
        if command in ['минет', 'отсос', 'отсосать', 'minet', 'сосать']:
        	# title = chat_info.items[0].chat_settings.title if chat_info.items else "ошибка"
            if chat_id in chatsbansgame:
                await message.reply(f"🚫 В чате «{title}» запрещены игры.\n\nИграйте в - https://vk.me/join/HqDuIRtr4H5TV3y4xZPQbl0rpacZxmFOyEQ=")
                return True
        	
            if message.reply_message:
                user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
            else:
                user = user_id
                
            if user == 488828183:
                return await message.answer("Нельзя использовать команду на этом пользователе")

            # Получаем имя цели
            try:
                info = await bot.api.users.get(user_ids=user)
                name_target = f"{info[0].first_name} {info[0].last_name}"
            except:
                if user < 0:
                    name_target = f"@club{abs(user)} (Не удалось получить имя)"
                else:
                    name_target = f"@id{user} (Не удалось получить имя)"

            # Получаем имя инициатора
            try:
                info = await bot.api.users.get(user_ids=user_id)
                name = f"{info[0].first_name} {info[0].last_name}"
            except:
                name = f"@id{user_id} (Не удалось получить имя)"

            if user < 0:
                await message.reply(
                    f"🔞 | @id{user_id} ({name}) отсосал(-а) у @club{abs(user)} ({name_target})",
                    disable_mentions=1
                )
            else:
                await message.reply(
                    f"🔞 | @id{user_id} ({name}) отсосал(-а) у @id{user} ({name_target})",
                    disable_mentions=1
                )
            return True
      
        if command in ['трахнуть', 'секс', 'seks', 'трах', 'trax']:
        	# title = chat_info.items[0].chat_settings.title if chat_info.items else "ошибка"
            if chat_id in chatsbansgame:
                await message.reply(f"🚫 В чате «{title}» запрещены игры.\n\nИграйте в - https://vk.me/join/HqDuIRtr4H5TV3y4xZPQbl0rpacZxmFOyEQ=")
                return True
        	
            if message.reply_message:
                user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
            else:
                user = user_id
                
            if user == 488828183:
                return await message.answer("Нельзя использовать команду на этом пользователе")

            # Получаем имя цели
            try:
                info = await bot.api.users.get(user_ids=user)
                name_target = f"{info[0].first_name} {info[0].last_name}"
            except:
                if user < 0:
                    name_target = f"@club{abs(user)} (Не удалось получить имя)"
                else:
                    name_target = f"@id{user} (Не удалось получить имя)"

            # Получаем имя инициатора
            try:
                info = await bot.api.users.get(user_ids=user_id)
                name = f"{info[0].first_name} {info[0].last_name}"
            except:
                name = f"@id{user_id} (Не удалось получить имя)"

            if user < 0:
                await message.reply(
                    f"🔞 | @id{user_id} ({name}) принудил(-а) к интиму @club{abs(user)} ({name_target})",
                    disable_mentions=1
                )
            else:
                await message.reply(
                    f"🔞 | @id{user_id} ({name}) принудил(-а) к интиму @id{user} ({name_target})",
                    disable_mentions=1
                )
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
            if await get_role(user_id, chat_id) < 9:
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
            if await get_role(user_id, chat_id) < 13:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == 89:
                await message.replyLocalizedMessage('testers_chat') #

В рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)\n                return True\n\n            # Определяем пользователя\n            target = int\n            arg = 0\n            if message.reply_message:\n                target = message.reply_message.from_id\n                arg = 1\n            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:\n                target = message.fwd_messages[0].from_id\n                arg = 1\n            elif len(arguments) >= 2 and await getID(arguments[1]):\n                target = await getID(arguments[1])\n                arg = 2\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            # Проверка — не в ЧС ли уже\n            sql.execute("SELECT * FROM blacklist WHERE user_id = ?", (target,))\n            if sql.fetchone():\n                await message.reply("Данный пользователь уже находится в черном списке бота!", disable_mentions=1)\n                return True\n\n            if await equals_roles(user_id, target, chat_id, message) < 2:\n                await message.reply("Вы не можете добавить данного пользователя в ЧС!", disable_mentions=1)\n                return True\n\n            reason = await get_string(arguments, arg)\n            if not reason:\n                await message.reply("Укажите причину блокировки!", disable_mentions=1)\n                return True\n\n            date_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")\n\n            sql.execute("INSERT INTO blacklist (user_id, moderator_id, reason_gban, datetime_globalban) VALUES (?, ?, ?, ?)",\n                        (target, user_id, reason, date_now))\n            database.commit()\n\n            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) добавил @id{target} ({await get_user_name(target, chat_id)}) в черный список бота", disable_mentions=1)\n            await chats_log(user_id=user_id, target_id=target, role=None, log=f"добавил @id{target} (пользователя) в Чёрный список. Причина: {reason}")            \n            return True\n\n\n        # === Удаление из Чёрного списка ===\n        if command in ['unblack', 'убратьчс', 'blackdel', 'unch']:\n            if await get_role(user_id, chat_id) < 13:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            if chat_id == 89:\n                await message.replyLocalizedMessage('testers_chat') #\n\nВ рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)
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
            if await get_role(user_id, chat_id) < 9:
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

            # Эмодзи рулетки
            emojis = ["💎", "🍒", "🍀", "🪙", "🔔", "🍋", "💰", "⭐️", "🔥", "🎲"]

            # Генерация случайных трёх эмодзи
            result = random.choices(emojis, k=3)

            # Проверка на джекпот
            jackpot = False
            if result[0] == result[1] == result[2]:
                jackpot = True

            # Подсчитываем бонусы
            multiplier = 0.0
            bonuses = {
                "💎": 0.3,  # 30%
                "🪙": 0.1,  # 10%
                "🔔": 0.5   # 50%
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
                balances[str(user_id)] = bal
                save_data(BALANCES_FILE, balances)

                await message.reply(
                    f"🎰 Вы сыграли на ставку «{format_number(stake)}»\n"
                    f"Результат: {' '.join(result)}\n\n"
                    f"❌ Не выпали 💎, 🪙 или 🔔 — вы проиграли!"
                )
                return
            else:
                win_amount = stake

                if multiplier > 0:
                    win_amount = int(stake * (1 + multiplier))

                # Если джекпот — утроить выигрыш
                if jackpot:
                    win_amount = int(win_amount * 3)

                profit = win_amount - stake
                bal["wallet"] -= stake
                bal["wallet"] += win_amount
                balances[str(user_id)] = bal
                save_data(BALANCES_FILE, balances)
                await log_economy(user_id=user_id, target_id=None, amount=stake, log=f"сыграл(-а) в «Казино» на {stake}$")

                emoji_str = ", ".join(triggered) if triggered else "нет"
                jackpot_text = ""
                if jackpot:
                    jackpot_text = f"\n\n❗ JECKPOT! 3 одинаковых {result[0]} 🔥🔥🔥"

                await message.reply(
                    f"🎰 Вы сыграли на ставку «{format_number(stake)}»\n"
                    f"Результат: {' '.join(result)}{jackpot_text}\n\n"
                    f"Выпали: {emoji_str}\n"
                    f"📈 Общий бонус: +{int(multiplier * 100)}%\n"
                    f"💰 Выигрыш: {format_number(win_amount)}$ (прибыль: {format_number(profit)}$)"
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
                    9: "Заместитель директора",
                    11: "Осн. заместитель директора",
                    13: "Директор бота",
                    14: "Разработчик бота",
                    8: "Тестировщик бота",
                    10: "Зам. главного тестировщика бота",
                    12: "Главный тестировщик бота"
                }

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
                        'role': roles.get(role),
                        'bans': bans_count,
                        'gban': globalban,
                        'gbanpl': gban_status,
                        'warns': warns,
                        'mute': mute_status,
                        'nickname': nick,
                        'messages': messages['count'],
                        'last_message': messages['last'],
                        'messages_today': ms,                        
                    }, keyboard=keyboard)
                return True

        if command in ['подписка']:
            if await get_role(user_id, chat_id) < 0:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            PUB_ID = "232734612"
            subs = load_json_file(SUBS_FILE)
            user_key = str(user_id)
            if subs.get(user_key):
                await message.reply("Вы уже активировали подписку и получили награду.", disable_mentions=1)
                return True

            try:
                resp = await bot.api.groups.is_member(group_id=PUB_ID, user_id=user_id)
                member = getattr(resp, "member", None)
                if member is None:
                    member = bool(resp)
            except Exception as e:
                print(f"[подписка] is_member error: {e}")
                member = False

            if not member:
                await message.reply("❗ Подпишитесь на сообщество, https://vk.ru/public232734612", disable_mentions=1)
                return True

            try:
                await give_money_and_vip_fallback(user_id, 70000, 7)
            except Exception as e:
                print(f"[подписка] reward error: {e}")

            subs[user_key] = {
                "time": datetime.now().isoformat(),
                "reward": {"money": 70000, "vip_days": 7}
            }
            save_json_file(SUBS_FILE, subs)
            await message.reply(f"✅ @id{user_id} ({await get_user_name(user_id, chat_id)}) вы подписались на сообщество и получили бонус: 70.000$ и VIP на 7 дней.", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=None, role=None, log="получил награду за подписку")
            return True
            
        if command in ['blacklist']:
            if await get_role(user_id, chat_id) < 9:
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
            if await get_role(user_id, chat_id) < 9:
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
            if await get_role(user_id, chat_id) < 13:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == 89:
                await message.replyLocalizedMessage('testers_chat') #

В рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)\n                return True\n\n            if len(arguments) < 2:\n                await message.reply("Укажите чат!")\n                return True\n\n            try:\n                target_chat = int(arguments[1])\n            except:\n                await message.reply("Укажите чат!")\n                return True\n\n            sql.execute("SELECT chat_id FROM banschats WHERE chat_id = ?", (target_chat,))\n            if sql.fetchone():\n                await message.reply("Беседа уже находится в блокировке!")\n                return True\n\n            sql.execute("INSERT INTO banschats (chat_id) VALUES (?)", (target_chat,))\n            database.commit()\n            \n            target_peer = 2000000000 + target_chat\n            await bot.api.messages.send(\n                peer_id=target_peer,\n                random_id=0,\n                message=(\n                    f"Владелец беседы — не член, уже YUPIK MANAGER! Я не буду здесь работать."\n                )\n            )\n\n            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) заблокировал(-а) беседу №«{target_chat}»")\n            return True\n\n        if command in ["unbanid", "разбанчата"]:\n            if await get_role(user_id, chat_id) < 13:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            if chat_id == 89:\n                await message.replyLocalizedMessage('testers_chat') #\n\nВ рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)
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

        if command in ['statstester', 'тестерстата', 'тестстата']:
            # Проверка: доступна только в чате тестеров
            if chat_id != tchat:
                await message.reply("Данная команда доступна только в тестовом чате!", disable_mentions=1)
                return True

            # Проверка роли — только для тестеров и выше
            if await get_role(user_id, chat_id) < 8:
                await message.reply("Вы не являетесь тестировщиком бота!", disable_mentions=1)
                return True

            # Определяем пользователя для просмотра
            if message.reply_message:
                target = message.reply_message.from_id
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                target = message.fwd_messages[0].from_id
            else:
                target = user_id

            if target < 0:
                await message.reply("Нельзя получить информацию о сообществе!", disable_mentions=1)
                return True

            # Проверка роли — только для тестеров и выше
            if await get_role(target, chat_id) < 8:
                await message.reply("🔹Указанный пользователь не тестировщик, статистика невозможна к рассмотрению!", disable_mentions=1)
                return True

            # Получаем роль
            role = await get_role(target, chat_id)

            # Проверка глобального бана
            sql.execute("SELECT * FROM gbanlist WHERE user_id = ?", (target,))
            gban = sql.fetchone()
            gban_status = "Да" if gban else "Нет"

            # Получаем количество багов
            sql.execute("SELECT COUNT(*) FROM bugsusers WHERE user_id = ?", (target,))
            bug_count = sql.fetchone()[0] or 0

            # Получаем имя и фамилию
            try:
                info = await bot.api.users.get(user_ids=target)
                name = f"{info[0].first_name} {info[0].last_name}"
            except:
                name = f"@id{target} (Не удалось получить имя)"

            # Все роли
            roles = {
                0: "Пользователь",
                1: "Модератор",
                2: "Старший модератор",
                3: "Администратор",
                4: "Старший администратор",
                5: "Зам. спец администратора",
                6: "Спец администратор",
                7: "Владелец беседы",
                9: "Заместитель директора",
                11: "Осн. заместитель директора",
                13: "Директор бота",
                14: "Разработчик бота",
                8: "Тестировщик бота",
                10: "Зам. главного тестировщика ",
                12: "Главный тестировщик ",
            }

            await message.reply(
                f"👾 Информация о @id{target} ({name}):\n\n"
                f"🔹 Роль: {roles.get(role, 'Неизвестно')}\n"
                f"🔹 Глобальная блокировка: {gban_status}\n"
                f"🔹 Всего подано багов: {bug_count}\n\n"
                f"🧩 Вы тестировщик, спасибо за большой вклад в развитие системы!",
                disable_mentions=1
            )
            return True            

        # === /bugcommand — отправка бага ===
        if command in ['bugcommand', 'багкоманда', 'багкмд', 'bugcmd', 'bagcmd']:
            # Проверка, что команда только в чате ID 23
            if chat_id != tchat:
                await message.reply("Данная команда доступна только в официальном тестовом чате бота!", disable_mentions=1)
                return True

            # Проверка роли
            if await get_role(user_id, chat_id) < 8:
                await message.reply("Вы не являетесь тестировщиком бота!", disable_mentions=1)
                return True

            # Проверяем наличие текста бага
            bug_text = await get_string(arguments, 1)
            if not bug_text or len(bug_text) < 5:
                await message.reply("⚠️ Укажите описание бага (минимум 5 символов).", disable_mentions=1)
                return True

            # Получаем текущее количество багов пользователя
            sql.execute("SELECT COUNT(*) FROM bugsusers WHERE user_id = ?", (user_id,))
            bug_count = sql.fetchone()[0]

            # Формируем дату/время
            vremya = datetime.now().strftime("%d/%m/%Y %I:%M:%S %p")

            # Добавляем запись
            sql.execute("INSERT INTO bugsusers (user_id, bug, datetime, bug_counts_user) VALUES (?, ?, ?, ?)",
                        (user_id, bug_text, vremya, bug_count + 1))
            database.commit()

            # Отправляем уведомление разработчику (например, id = 123456789)
            dev_id = 488828183,574393629
            await bot.api.messages.send(
                peer_id=dev_id,
                random_id=0,
                message=f"👾 | Новый баг-репорт команды от @id{user_id} ({await get_user_name(user_id, chat_id)}):\n\n{bug_text}\n\n🕒 {vremya}"
            )

            await message.reply(
                f"@id{user_id} ({await get_user_name(user_id, chat_id)}), Ваш баг принят!\n\n"
                f"Время подачи бага: {vremya}\n"
                f"Содержание бага — {bug_text}\n"
                f"Вы отправили уже — {bug_count + 1} баг(ов).",
                disable_mentions=1
            )
            return True


        # === /buglist — список всех багов ===
        if command in ['buglist', 'баглист', 'баги']:
            if chat_id != tchat:
                await message.reply("Данная команда доступна только в тестовом чате!", disable_mentions=1)
                return True

            if await get_role(user_id, chat_id) < 8:
                await message.reply("У вас недостаточно прав для просмотра списка багов!", disable_mentions=1)
                return True

            # Получаем все баги пользователя
            sql.execute("SELECT datetime, bug, bug_counts_user FROM bugsusers WHERE user_id = ?", (user_id,))
            user_bugs = sql.fetchall()

            if not user_bugs:
                await message.reply("У вас пока нет подданых багов!", disable_mentions=1)
                return True

            # Формируем список
            bugs_text = ""
            for i, (vremya, bug, count) in enumerate(user_bugs, start=1):
                bugs_text += f"{i}) Время: {vremya} || Баг: {bug}\n"

            total_bugs = user_bugs[-1][2]  # берём последнее значение счётчика

            await message.reply(
                f"❗ | Список ваших поданных багов:\n\n{bugs_text}\n\nВсего багов подано: {total_bugs}",
                disable_mentions=1
            )
            return True            
            
        if command in ["clearchat", "удалитьчат"]:
            if await get_role(user_id, chat_id) < 13:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == 89:
                await message.replyLocalizedMessage('testers_chat') #

В рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)\n                return True\n\n            if len(arguments) < 2:\n                await message.reply("Укажите чат!")\n                return True\n\n            try:\n                target_chat = int(arguments[-1])\n            except:\n                await message.reply("Укажите чат!")\n                return True\n                \n            target_peer = 2000000000 + target_chat\n            await bot.api.messages.send(\n                peer_id=target_peer,\n                random_id=0,\n                message=(\n                    f"Чат удален из базы данных бота! Работа бота в чате прекращена."\n                )\n            )\n\n            sql.execute("DELETE FROM chats WHERE chat_id = ?", (target_chat,))\n            database.commit()\n\n            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) удалил(-а) беседу №«{target_chat}»")\n            return True\n                        \n        if command in ['help', 'помощь', 'хелп', 'команды', 'commands']:\n            commands_levels = {\n                0: [\n                    'Команды пользователя:',\n                    '/info -- офицальные ресурсы проекта',\n                    '/правила — правила чата установленные владельцем беседы',\n                    '/infobot — офицальные ресурсы бота',                    \n                    '/stats -- информация о пользователе',\n                    '/getid -- узнать оригинальный ID пользователя в ВК',\n                    '/q -- выход из текущей беседы',\n                    '/игры -- игровые команды',\n                    '/form -- подать форму на бан (в определенном чате)',\n                    '/offer -- предложить улучшение для бота'\n                ],\n                1: [\n                    '\nКоманды модератора:',\n                    '/setnick — сменить ник у пользователя',\n                    '/removenick — очистить ник у пользователя',\n                    '/getnick — проверить ник пользователя',\n                    '/getacc — узнать пользователя по нику',\n                    '/nlist — просмотреть ники пользователей',\n                    '/nonick — пользователи без ников',\n                    '/kick — исключить пользователя из беседы',\n                    '/warn — выдать предупреждение пользователю',\n                    '/unwarn — снять предупреждение пользователю',\n                    '/getwarn — информация о активных предупреждениях пользователя',\n                    '/warnhistory — информация о всех предупреждениях пользователя',\n                    '/warnlist — список пользователей с варном',\n                    '/staff — пользователи с ролями',\n                    '/mute — замутить пользователя',\n                    '/unmute — размутить пользователя',\n                    '/alt — узнать альтернативные команды',\n                    '/getmute -- информация о муте пользователя',\n                    '/mutelist -- список пользователей с мутом',\n                    '/clear -- очистить сообщения',\n                    '/getban -- информация о банах пользователя',\n                    '/delete -- удалить сообщение пользователя',\n                    '/chatid -- узнать оригинальный айди чата в боте'                    \n                ],\n                2: [\n                    '\nКоманды старшего модератора:',\n                    '/ban — заблокировать пользователя в беседе',\n                    '/unban -- разблокировать пользователя в беседе',\n                    '/addmoder -- выдать пользователю модератора',\n                    '/removerole -- забрать роль у пользователя',\n                    '/zov -- упомянуть всех пользователей',\n                    '/online -- упомянуть пользователей онлайн',\n                    '/onlinelist — посмотреть пользователей в онлайн',\n                    '/banlist -- посмотреть заблокированных',\n                    '/inactivelist -- список неактивных пользователей'\n                ],\n                3: [\n                    '\nСписок команд администратора:',\n                    '/quiet -- Включить выключить режим тишины',\n                    '/skick -- исключить пользователя с бесед сетки',\n                    '/sban -- заблокировать пользователя в сетке бесед',\n                    '/sunban — разбанить пользователя в сетке бесед',\n                    '/addsenmoder — выдать права старшего модератора',\n                    '/rnickall -- очистить все ники в беседе',\n                    '/sremovenick -- очистить ник у пользователя в сетке бесед',\n                    '/szov -- вызов участников бесед сетки',\n                    '/srole -- выдать права в сетке бесед'\n                ],\n                4: [\n                    '\nСписок команд старшего администратора:',\n                    '/addadmin -- выдать права администратора',\n                    '/serverinfo -- информация о сервере',\n                    '/filter -- фильтр запрещенных слов',\n                    '/sremoverole -- забрать роль у пользователя в сетке бесед',\n                    '/ssetnick -- установить ник в сетке бесед',\n                    '/bug -- отправить баг-трекер разработчику бота',\n                    '/report -- жалоба на пользователя'                   \n                ],\n                5: [\n                    '\nСписок команд зам. спец администратора:',\n                    '/addsenadmin -- выдать права старшего администратора',\n                    '/sync -- синхронизация с базой данных',\n                    '/pin -- закрепить сообщение',\n                    '/unpin -- открепить сообщение',\n                    '/deleteall -- удалить последние 200 сообщений пользователя',\n                    '/gsinfo -- информация о глобальной привязке',\n                    '/gsrnick -- очистить ник у пользователя в беседах привязки',\n                    '/gssnick -- поставить ник пользователю в беседах привязки',\n                    '/gskick -- исключить пользователя с бесед привязки',\n                    '/gsban -- заблокировать пользователя в беседах привязки',\n                    '/gsunban -- разбанить пользователя в беседах привязки'                    \n                ],                \n                6: [\n                    '\nСписок команд спец. администратора:',\n                    '/addzsa -- выдать права зам. спец. администратора',\n                    '/server -- привязать беседу к серверу',\n                    '/settings -- показать настройки беседы',\n                    '/clearwarn -- снять варны всем пользователям',\n                    '/title -- изменить название беседы',\n                    '/antisliv -- включить систему антислива в беседе'\n                ],                \n                7: [\n                    '\nСписок команд владельца беседы:',\n                    '/addsa -- выдать права спец. администратора',\n                    '/antiflood -- режим защиты от спама',\n                    '/welcometext -- текст приветствия',\n                    '/invite -- система добавления пользователей только модераторами',\n                    '/leave -- система исключения пользователей при выходе',\n                    '/editowner -- передать права владельца беседы',\n                    '/masskick -- исключить участников без ролей',\n                    '/защита -- защита от сторонних сообществ',\n                    '/settingsmute -- включить выдачу варнов за написание сообщений в муте',\n                    '/setinfo -- установить информацию о официальных ресурсах проекта в «/info»',\n                    '/setrules -- установить правила беседы в «/rules»',\n                    '/type – изменить тип беседы',\n                    '/gsync -- поставить глобальную синхронизацию бесед',\n                    '/gunsync – отключить глобальную синхронизацию бесед',\n                    '/masskick -- исключить нескольких пользователей',\n                    '/amnesty -- амнистия наказаний в чате',\n                    '/settingsgame -- запретить игры в беседе',\n                    '/settingsphoto -- запретить отправку фото в беседу'\n                ],        \n                8: [\n                    '\nСписок команд тестировщика бота:',\n                    '/bugcommand — подать баг на команду',\n                    '/statstester — посмотреть свою статистику тестера',\n                    '/buglist — посмотреть список отправленых багов на команды'\n                ],          \n                9: [\n                    '\nСписок команд заместителя директора:',\n                    '/gbanpl -- заблокировать пользователя во всех игровых беседах',\n                    '/gunbanpl -- разбанить пользователя во всех игровых беседах',\n                    '/gban -- заблокировать пользователя во всех беседах',\n                    '/ungban -- разблокировать пользователя во всех беседах',\n                    '/логиэко -- логирование экономики (пользователя или общие)',\n                    '/логи -- логи модераторских действий (пользователя или общие)',\n                    '/gbanlist -- список пользователей в глобальной блокировке',\n                    '/blacklist -- список пользователей в черном списке бота'\n                ],\n                10: [\n                    '\nСписок команд заместителя главного тестировщика:',\n                    '/settester — выдать права тестировщика бота (только в определенном чате)',\n                    '/testerslist — список тестеров бота'\n                ], \n                11: [\n                    '\nСписок команд осн. заместителя директора:',\n                    '/addzamdirector – выдать права заместителя директора',\n                    '/setowner – установить владельца беседы',\n                    '/gstaff – пользователи с глобальными ролями',\n                    '/grrole -- забрать роль (глобальную)'\n                ],\n                12: [\n                    '\nСписок команд главного тестировщика:',\n                    '/addzamtester — выдать права заместителя тестировщика бота',\n                    '/сглтестер — вернуть себе права тестировщика бота',\n                    '/unglobaltester — снять права тестировщика бота (глобально)',\n                    '/addgltester — выдать права главного тестера',\n                    '/deltester -- снять права тестировщика бота во всех беседах'\n                ],\n                13: [\n                    '\nСписок команд директора бота:',\n                    '/infoid -- группы по айди владельца',\n                    '/banid -- забанить группу в боте по чат айди',\n                    '/unbanid -- разбанить группу в боте по чат айди',\n                    '/say -- сообщение от имени бота',\n                    '/addoszamdirector – выдать права основного заместителя директора', \n                    '/clearchat -- очистить все данные из определенного чата',                   \n                    '/listchats -- список чатов',\n                    '/gzov -- упомянуть всех пользователей в категории бесед',\n                    '/banwords -- просмотр списка запрещённых слов',\n                    '/addbanwords -- добавить запрещённое слово',     \n                    '/removebanwords -- удалить запрещённое слово',               \n                    '/give -- выдать монеты',\n                    '/addblack -- добавить пользоваля в черный список бота',\n                    '/unblack -- вынести пользователя из черного списка бота',\n                    '/infochat -- информация о беседе по айди',\n                    '/zunban -- снять все баны пользователю',  \n                    '/createpromo -- создать промо-код',                  \n                    '/clearbans -- удалить все блокировки в определенном чате'\n                ],                \n                14: [\n                    '\nСписок команд разработчиков бота:',\n                    '/resetmoney -- обнулить баланс пользователя',\n                    '/раздача -- раздача монет пользователям',\n                    '/adddirector -- выдать права директора бота',\n                    '/removeduel -- удалить активную дуэль в беседе',\n                    '/оффроль -- снять с себя права',\n                    '/adddev -- выдать права разработчика бота'\n                ]                \n            }\n\n            user_role = await get_role(user_id, chat_id)\n\n            if user_role > 1:\n                keyboard = (\n                    Keyboard(inline=True)\n                    .add(Callback("Альтернативные команды", {"command": "alt", "chatId": chat_id}), color=KeyboardButtonColor.PRIMARY)\n                )\n            else:\n                keyboard = None\n\n            commands = []\n            for i in commands_levels.keys():\n                if i <= user_role:\n                    for b in commands_levels[i]:\n                        commands.append(b)\n\n            level_commands = '\n'.join(commands)\n\n            await message.reply(f"{level_commands}", disable_mentions=1, keyboard=keyboard)\n            await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) список доступных команд")            \n\n        if command in ['snick', 'setnick', 'nick', 'addnick', 'ник', 'сетник', 'аддник']:\n            if await get_role(user_id, chat_id) < 1:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            user = int\n            arg = 0\n            if message.reply_message:\n                user = message.reply_message.from_id\n                arg = 1\n            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:\n                user = message.fwd_messages[0].from_id\n                arg = 1\n            elif len(arguments) >= 2 and await getID(arguments[1]):\n                user = await getID(arguments[1])\n                arg = 2\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            if await equals_roles(user_id, user, chat_id, message) == 0:\n                await message.replyLocalizedMessage('command_setnick_preminissions')\n                return True\n\n            new_nick = await get_string(arguments, arg)\n            if not new_nick:\n                await message.replyLocalizedMessage('command_setnick_nick')\n                return True\n            else: await setnick(user, chat_id, new_nick)\n\n            await message.replyLocalizedMessage('command_setnick', {\n                        'user': userf,\n                        'target': f'@id{user} (пользователю)',\n                        'nick': new_nick\n                    })\n            await chats_log(user_id=user_id, target_id=user, role=None, log=f"установил(-а) новый ник @id{user} (пользователю). Новый ник: {new_nick}")                       \n\n        if command in ['rnick', 'removenick', 'clearnick', 'cnick', 'рник', 'удалитьник', 'снятьник']:\n            if await get_role(user_id, chat_id) < 1:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            user = int\n            if message.reply_message: user = message.reply_message.from_id\n            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:\n                user = message.fwd_messages[0].from_id\n            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            if await equals_roles(user_id, user, chat_id, message) == 0:\n                await message.replyLocalizedMessage('command_removenick_premminisions')\n                return True\n\n            await rnick(user, chat_id)\n            await message.replyLocalizedMessage('command_removenick', {\n                        'user': userf,\n                        'target': f'@id{user} (пользователю)'\n                    })\n            await chats_log(user_id=user_id, target_id=user, role=None, log=f"удалил(-а) старый ник @id{user} (пользователю)")            \n\n        if command in ['type', 'тип']:\n            if await get_role(user_id, chat_id) < 7:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            # получаем аргумент (новый тип)\n            if len(arguments) < 2:\n                # тип не указан, показываем текущий тип\n                sql.execute(f"SELECT type FROM chats WHERE chat_id = {chat_id}")\n                current_type = sql.fetchone()\n                if current_type:\n                    type_value = current_type[0]\n                    await message.reply(\n                        f"Беседа имеет тип: {chat_types.get(type_value, type_value)}

"\n                        "Все типы бесед:
" +\n                        "
".join([f"{k} -- {v}" for k, v in chat_types.items()]),\n                        disable_mentions=1\n                    )\n                return True\n\n            new_type = arguments[1].lower()\n\n            # проверка на валидность\n            if new_type not in chat_types:\n                await message.reply(\n                    "Неверный тип беседы, типы:
" +\n                    "
".join([f"{k} -- {v}" for k, v in chat_types.items()]),\n                    disable_mentions=1\n                )\n                return True\n\n            # устанавливаем новый тип\n            sql.execute(f"UPDATE chats SET type = ? WHERE chat_id = ?", (new_type, chat_id))\n            database.commit()\n\n            await message.replyLocalizedMessage('command_settype', {\n                        'type': chat_types[new_type]\n                    })            \n            await chats_log(user_id=user_id, target_id=None, role=None, log=f"установил(-а) новый тип беседы. Новый тип: {chat_types[new_type]}")            \n            \n        if command in ["settings", "настройки"]:\n            if await get_role(user_id, chat_id) < 6:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return\n\n            # Получаем владельца чата через VK API\n            x = await bot.api.messages.get_conversations_by_id(\n                peer_ids=peer_id,\n                extended=1,\n                fields='chat_settings',\n                group_id=message.group_id\n            )\n            x = json.loads(x.json())\n            chat_owner = None\n            chat_title = None\n            for i in x['items']:\n                chat_owner = int(i["chat_settings"]["owner_id"])\n                chat_title = i["chat_settings"]["title"]\n\n            # Получаем данные из базы по chat_id\n            sql.execute(f"SELECT type, in_pull, filter, leave_kick, invite_kick, antiflood FROM chats WHERE chat_id = {chat_id}")\n            row = sql.fetchone()\n            if row:\n                type_value = chat_types.get(row[0], row[0])\n                server = await get_current_server(chat_id)\n                filter_text = "Включено" if row[2] == 1 else "Выключено"\n                leave_text = "Включено" if row[3] == 1 else "Выключено"\n                invite_text = "Включено" if row[4] == 1 else "Выключено"\n                antiflood_text = "Включено" if row[5] == 1 else "Выключено"\n            else:\n                type_value = "Общие беседы"\n                server = "0"\n                filter_text = "Выключено"\n                leave_text = "Выключено"\n                invite_text = "Выключено"\n                antiflood_text = "Выключено"\n\n            await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) текущие настройки беседы")            \n            await message.replyLocalizedMessage('command_settings', {\n                        'chat_title': chat_title,\n                        'owner': f'@id{chat_owner} ({await get_user_name(chat_owner, chat_id)})',\n                        'type': type_value,\n                        'chat_id': chat_id,\n                        'filter': filter_text,\n                        'leave': leave_text,\n                        'antiflood': antiflood_text,\n                        'invite': invite_text,\n                        'server': server                                                                                               \n                    })            \n            return            \n\n        if command in ['gsrnick', 'грник']:\n            if await get_role(user_id, chat_id) < 5:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            gsync_chats = await get_gsync_chats(chat_id)\n            if not gsync_chats:\n                await message.reply("Беседа не привязана к глобальной связке!", disable_mentions=1)\n                return True\n\n            user = int\n            if message.reply_message:\n                user = message.reply_message.from_id\n            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:\n                user = message.fwd_messages[0].from_id\n            elif len(arguments) >= 2 and await getID(arguments[1]):\n                user = await getID(arguments[1])\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            if await equals_roles(user_id, user, chat_id, message) == 0:\n                await message.reply("Вы не можете снять ник у данного пользователя!", disable_mentions=1)\n                return True\n\n            for i in gsync_chats:\n                try:\n                    await rnick(user, i)\n                except:\n                    continue\n\n            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) убрал ник у @id{user} (пользователя) во всех беседах глобальной связки.", disable_mentions=1)\n            await chats_log(user_id=user_id, target_id=user, role=None, log=f"снял ник @id{user} (пользователю) во всех беседах глобальной связки")\n            return True\n            \n        if command in ['gssnick', 'гссник']:\n            if await get_role(user_id, chat_id) < 5:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            gsync_chats = await get_gsync_chats(chat_id)\n            if not gsync_chats:\n                await message.reply("Беседа не привязана к глобальной связке!", disable_mentions=1)\n                return True\n\n            user = int\n            arg = 0\n            if message.reply_message:\n                user = message.reply_message.from_id\n                arg = 1\n            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:\n                user = message.fwd_messages[0].from_id\n                arg = 1\n            elif len(arguments) >= 2 and await getID(arguments[1]):\n                user = await getID(arguments[1])\n                arg = 2\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            if await equals_roles(user_id, user, chat_id, message) == 0:\n                await message.reply("Вы не можете установить ник данному пользователю!", disable_mentions=1)\n                return True\n\n            new_nick = await get_string(arguments, arg)\n            if not new_nick:\n                await message.reply("Укажите ник!", disable_mentions=1)\n                return True\n\n            for i in gsync_chats:\n                try:\n                    await setnick(user, i, new_nick)\n                except:\n                    continue\n\n            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) установил ник @id{user} (пользователю) во всех беседах глобальной связки.
Новый ник: {new_nick}", disable_mentions=1)\n            await chats_log(user_id=user_id, target_id=user, role=None, log=f"установил ник {new_nick} @id{user} (пользователю) во всех беседах глобальной связки")\n            return True\n\n        if command in ['settingsphoto', 'настройкифото']:\n            if await get_role(user_id, chat_id) < 7:\n                await message.reply("Недостаточно прав!", disable_mentions=1)\n                return True\n\n            sql.execute("SELECT * FROM photosettings WHERE chat_id = ?", (chat_id,))\n            row = sql.fetchone()\n            if row is None:\n                sql.execute("INSERT INTO photosettings (chat_id, mode) VALUES (?, ?)", (chat_id, 1))\n                database.commit()\n                await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), включил(-а) систему удаления фотографий!", disable_mentions=1)\n            else:\n                new_mode = 0 if row[1] == 1 else 1\n                sql.execute("UPDATE photosettings SET mode = ? WHERE chat_id = ?", (new_mode, chat_id))\n                database.commit()\n                if new_mode == 0:\n                    await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), выключил(-а) систему удаления фотографий!", disable_mentions=1)\n                else:\n                    await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), включил(-а) систему удаления фотографий!", disable_mentions=1)\n\n            return True            \n\n        if command in ['settingsgame', 'настройкиигр']:\n            if await get_role(user_id, chat_id) < 7:\n                await message.reply("Недостаточно прав!", disable_mentions=1)\n                return True\n\n            sql.execute("SELECT * FROM gamesettings WHERE chat_id = ?", (chat_id,))\n            row = sql.fetchone()\n            if row is None:\n                sql.execute("INSERT INTO gamesettings (chat_id, mode) VALUES (?, ?)", (chat_id, 1))\n                database.commit()\n                await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), включил(-а) систему блокировки игровых команд!", disable_mentions=1)\n            else:\n                new_mode = 0 if row[1] == 1 else 1\n                sql.execute("UPDATE gamesettings SET mode = ? WHERE chat_id = ?", (new_mode, chat_id))\n                database.commit()\n                if new_mode == 0:\n                    await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), выключил(-а) систему блокировки игровых команд!", disable_mentions=1)\n                else:\n                    await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), включил(-а) систему блокировки игровых команд!", disable_mentions=1)\n\n            return True\n\n        if command in ['gskick', 'гскик']:\n            if await get_role(user_id, chat_id) < 5:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            gsync_chats = await get_gsync_chats(chat_id)\n            if not gsync_chats:\n                await message.reply("Беседа не привязана к глобальной связке!", disable_mentions=1)\n                return True\n\n            user = int\n            reason = None\n            if message.reply_message:\n                user = message.reply_message.from_id\n            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:\n                user = message.fwd_messages[0].from_id\n            elif len(arguments) >= 2 and await getID(arguments[1]):\n                user = await getID(arguments[1])\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            if await equals_roles(user_id, user, chat_id, message) < 2:\n                await message.reply("Вы не можете исключить данного пользователя!", disable_mentions=1)\n                return True\n\n            for i in gsync_chats:\n                try:\n                    await bot.api.messages.remove_chat_user(i, user)\n                    msg = f"@id{user_id} ({await get_user_name(user_id, chat_id)}) исключил @id{user} ({await get_user_name(user, chat_id)}) в беседах глобальной связки!"\n                    if reason:\n                        msg += f"
Причина: {reason}"\n                    await bot.api.messages.send(peer_id=2000000000 + i, message=msg, disable_mentions=1, random_id=0)\n                except:\n                    continue\n\n            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) исключил @id{user} (пользователя) из всех бесед глобальной связки.", disable_mentions=1)\n            await chats_log(user_id=user_id, target_id=user, role=None, log=f"исключил @id{user} из всех бесед глобальной связки")\n            return True\n\n        if command in ['gsban', 'гсбан']:\n            if await get_role(user_id, chat_id) < 5:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            gsync_chats = await get_gsync_chats(chat_id)\n            if not gsync_chats:\n                await message.reply("Беседа не привязана к глобальной связке!", disable_mentions=1)\n                return True\n\n            user = int\n            arg = 0\n            if message.reply_message:\n                user = message.reply_message.from_id\n                arg = 1\n            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:\n                user = message.fwd_messages[0].from_id\n                arg = 1\n            elif len(arguments) >= 2 and await getID(arguments[1]):\n                user = await getID(arguments[1])\n                arg = 2\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            if await equals_roles(user_id, user, chat_id, message) < 2:\n                await message.reply("Вы не можете заблокировать данного пользователя!", disable_mentions=1)\n                return True\n\n            reason = await get_string(arguments, arg)\n            if not reason:\n                await message.reply("Укажите причину блокировки!", disable_mentions=1)\n                return True\n\n            for i in gsync_chats:\n                try:\n                    await ban(user, user_id, i, reason)\n                    await bot.api.messages.remove_chat_user(i, user)\n                    msg = f"@id{user_id} ({await get_user_name(user_id, chat_id)}) исключил @id{user} ({await get_user_name(user, chat_id)}) в беседах глобальной связки!"\n                    if reason:\n                        msg += f"
Причина: {reason}"\n                    await bot.api.messages.send(peer_id=2000000000 + i, message=msg, disable_mentions=1, random_id=0)\n                except:\n                    continue\n\n            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) заблокировал @id{user} (пользователя) во всех беседах глобальной связки.
Причина: {reason}", disable_mentions=1)\n            await chats_log(user_id=user_id, target_id=user, role=None, log=f"заблокировал @id{user} (пользователя) во всех беседах глобальной связки. Причина: {reason}")\n            return True            \n            \n        if command in ['gsunban', 'гсунбан']:\n            if await get_role(user_id, chat_id) < 5:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            gsync_chats = await get_gsync_chats(chat_id)\n            if not gsync_chats:\n                await message.reply("Беседа не привязана к глобальной связке!", disable_mentions=1)\n                return True\n\n            user = int\n            if message.reply_message:\n                user = message.reply_message.from_id\n            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:\n                user = message.fwd_messages[0].from_id\n            elif len(arguments) >= 2 and await getID(arguments[1]):\n                user = await getID(arguments[1])\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            if await equals_roles(user_id, user, chat_id, message) == 0:\n                await message.reply("Вы не можете разбанить данного пользователя!", disable_mentions=1)\n                return True\n\n            for i in gsync_chats:\n                try:\n                    await unban(user, i)\n                except:\n                    continue\n\n            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) снял блокировку с @id{user} (пользователя) во всех беседах глобальной связки.", disable_mentions=1)\n            await chats_log(user_id=user_id, target_id=user, role=None, log=f"разблокировал @id{user} во всех беседах глобальной связки")\n            return True\n            \n        if command in ['getacc', 'acc', 'гетакк', 'аккаунт', 'account']:\n            if await get_role(user_id, chat_id) < 1:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            nick = await get_string(arguments, 1)\n            if not nick:\n                await message.replyLocalizedMessage('commabd_getacc_params')\n                return True\n\n            nick_result = await get_acc(chat_id, nick)\n\n            if not nick_result: await message.replyLocalizedMessage('command_getacc_not')\n            else:\n                info = await bot.api.users.get(nick_result)\n                await message.reply(f"Ник {nick} принадлежит @id{nick_result} ({info[0].first_name} {info[0].last_name})", disable_mentions=1)\n                await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-a) кому принадлежит НикНейм «{nick}»")            \n\n        if command in ['getnick', 'gnick', 'гник', 'гетник']:\n            if await get_role(user_id, chat_id) < 1:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            user = 0\n            if message.reply_message: user = message.reply_message.from_id\n            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:\n                user = message.fwd_messages[0].from_id\n            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            nick = await get_nick(user, chat_id)\n            if not nick: await message.replyLocalizedMessage('command_getnick_not')\n            else: await message.reply(f"Ник данного @id{user} (пользователя): {nick}", disable_mentions=1)\n            await chats_log(user_id=user_id, target_id=user, role=None, log=f"посмотрел(-а) текущее имя @id{user} (пользователя). Текущий ник: «{nick}»")            \n\n        if command in ['никлист', 'ники', 'всеники', 'nlist', 'nickslist', 'nicklist', 'nicks']:\n            if await get_role(user_id, chat_id) < 1:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            nicks = await nlist(chat_id, 1)\n            nick_list = '\n'.join(nicks)\n            if nick_list == "": nick_list = "Ники отсутствуют!"\n\n            keyboard = (\n                Keyboard(inline=True)\n                .add(Callback("⏪", {"command": "nicksMinus", "page": 1, "chatId": chat_id}), color=KeyboardButtonColor.NEGATIVE)\n                .add(Callback("Без ников", {"command": "nonicks", "chatId": chat_id}), color=KeyboardButtonColor.PRIMARY)\n                .add(Callback("⏩", {"command": "nicksPlus", "page": 1, "chatId": chat_id}), color=KeyboardButtonColor.POSITIVE)\n            )\n\n            await message.reply(f"Пользователи с ником [1 страница]:
{nick_list}

Пользователи без ников: «/nonick»", disable_mentions=1, keyboard=keyboard)\n            await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) пользователей с ником")            \n\n        if command in ['nonick', 'nonicks', 'nonicklist', 'nolist', 'nnlist', 'безников', 'ноникс']:\n            if await get_role(user_id, chat_id) < 1:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            nonicks = await nonick(chat_id, 1)\n            nonick_list = '\n'.join(nonicks)\n            if nonick_list == "": nonick_list = "Пользователи без ников отсутствуют!"\n\n            keyboard = (\n                Keyboard(inline=True)\n                .add(Callback("⏪", {"command": "nonickMinus", "page": 1, "chatId": chat_id}), color=KeyboardButtonColor.NEGATIVE)\n                .add(Callback("С никами", {"command": "nicks", "chatId": chat_id}), color=KeyboardButtonColor.PRIMARY)\n                .add(Callback("⏩", {"command": "nonickPlus", "page": 1, "chatId": chat_id}),\n                     color=KeyboardButtonColor.POSITIVE)\n            )\n\n            await message.reply(f"Пользователи без ников [1]:
{nonick_list}

Пользователи с никами: «/nlist»", disable_mentions=1, keyboard=keyboard)\n            await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) пользователей без ников")            \n\n        if command in ['kick', 'кик', 'исключить']:\n            if await get_role(user_id, chat_id) < 1:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            user = int\n            arg = 0\n            if message.reply_message:\n                user = message.reply_message.from_id\n                arg = 1\n            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:\n                user = message.fwd_messages[0].from_id\n                arg = 1\n            elif len(arguments) >= 2 and await getID(arguments[1]):\n                user = await getID(arguments[1])\n                arg = 2\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            if chat_id == tchat:\n                await message.replyLocalizedMessage('testers_chat') #\n\nВ рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)
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
                except Exception as e: print(f'ПРОИЗОШЛА ОШИБКА ПРИ КИКЕ ЮЗЕРА: {user}', e)
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
                if await get_role(user_id, chat_id) < 13:
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
                if await get_role(user_id, chat_id) < 13:
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
                if await get_role(user_id, chat_id) < 13:
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
                if await get_role(user_id, chat_id) < 13:
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

        if command in ['games', 'game', 'игры', 'gamehelp']:
            await message.replyLocalizedMessage('command_other')
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
                if await get_role(user_id, chat_id) < 13:
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
            if await get_role(user_id, chat_id) < 13:
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

            balances = load_data(BALANCES_FILE)
            if str(target) not in balances:
                balances[str(target)] = get_balance(target)
            bal = balances[str(target)]

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
                            f"\n💸 Депозит: {format_number(deposit_amount)}$ "
                            f"на {days} дн. "
                            f"под {deposit_percent}%"
                            f"\n⏳ До вывода: {days}д {hours}ч {minutes}м"
                        )
                    else:
                        deposit_text = (
                            f"\n💸 Депозит: {format_number(deposit_amount)}$ "
                            f"под {deposit_percent}%"
                            f"\n⏳ До вывода: можно забирать!"
                        )
                except:
                    pass

            await message.reply(
                f"💰 У {mention} {format_number(bal['wallet'])}$\n"
                f"🏛 Счет в банке: {format_number(bal['bank'])}$\n"
                f"🏆 Дуэлей выиграно: {bal['won']}\n"
                f"💔 Дуэлей проиграно: {bal['lost']}\n"
                f"🎉 Всего выиграно: {format_number(bal['won_total'])}$\n"
                f"💰 Всего проиграно: {format_number(bal['lost_total'])}$\n"
                f"📤 Отправлено переводами: {format_number(bal['sent_total'])}$\n"
                f"📥 Получено переводами: {format_number(bal['received_total'])}$\n"
                f"⭐ Статус: {vip_status}\n"
                f"{vip_time}\n"
                f"{deposit_text}"
            )
            return            
          
        # ---------------- GIVEALL / РАЗДАЧА ----------------
        if command in ["giveall", "раздача"]:
            # разрешённый ВК ID администратора
            role = await get_role(user_id, chat_id)
            if role < 11:
                await message.replyLocalizedMessage('not_preminisionss')
                return

            if chat_id == 89:
                await message.replyLocalizedMessage('testers_chat') #

В рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)\n                return True\n\n            if len(arguments) < 1:\n                await message.reply("💰 Пример: /раздача 1000")\n                return\n\n            try:\n                amount = int(arguments[-1])\n                if amount <= 0:\n                    raise ValueError()\n            except:\n                await message.reply("Укажите сумму числом!")\n                return\n\n            # загружаем балансы\n            balances = load_data(BALANCES_FILE)\n\n            all_users_text = ""\n            for i, (uid, bal) in enumerate(balances.items(), start=1):\n                # обновляем кошелёк\n                bal["wallet"] += amount\n\n                # получаем имя пользователя\n                try:\n                    info = await bot.api.users.get(user_ids=uid)\n                    full_name = f"{info[0].first_name} {info[0].last_name}"\n                except:\n                    full_name = f"Ошибка"\n\n                all_users_text += f"{i}. [id{uid}|{full_name}] | 💰 Новый баланс: {format_number(bal['wallet'])}
"\n\n            # сохраняем обновлённые балансы\n            save_data(BALANCES_FILE, balances)\n            await log_economy(user_id=uid, target_id=None, amount=amount, log=f"произвел(-а) раздачу на {amount}$")            \n\n            # формируем сообщение\n            admin_name = f"@id{user_id}"  # или можно получить полное имя администратора\n            await message.reply(\n                f"Раздача на «{format_number(amount)}$» была успешно произведена {admin_name} (администратором бота), монеты получили:

{all_users_text}"\n            )\n            return            \n\n        if command in ['say', 'сообщение']:\n            if await get_role(user_id, chat_id) < 13:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            if len(arguments) < 2:\n                await message.reply("Укажите айди беседы!")\n                return True\n\n            # Парсим target_chat из первого аргумента\n            try:\n                target_chat = int(arguments[1])\n            except ValueError:\n                await message.reply("Укажите конкретный айди беседы!")\n                return True\n\n            # Проверка: если это беседа, прибавляем 2000000000\n            if target_chat > 0:\n                target_peer = 2000000000 + target_chat\n            else:\n                target_peer = target_chat\n\n            # Текст сообщения — всё после первого аргумента\n            text = " ".join(arguments[2:])\n            if not text.strip():\n                await message.reply("Укажите текст сообщения!")\n                return True\n\n            try:\n                await bot.api.messages.send(\n                    peer_id=target_peer,\n                    message=text,\n                    random_id=0\n                )\n                await message.reply(f"Сообщение успешно отправлено в чат ID {target_chat}.")\n                await chats_log(user_id=user_id, target_id=None, role=None, log=f"отправил(-а) сообщение в чат «{target_chat}» Сообщение: {text}")            \n            except Exception as e:\n                await message.reply(f"Произошла ошибка при отправке: {e}")\n                print(f"[say command] Ошибка отправки в чат {target_chat}: {e}")\n            return True\n            \n        # ---------------- GIVE ----------------\n        if command in ["give", "выдать"]:\n            role = await get_role(user_id, chat_id)\n            if role < 10:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return\n\n            if chat_id == 89:\n                await message.replyLocalizedMessage('testers_chat') #\n\nВ рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)
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
                await message.replyLocalizedMessage('testers_chat') #

В рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)\n                return True\n\n            target = await extract_user_id(message)\n            if not target:\n                await message.reply("Укажите пользователя!")\n                return\n\n            balances = load_data(BALANCES_FILE)\n            bal = balances.get(str(target), get_balance(target))\n            amount = bal["wallet"] + bal["bank"]  # сохраняем текущий баланс\n            bal["wallet"] = 0\n            bal["bank"] = 0\n            balances[str(target)] = bal\n            save_data(BALANCES_FILE, balances)\n            await log_economy(user_id=user_id, target_id=target, amount=amount, log=f"обнулил(-а) весь баланс {amount}$ у пользователя {target}")          \n\n            try:\n                s_info = await bot.api.users.get(user_ids=user_id)\n                r_info = await bot.api.users.get(user_ids=target)\n                s_name = f"{s_info[0].first_name} {s_info[0].last_name}"\n                r_name = f"{r_info[0].first_name} {r_info[0].last_name}"\n            except:\n                s_name = str(user_id)\n                r_name = str(target)\n\n            await message.reply(\n                f"[id{user_id}|{s_name}] анулировал(-а) весь баланс «{format_number(amount)}$» у пользователя [id{target}|{r_name}]"\n            )\n            return\n\n        if command in ["передать"]:\n            if get_block_game(chat_id):\n                await message.reply(f"В данной беседе запрещено использовать любые игровые команды!

Выключить данную настройку можно в: «/settingsgame»")\n                return True\n            if len(arguments) < 1 and not getattr(message, "reply_message", None):\n                await message.reply("💸 Пример: /передать @yupikrussiaboss 100")\n                return\n\n            target = await extract_user_id(message)\n            if not target and arguments:\n                target = extract_user_id_from_text(arguments[0])\n\n            if not target or target == user_id:\n                await message.reply("💸 Пример: /передать @yupikrussiaboss 100")\n                return\n\n            try:\n                amount = int(arguments[-1])\n            except:\n                await message.reply("Укажи сумму числом")\n                return\n\n            balances = load_data(BALANCES_FILE)\n            sender = balances.get(str(user_id), get_balance(user_id))\n            recipient = balances.get(str(target), get_balance(target))\n\n            if sender["wallet"] < amount:\n                await message.reply("Недостаточно монет для перевода")\n                return\n\n            if amount < 1:\n                await message.reply("Укажи сумму числом!")\n                return\n\n            commission = int(amount * 0.05) if amount > 1000 else 0\n            net = amount - commission\n\n            sender["wallet"] -= amount\n            sender["sent_total"] += amount\n            recipient["wallet"] += net\n            recipient["received_total"] += net\n\n            balances[str(user_id)] = sender\n            balances[str(target)] = recipient\n            save_data(BALANCES_FILE, balances)\n            await log_economy(user_id=user_id, target_id=target, amount=amount, log=f"передал(-а) {amount}$ пользователю {target}")\n\n            try:\n                s_info = await bot.api.users.get(user_ids=user_id)\n                r_info = await bot.api.users.get(user_ids=target)\n                s_name = f"{s_info[0].first_name} {s_info[0].last_name}"\n                r_name = f"{r_info[0].first_name} {r_info[0].last_name}"\n            except:\n                s_name = str(user_id)\n                r_name = str(target)\n\n            if commission > 0:\n                await message.reply(\n                    f"💸 [id{user_id}|{s_name}] передал {format_number(net)}$ "\n                    f"[id{target}|{r_name}]
"\n                    f"💰 Комиссия: {format_number(commission)}$"\n                )\n            else:\n                await message.reply(\n                    f"💸 [id{user_id}|{s_name}] передал {format_number(amount)}$ "\n                    f"[id{target}|{r_name}]"\n                )\n            return\n\n        if command in ["положить"]:\n            if get_block_game(chat_id):\n                await message.reply(f"В данной беседе запрещено использовать любые игровые команды!

Выключить данную настройку можно в: «/settingsgame»")\n                return True\n            if len(arguments) < 1:\n                await message.reply("Укажи сумму числом!")\n                return\n\n            try:\n                amount = int(arguments[-1])\n            except:\n                await message.reply("Укажи сумму числом!")\n                return\n\n            balances = load_data(BALANCES_FILE)\n            bal = balances.get(str(user_id), get_balance(user_id))\n\n            if bal["wallet"] < amount:\n                await message.reply("Недостаточно средств на балансе")\n                return\n\n            if amount < 1:\n                await message.reply("Укажи сумму числом!")\n                return\n\n            bal["wallet"] -= amount\n            bal["bank"] += amount\n\n            balances[str(user_id)] = bal\n            save_data(BALANCES_FILE, balances)\n            await log_economy(user_id=user_id, target_id=None, amount=amount, log=f"положил(-а) {amount}$ в банк")\n\n            await message.reply(f"Вы положили {format_number(amount)}$ в банк.")\n            return\n\n        if command in ["снять"]:\n            if get_block_game(chat_id):\n                await message.reply(f"В данной беседе запрещено использовать любые игровые команды!

Выключить данную настройку можно в: «/settingsgame»")\n                return True\n            if len(arguments) < 1:\n                await message.reply("Укажи сумму числом!")\n                return\n\n            try:\n                amount = int(arguments[-1])\n            except:\n                await message.reply("Укажи сумму числом!")\n                return\n\n            balances = load_data(BALANCES_FILE)\n            bal = balances.get(str(user_id), get_balance(user_id))\n\n            commission = int(amount * 0.05) if amount > 1000 else 0\n            total = amount + commission\n\n            if bal["bank"] < total:\n                await message.reply(f"Недостаточно средств в банке (с учётом комиссии {format_number(total)}$)")\n                return\n\n            if amount < 1:\n                await message.reply("Укажи сумму числом!")\n                return\n\n            bal["bank"] -= total\n            bal["wallet"] += amount\n\n            balances[str(user_id)] = bal\n            save_data(BALANCES_FILE, balances)\n            await log_economy(user_id=user_id, target_id=None, amount=amount, log=f"снял(-а) {amount}$ с банка")\n\n            await message.reply(f"Вы сняли {format_number(amount)}$ с банка.
💸 Комиссия: ({format_number(commission)}$)")\n            return\n\n        if command in ["открытьдепозит"]:\n            if get_block_game(chat_id):\n                await message.reply(f"В данной беседе запрещено использовать любые игровые команды!

Выключить данную настройку можно в: «/settingsgame»")\n                return True\n            if len(arguments) < 2:\n                await message.reply("Доступные сроки: 4, 8 или 10 дней. Пример: /открытьдепозит 4 1000")\n                return\n\n            days, amount = None, None\n            percent_map = {4: 25, 8: 45, 10: 75}\n\n            for arg in arguments:\n                try:\n                    num = int(arg)\n                except:\n                    continue\n\n                if num in percent_map and days is None:\n                    days = num\n                elif amount is None:\n                    amount = num\n\n            if days is None or amount is None:\n                await message.reply("Аргументы должны быть числами! Пример: /открытьдепозит 4 1000")\n                return\n\n            balances = load_data(BALANCES_FILE)\n            bal = balances.get(str(user_id), get_balance(user_id))\n\n            vip_until = bal.get("vip_until")\n            if not vip_until or datetime.fromisoformat(vip_until) < datetime.now():\n                await message.reply("Для открытия депозита требуется VIP-статус!")\n                return\n\n            if bal.get("deposit_amount", 0) > 0:\n                await message.reply("У вас уже есть активный депозит. Дождитесь завершения.")\n                return\n\n            if bal["wallet"] < amount:\n                await message.reply("Недостаточно монет на балансе")\n                return\n\n            percent = percent_map[days]\n            end_time = datetime.now() + datetime.timedelta(days=days)\n\n            bal["wallet"] -= amount\n            bal["deposit_amount"] = amount\n            bal["deposit_until"] = end_time.isoformat()\n            bal["deposit_percent"] = percent\n            bal["deposit_days"] = days\n\n            balances[str(user_id)] = bal\n            save_data(BALANCES_FILE, balances)\n            await log_economy(user_id=user_id, target_id=None, amount=amount, log=f"открыл(-а) депозит на {amount}$ на {days}д.")\n\n            await message.reply(f"Депозит {format_number(amount)}$ на {days} дней под {percent}% успешно открыт!")\n            return\n\n        if command in ["закрытьдепозит"]:\n            if get_block_game(chat_id):\n                await message.reply(f"В данной беседе запрещено использовать любые игровые команды!

Выключить данную настройку можно в: «/settingsgame»")\n                return True\n            balances = load_data(BALANCES_FILE)\n            bal = balances.get(str(user_id), get_balance(user_id))\n\n            deposit_amount = bal.get("deposit_amount", 0)\n            deposit_until = bal.get("deposit_until")\n            deposit_percent = bal.get("deposit_percent", 0)\n\n            if deposit_amount == 0 or not deposit_until:\n                await message.reply("Нет завершённых депозитов для вывода.")\n                return\n\n            try:\n                end_time = datetime.fromisoformat(deposit_until)\n            except:\n                await message.reply("Нет завершённых депозитов для вывода.")\n                return\n\n            now = datetime.now()\n            if now < end_time:\n                await message.reply("Депозит ещё не завершён.")\n                return\n\n            reward = int(deposit_amount + (deposit_amount * deposit_percent / 100))\n            bal["wallet"] += reward\n\n            bal["deposit_amount"] = 0\n            bal["deposit_until"] = None\n            bal["deposit_percent"] = 0\n            bal["deposit_days"] = 0\n\n            balances[str(user_id)] = bal\n            save_data(BALANCES_FILE, balances)\n            await log_economy(user_id=user_id, target_id=None, amount=reward, log=f"закрыл(-а) депозит на {reward}$")\n\n            await message.reply(f"Депозит закрыт, вы получили {format_number(reward)}$")\n            return\n\n        if command in ["приз"]:\n            if get_block_game(chat_id):\n                await message.reply(f"В данной беседе запрещено использовать любые игровые команды!

Выключить данную настройку можно в: «/settingsgame»")\n                return True\n            uid = str(user_id)\n            bal = get_balance(user_id)\n            now = datetime.now()\n            balances = load_data(BALANCES_FILE)\n\n            is_vip = bal.get("vip_until") and datetime.fromisoformat(bal["vip_until"]) > now\n            cooldown = timedelta(hours=2) if is_vip else timedelta(hours=5)\n            reward_min, reward_max = (50000, 60000) if is_vip else (20000, 30000)\n\n            last = prizes.get(uid)\n            if last:\n                try:\n                    last_time = datetime.fromisoformat(last)\n                    if now < last_time + cooldown:\n                        delta = (last_time + cooldown) - now\n                        h, m = divmod(delta.seconds // 60, 60)\n                        await message.reply(f"⏳ Получить монеты можно через {h}ч. {m}м.")\n                        return\n                except:\n                    pass\n\n            reward = random.randint(reward_min, reward_max)\n\n            try:\n                with open("x3prize.json", "r", encoding="utf-8") as f:\n                    x3_data = json.load(f)\n                if x3_data.get("X3Activated", False):\n                    reward *= 3\n            except FileNotFoundError:\n                pass\n\n            extra_bonus = await get_prize_bonus_percent(user_id)\n            if extra_bonus > 0:\n                reward = int(reward * (1 + (extra_bonus / 100)))\n\n            prizes[uid] = now.isoformat()\n            save_data(PRIZES_FILE, prizes)\n            balances = load_data(BALANCES_FILE)\n            bal = balances.get(str(user_id), get_balance(user_id))\n            bal["wallet"] += reward\n            balances[str(user_id)] = bal\n            await log_economy(user_id=user_id, target_id=None, amount=reward, log=f"получил(-а) приз на {reward}$")\n            save_data(BALANCES_FILE, balances)\n\n            await message.reply(f"🎉 Ты получил приз {reward}!")\n            return            \n\n        if command in ['защита', 'protection']:\n            if await get_role(user_id, chat_id) < 7:\n                await message.reply("Недостаточно прав для использования команды!", disable_mentions=1)\n                return True\n\n            sql.execute("SELECT * FROM protection WHERE chat_id = ?", (chat_id,))\n            row = sql.fetchone()\n            if row is None:\n                sql.execute("INSERT INTO protection (chat_id, mode) VALUES (?, ?)", (chat_id, 1))\n                database.commit()\n                await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), включил(-а) систему защиты от сторонних сообществ!", disable_mentions=1)\n            else:\n                new_mode = 0 if row[1] == 1 else 1\n                sql.execute("UPDATE protection SET mode = ? WHERE chat_id = ?", (new_mode, chat_id))\n                database.commit()\n                if new_mode == 0:\n                    await message.replyLocalizedMessage('command_protection_off')\n                else:\n                    await message.replyLocalizedMessage('commabd_protection_on')\n\n            return True            \n            \n        if command in ['settingsmute', 'настройкимута']:\n            if await get_role(user_id, chat_id) < 7:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            sql.execute("SELECT * FROM mutesettings WHERE chat_id = ?", (chat_id,))\n            row = sql.fetchone()\n            if row is None:\n                sql.execute("INSERT INTO mutesettings (chat_id, mode) VALUES (?, ?)", (chat_id, 1))\n                database.commit()\n                await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), включил(-а) систему выдачи варнов в муте!", disable_mentions=1)\n            else:\n                new_mode = 0 if row[1] == 1 else 1\n                sql.execute("UPDATE mutesettings SET mode = ? WHERE chat_id = ?", (new_mode, chat_id))\n                database.commit()\n                if new_mode == 0:\n                    await message.replyLocalizedMessage('command_settingsmute_off')\n                else:\n                    await message.replyLocalizedMessage('command_settingsmute_on')\n\n            return True            \n\n        if command in ["дуэль", "duel"]:\n            if get_block_game(chat_id):\n                await message.reply(f"В данной беседе запрещено использовать любые игровые команды!

Выключить данную настройку можно в: «/settingsgame»")\n                return True\n            cooldown = 20\n            now = datetime.now()\n\n            balances = load_data(BALANCES_FILE)\n            last_duel_time = duels.get(f"user_{user_id}", {}).get("last_time")\n            if last_duel_time:\n                last_dt = datetime.fromisoformat(last_duel_time)\n                delta = (now - last_dt).total_seconds()\n                if delta < cooldown:\n                    remain = int(cooldown - delta)\n                    await message.reply(f"⏳ Подождите ещё {remain}с для создания новой дуэли!")\n                    return\n\n            if len(arguments) < 1:\n                await message.reply("⚔️ Укажи ставку: /дуэль <сумма> (минимум 20)")\n                return\n            try:\n                stake = int(arguments[-1])\n            except:\n                await message.reply("Ставка должна быть числом")\n                return\n            if stake < 20:\n                await message.reply("Минимальная ставка — 20$")\n                return\n\n            bal = balances.get(str(user_id), get_balance(user_id))\n            if bal["wallet"] < stake:\n                await message.reply("У тебя недостаточно монет для ставки")\n                return\n\n            balances[str(user_id)] = bal\n            save_data(BALANCES_FILE, balances)\n\n            peer_id = str(message.peer_id)\n\n            duels[peer_id] = {\n                "author": user_id,\n                "stake": stake,\n                "time": now.isoformat()\n            }\n            duels[f"user_{user_id}"] = {"last_time": now.isoformat()}\n            save_data(DUELS_FILE, duels)\n\n            kb = Keyboard(inline=True)\n            kb.add(\n                Callback("🎮 Вступить в дуэль", {"command": "join_duel", "peer": peer_id}),\n                color=KeyboardButtonColor.POSITIVE\n            )\n\n            msg = await message.reply(\n                f"⚔️ Дуэль на {format_number(stake)}$ создана!
Нажми на кнопку чтобы вступить.",\n                keyboard=kb\n            )\n            duels[peer_id]["message_id"] = getattr(msg, "conversation_message_id", None) or getattr(msg, "id", None)\n            save_data(DUELS_FILE, duels)\n            await log_economy(user_id=user_id, target_id=None, amount=stake, log=f"создал(-а) дуэль на {stake}$")\n            return\n\n        if command in ["топ"]:\n            if get_block_game(chat_id):\n                await message.reply(f"В данной беседе запрещено использовать любые игровые команды!

Выключить данную настройку можно в: «/settingsgame»")\n                return True\n            balances = load_data(BALANCES_FILE)\n\n            top_users = sorted(\n                ((uid, bal) for uid, bal in balances.items() if bal.get("wallet", 0) > 0),\n                key=lambda x: x[1]["wallet"],\n                reverse=True\n            )[:10]\n\n            if not top_users:\n                await message.reply("Топ не сформирован.")\n                return\n\n            lines = ["💰 Самые богатые пользователи:

"]\n            for i, (uid, bal) in enumerate(top_users, start=1):\n                try:\n                    info = await bot.api.users.get(user_ids=uid)\n                    name = f"{info[0].first_name} {info[0].last_name}"\n                except:\n                    name = f"id{uid}"\n\n                total = bal.get("wallet", 0)\n                bank_balance = bal.get("bank", 0)\n\n                vip_until = bal.get("vip_until")\n                vip_status = "VIP" if vip_until and datetime.fromisoformat(vip_until) > datetime.now() else "Отсутствует"\n\n                prefix = "👑" if i == 1 else "🔱" if i <= 10 else ""\n\n                lines.append(\n                    f"Топ: {i} {prefix}: ⭐ Статус: {vip_status} "\n                    f"[id{uid}|{name}] | {format_number(total)}$

 "\n                    f"🏛 Счет в банке: {format_number(bank_balance)}$
 "\n                )\n\n            await message.reply("
".join(lines))\n            return\n\n        if command in ["благо"]:\n            if get_block_game(chat_id):\n                await message.reply(f"В данной беседе запрещено использовать любые игровые команды!

Выключить данную настройку можно в: «/settingsgame»")\n                return True\n            if len(arguments) < 1:\n                await message.reply("💰 Укажи сумму монет для блага, например: благо 10")\n                return\n\n            try:\n                amount = int(arguments[-1])\n            except ValueError:\n                await message.reply("💰 Сумма должна быть числом, например: благо 10")\n                return\n\n            balances = load_data(BALANCES_FILE)\n            bal = balances.get(str(user_id), get_balance(user_id))\n\n            if bal["wallet"] < amount:\n                await message.reply("Недостаточно монет для блага!")\n                return\n\n            if amount < 1:\n                await message.reply("Укажи сумму числом!")\n                return\n\n            bal["wallet"] -= amount\n            balances[str(user_id)] = bal\n            save_data(BALANCES_FILE, balances)\n\n            donates[user_id] = donates.get(user_id, 0) + amount\n            save_data(DONATES_FILE, donates)\n            await log_economy(user_id=user_id, target_id=None, amount=amount, log=f"благотворил(-а) {amount}$ в благотворительность")\n\n            try:\n                info = await bot.api.users.get(user_ids=user_id)\n                name = f"{info[0].first_name} {info[0].last_name}"\n            except:\n                name = str(user_id)\n\n            await message.reply(f"👍 [id{user_id}|{name}] внес {format_number(amount)}$ в благо!")\n            return\n\n        if command in ["топблаго"]:\n            if get_block_game(chat_id):\n                await message.reply(f"В данной беседе запрещено использовать любые игровые команды!

Выключить данную настройку можно в: «/settingsgame»")\n                return True\n            top_donors = sorted(donates.items(), key=lambda x: x[1], reverse=True)[:10]\n            if not top_donors:\n                await message.reply("Список благотворителей не сформирован!")\n                return\n            lines = ["🏆 Топ пользователей по внесенным монетам в благотворительность:"]\n            for i, (uid, amount) in enumerate(top_donors, start=1):\n                try:\n                    info = await bot.api.users.get(user_ids=uid)\n                    name = f"{info[0].first_name} {info[0].last_name}"\n                except:\n                    name = f"id{uid}"\n                lines.append(f"{i}. [id{uid}|{name}] — {format_number(amount)} монет")\n            await message.reply("
".join(lines))\n            return\n\n        if command in ["buyvip", "купитьвипку"]:\n            if get_block_game(chat_id):\n                await message.reply(f"В данной беседе запрещено использовать любые игровые команды!

Выключить данную настройку можно в: «/settingsgame»")\n                return True\n            balances = load_data(BALANCES_FILE)\n            bal = balances.get(str(user_id), get_balance(user_id))\n            vip_until = bal.get("vip_until")\n\n            if vip_until and datetime.fromisoformat(vip_until) > datetime.now():\n                await message.reply("У вас уже есть активный VIP статус!")\n                return\n\n            cost = 150_000\n            if bal["wallet"] < cost:\n                await message.reply("Недостаточно монет для покупки VIP статуса! Нужно 150.000$.")\n                return\n\n            bal["wallet"] -= cost\n            bal["vip_until"] = (datetime.now() + timedelta(days=30)).isoformat()\n\n            balances[str(user_id)] = bal\n            save_data(BALANCES_FILE, balances)\n            await log_economy(user_id=user_id, target_id=None, amount=None, log=f"купил(-а) вип-статус")\n\n            await message.reply("🎉 Поздравляем! Вы приобрели VIP статус на 30 дней и теперь получаете увеличенный приз!")\n            return\n\n        if command in ["промо"]:\n            if get_block_game(chat_id):\n                await message.reply(f"В данной беседе запрещено использовать любые игровые команды!

Выключить данную настройку можно в: «/settingsgame»")\n                return True\n            balances = load_data(BALANCES_FILE)\n            bal = balances.get(str(user_id), get_balance(user_id))\n            uid = str(user_id)\n\n            if uid in promo:\n                await message.reply("🎁 Вы уже получали бонус за подписку.")\n                return\n\n            reward = 70_000\n            bal["wallet"] += reward\n            balances[uid] = bal\n            save_data(BALANCES_FILE, balances)\n\n            promo[uid] = True\n            save_data(PROMO_FILE, promo)\n            await log_economy(user_id=user_id, target_id=None, amount=reward, log=f"получил(-а) бонус за промокод {reward}$")\n\n            await message.reply(f"🎁 Вы получили {format_number(reward)}$ за активированный промокод!")\n            return          \n\n        # ---------------- УДАЛИТЬ ДУЭЛЬ ----------------\n        if command in ["удалитьдуэль", "removeduel"]:\n            role = await get_role(user_id, chat_id)\n            if role < 11:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return\n\n            peer_id = str(message.peer_id)\n            if peer_id not in duels:\n                await message.reply("В чате котором вы находитесь отсутствуют активные дуэли.")\n                return\n\n            duels.pop(peer_id, None)\n            save_data(DUELS_FILE, duels)\n\n            try:\n                info = await bot.api.users.get(user_ids=user_id)\n                name = f"{info[0].first_name} {info[0].last_name}"\n            except:\n                name = str(user_id)\n\n            await message.reply(f"⚔️ [id{user_id}|{name}] удалил активную дуэль в данном чате.")\n            return         \n\n        if command in ['warnlist', 'warns', 'wlist', 'варны', 'варнлист']:\n            if await get_role(user_id, chat_id) < 1:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            warns = await warnlist(chat_id)\n            if warns == False: warns_string = "Пользователей с предупреждениями нет!"\n            else: warns_string = '\n'.join(warns)\n\n            await message.replyLocalizedMessage('command_warnlist', {\n                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',\n                        'warns': warns,\n                        'info': warns_string\n                    })\n\n        if command in ['staff', 'стафф']:\n            if await get_role(user_id, chat_id) < 1:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            staff_mass = await staff(chat_id)\n\n            if staff_mass is None:\n                staff_str = "В данной беседе нет пользователей с ролями!"\n                await message.reply(staff_str, disable_mentions=1)\n                return True\n            else:\n                moders = '\n'.join(staff_mass['moders']) if staff_mass['moders'] else "Отсутствуют"\n                stmoders = '\n'.join(staff_mass['stmoders']) if staff_mass['stmoders'] else "Отсутствуют"\n                admins = '\n'.join(staff_mass['admins']) if staff_mass['admins'] else "Отсутствуют"\n                stadmins = '\n'.join(staff_mass['stadmins']) if staff_mass['stadmins'] else "Отсутствуют"\n                zsa = '\n'.join(staff_mass['zamspecadm']) if staff_mass['zamspecadm'] else "Отсутствуют"\n                sa = '\n'.join(staff_mass['specadm']) if staff_mass['specadm'] else "Отсутствуют"\n\n                x = await bot.api.messages.get_conversations_by_id(\n                    peer_ids=peer_id,\n                    extended=1,\n                    fields='chat_settings',\n                    group_id=message.group_id\n                )\n                x = json.loads(x.json())\n                for i in x['items']:\n                    owner = int(i["chat_settings"]["owner_id"])\n\n                if owner < 1:\n                    owner = f"[club{abs(owner)}|BANANA MANAGER]"\n                else:\n                    owner = f"@id{owner} (BANANA MANAGER)"\n\n                await message.replyLocalizedMessage('command_staff', {\n                        'owner': owner,\n                        'sa': sa,\n                        'zsa': zsa,\n                        'sadm': stadmins,\n                        'adm': admins,\n                        'smod': stmoders,\n                        'moders': moders\n                    })\n                await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) список администрации в чате")            \n                return True              \n                \n        if command in ['gstaff', 'гстафф']:\n            if await get_role(user_id, chat_id) < 11:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            staff_mass = await staff(chat_id)\n\n            if staff_mass is None:\n                staff_str = "В данной беседе нет пользователей с глобальными ролями!"\n                await message.reply(staff_str, disable_mentions=1)\n                return True\n            else:\n                moders = '\n'.join(staff_mass['moders']) if staff_mass['moders'] else "Отсутствуют"\n                stmoders = '\n'.join(staff_mass['stmoders']) if staff_mass['stmoders'] else "Отсутствуют"\n                admins = '\n'.join(staff_mass['admins']) if staff_mass['admins'] else "Отсутствуют"\n                stadmins = '\n'.join(staff_mass['stadmins']) if staff_mass['stadmins'] else "Отсутствуют"\n                zsa = '\n'.join(staff_mass['zamspecadm']) if staff_mass['zamspecadm'] else "Отсутствуют"\n                sa = '\n'.join(staff_mass['specadm']) if staff_mass['specadm'] else "Отсутствуют"\n                zamruk = '\n'.join(staff_mass['zamruk']) if staff_mass['zamruk'] else "Отсутствуют"\n                oszamruk = '\n'.join(staff_mass['oszamruk']) if staff_mass['oszamruk'] else "Отсутствуют"\n                ruk = '\n'.join(staff_mass['ruk']) if staff_mass['ruk'] else "Отсутствуют"\n                dev = '\n'.join(staff_mass['dev']) if staff_mass['dev'] else "Отсутствуют"\n\n                x = await bot.api.messages.get_conversations_by_id(\n                    peer_ids=peer_id,\n                    extended=1,\n                    fields='chat_settings',\n                    group_id=message.group_id\n                )\n                x = json.loads(x.json())\n                for i in x['items']:\n                    owner = int(i["chat_settings"]["owner_id"])\n\n                if owner < 1:\n                    owner = f"[club{abs(owner)}|BANANA MANAGER]"\n                else:\n                    owner = f"@id{owner} (BANANA MANAGER)"\n\n                await message.reply(\n                    f"💻 | Разработчики бота:
{dev}

"\n                    f"⭐️ | Директор бота:
{ruk}

"\n                    f"💫 | Осн. заместители директора:
{oszamruk}

"\n                    f"✨ | Заместители директора:
{zamruk}",\n                    disable_mentions=1\n                )\n                await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) глобальный список администрации в чате")            \n                return True                \n                \n        if command in ['testerslist', 'списоктестров', 'тестеры', 'testers']:\n            if chat_id != tchat:\n                await message.reply("Данная команда доступна только в официальном тестовом чате бота!", disable_mentions=1)\n                return True\n\n            if await get_role(user_id, chat_id) < 10:\n                await message.reply("Вы не являетесь тестировщиком бота!", disable_mentions=1)\n                return True\n\n            staff_mass = await staff(chat_id)\n\n            if staff_mass is None:\n                staff_str = "В данной беседе нет пользователей с глобальными ролями!"\n                await message.reply(staff_str, disable_mentions=1)\n                return True\n            else:\n                moders = '\n'.join(staff_mass['moders']) if staff_mass['moders'] else "Отсутствуют"\n                stmoders = '\n'.join(staff_mass['stmoders']) if staff_mass['stmoders'] else "Отсутствуют"\n                admins = '\n'.join(staff_mass['admins']) if staff_mass['admins'] else "Отсутствуют"\n                stadmins = '\n'.join(staff_mass['stadmins']) if staff_mass['stadmins'] else "Отсутствуют"\n                zsa = '\n'.join(staff_mass['zamspecadm']) if staff_mass['zamspecadm'] else "Отсутствуют"\n                sa = '\n'.join(staff_mass['specadm']) if staff_mass['specadm'] else "Отсутствуют"\n                zamruk = '\n'.join(staff_mass['zamruk']) if staff_mass['zamruk'] else "Отсутствуют"\n                oszamruk = '\n'.join(staff_mass['oszamruk']) if staff_mass['oszamruk'] else "Отсутствуют"\n                ruk = '\n'.join(staff_mass['ruk']) if staff_mass['ruk'] else "Отсутствуют"\n                dev = '\n'.join(staff_mass['dev']) if staff_mass['dev'] else "Отсутствуют"\n                testers = '\n'.join(staff_mass['testers']) if staff_mass['testers'] else "Отсутствуют"\n                zamglt = '\n'.join(staff_mass['zamglt']) if staff_mass['zamglt'] else "Отсутствуют"\n                glt = '\n'.join(staff_mass['glt']) if staff_mass['glt'] else "Отсутствуют"\n\n                x = await bot.api.messages.get_conversations_by_id(\n                    peer_ids=peer_id,\n                    extended=1,\n                    fields='chat_settings',\n                    group_id=message.group_id\n                )\n                x = json.loads(x.json())\n                for i in x['items']:\n                    owner = int(i["chat_settings"]["owner_id"])\n\n                if owner < 1:\n                    owner = f"[club{abs(owner)}|BANANA MANAGER]"\n                else:\n                    owner = f"@id{owner} (BANANA MANAGER)"\n\n                await message.reply(\n                    f"Владелец беседы — {owner}

"\n                    f"Главные тестировщики бота:
{glt}

"\n                    f"Заместители главных тестировщиков:
{zamglt}

"\n                    f"Тестировщики бота:
{testers}",\n                    disable_mentions=1\n                )\n                await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) глобальный список администрации в чате")            \n                return True                                \n\n        if command in ['mute', 'мут', 'мьют', 'муте', 'addmute']:\n            if await get_role(user_id, chat_id) < 1:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            user = int\n            arg = 0\n            if message.reply_message:\n                user = message.reply_message.from_id\n                arg = 2\n            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:\n                user = message.fwd_messages[0].from_id\n                arg = 2\n            elif len(arguments) >= 2 and await getID(arguments[1]):\n                user = await getID(arguments[1])\n                arg = 3\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            if len(arguments) < 4 and arg == 3:\n                await message.replyLocalizedMessage('command_mute_params')\n                return True\n\n            if len(arguments) < 3 and arg == 2:\n                await message.replyLocalizedMessage('command_mute_params')\n                return True\n\n            await checkMute(chat_id, user)\n\n            if await equals_roles(user_id, user, chat_id, message) < 2:\n                await message.replyLocalizedMessage('command_mute_preminisionss')\n                return True\n\n            if await get_mute(user, chat_id):\n                await message.replyLocalizedMessage('command_mute_alyready')\n                return True\n\n            reason = await get_string(arguments, arg)\n            if not reason:\n                await message.replyLocalizedMessage('command_mute_not_reason')\n                return True\n\n            if arg == 3: mute_time = arguments[2]\n            else: mute_time = arguments[1]\n            try: mute_time = int(mute_time)\n            except:\n                await message.replyLocalizedMessage('command_mute_params')\n                return True\n\n            if mute_time < 1 or mute_time > 1000:\n                await message.replyLocalizedMessage('command_mute_time')\n                return True\n\n            await add_mute(user, chat_id, user_id, reason, mute_time)\n            await add_mutelog(chat_id, user, user_id, reason, mute_time, "выдан")\n\n            do_time = datetime.now() + timedelta(minutes=mute_time)\n            mute_time = str(do_time).split('.')[0]\n\n            keyboard = (\n                Keyboard(inline=True)\n                .add(Callback("Снять мут", {"command": "unmute", "user": user, "chatId": chat_id}), color=KeyboardButtonColor.POSITIVE)\n                .add(Callback("Очистить", {"command": "clear", "chatId": chat_id, "user": user}), color=KeyboardButtonColor.NEGATIVE)\n            )\n\n            await message.replyLocalizedMessage('command_mute', {\n                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',\n                        'target': f'@id{user} ({await get_user_name(user, chat_id)})',\n                        'reason': reason,\n                        'time_mute': mute_time\n                    }, keyboard=keyboard)\n            await chats_log(user_id=user_id, target_id=user, role=None, log=f"замутил(-а) @id{user} (пользователю). Мут выдан до: {mute_time}")            \n            await add_punishment(chat_id, user_id)\n            if await get_sliv(user_id, chat_id) and await get_role(user_id, chat_id) < 5:\n                await roleG(user_id, chat_id, 0)\n                await message.reply(\n                    f"❗️ Уровень прав @id{user_id} (пользователя) был снят из-за подозрений в сливе беседы

{await staff_zov(chat_id)}")\n\n        if command in ['unmute', 'снятьмут', 'анмут', 'анмьют', 'унмут']:\n            if await get_role(user_id, chat_id) < 1:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            user = int\n            if message.reply_message:user = message.reply_message.from_id\n            elif len(arguments) >= 2 and await getID(arguments[1]):user = await getID(arguments[1])\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            await checkMute(chat_id, user)\n\n            if await equals_roles(user_id, user, chat_id, message) < 2:\n                await message.replyLocalizedMessage('command_unmute_preminisionss')\n                return True\n\n            if not await get_mute(user, chat_id):\n                await message.replyLocalizedMessage('command_unmute_no')\n                return True\n\n            mute_info = await get_mute(user, chat_id)\n            await unmute(user, chat_id)\n            if mute_info:\n                await add_mutelog(chat_id, user, user_id, mute_info['reason'], mute_info['time'], "снят")\n\n            await message.replyLocalizedMessage('command_unmute', {\n                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',\n                        'target': f'@id{user} ({await get_user_name(user, chat_id)})'                       \n                    })\n            await chats_log(user_id=user_id, target_id=user, role=None, log=f"снял(-а) мут @id{user} (пользователю)")           \n\n        if command in ['getmute', 'gmute', 'гмут', 'гетмут', 'чекмут']:\n            if await get_role(user_id, chat_id) < 1:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            user = int\n            if message.reply_message:user = message.reply_message.from_id\n            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:\n                user = message.fwd_messages[0].from_id\n            elif len(arguments) >= 2 and await getID(arguments[1]):user = await getID(arguments[1])\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            await checkMute(chat_id, user)\n\n            mute_string = str\n            gmute = await get_mute(user, chat_id)\n            if not gmute: mute_string = "У пользователя нет мута!"\n            else:\n                do_time = datetime.fromisoformat(gmute['date']) + timedelta(minutes=gmute['time'])\n                mute_time = str(do_time).split('.')[0]\n\n                try:\n                    int(gmute['moder'])\n                    mute_string = f"@id{gmute['moder']} (Модератор) | {gmute['reason']} | {gmute['date']} | До: {mute_time}"\n                except: mute_string = f"Бот | {gmute['reason']} | {gmute['date']} | До: {mute_time}"\n\n            await message.replyLocalizedMessage('command_getmute', {\n                        'target': f'@id{user} ({await get_user_name(user, chat_id)})',\n                        'info': mute_string\n                    })\n            await chats_log(user_id=user_id, target_id=user, role=None, log=f"посмотрел(-а) историю мутов @id{user} (пользователя)")            \n\n        if command in ['mutelist', 'mutes', 'муты', 'мутлист']:\n            if await get_role(user_id, chat_id) < 1:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            mutes = await mutelist(chat_id)\n            if not mutes: mutes_str = ""\n            else:\n                mutes_str = '\n'.join(mutes)\n\n            await message.replyLocalizedMessage('command_mutelist', {\n                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',\n                        'info': mutes_str\n                    })            \n            await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) список замученных в чате")\n\n        if command in ['mutelogs', 'логимутов']:\n            await mutelogs_command(message, arguments, user_id, chat_id, get_role, message.replyLocalizedMessage, getID, sql, datetime, timedelta, chats_log, get_user_name)\n\n        if command in ['clear', 'чистка', 'очистить', 'очистка']:\n            if await get_role(user_id, chat_id) < 1:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            user = int            \n            cmid = message.reply_message.conversation_message_id if message.reply_message else None\n            user = message.reply_message.from_id if message.reply_message else None\n            if message.reply_message: user = message.reply_message.from_id\n            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:\n                user = message.fwd_messages[0].from_id\n            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            if await equals_roles(user_id, user, chat_id, message) < 2:\n                await message.replyLocalizedMessage('command_clear_preminisionss')\n                return True\n\n            await message.replyLocalizedMessage('command_clear', {\n                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',\n                        'target': f'@id{user} ({await get_user_name(user, chat_id)})'\n                    })\n            \n            try: await bot.api.messages.delete(group_id=message.group_id, peer_id=peer_id, delete_for_all=True, cmids=cmid)\n            except: pass\n\n            try: await bot.api.messages.delete(group_id=message.group_id, peer_id=peer_id, delete_for_all=True, cmids=message.conversation_message_id)\n            except: pass            \n            \n        if command in ['deleteall', 'удалитьвсе']:\n            if await get_role(user_id, chat_id) < 5:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            # Определяем пользователя (аналогично clear)\n            user = int\n            if message.reply_message:\n                user = message.reply_message.from_id\n            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:\n                user = message.fwd_messages[0].from_id\n            elif len(arguments) >= 2 and await getID(arguments[1]):\n                user = await getID(arguments[1])\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            # Проверка ролей (чтоб низший не мог трогать высшего)\n            if await equals_roles(user_id, user, chat_id, message) < 2:\n                await message.replyLocalizedMessage('command_deleteall_preminisionss')\n                return True\n\n            # Получаем последние 200 сообщений из чата\n            history = await bot.api.messages.get_history(\n                peer_id=2000000000 + chat_id,\n                count=200\n            )\n\n            # Фильтруем по автору\n            cmids = [msg.conversation_message_id for msg in history.items if msg.from_id == user]\n\n            if not cmids:\n                await message.replyLocalizedMessage('command_deleteall_no_messages')\n                return True\n\n            # Удаляем все найденные\n            await bot.api.messages.delete(\n                peer_id=2000000000 + chat_id,\n                cmids=cmids,\n                delete_for_all=True\n            )\n\n            await message.replyLocalizedMessage('command_deleteall', {\n                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',\n                        'target': f'@id{user} ({await get_user_name(user, chat_id)})'\n                    })            \n            await chats_log(user_id=user_id, target_id=user, role=None, log=f"удалил(-а) последнее 200 сообщений @id{user} (пользователя)")            \n            return True\n\n        if command in ['mclear', 'мклиар']:\n            if await get_role(user_id, chat_id) < 4:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            # Определяем пользователя (аналогично clear)\n            user = int\n            if message.reply_message:\n                user = message.reply_message.from_id\n            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:\n                user = message.fwd_messages[0].from_id\n            elif len(arguments) >= 2 and await getID(arguments[1]):\n                user = await getID(arguments[1])\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            # Проверка ролей (чтоб низший не мог трогать высшего)\n            if await equals_roles(user_id, user, chat_id, message) < 2:\n                await message.reply("Вы не можете удалять сообщения этого пользователя!", disable_mentions=1)\n                return True\n\n            # Получаем последние 500 сообщений из чата\n            history = await bot.api.messages.get_history(\n                peer_id=2000000000 + chat_id,\n                count=500\n            )\n\n            # Фильтруем по автору\n            cmids = [msg.conversation_message_id for msg in history.items if msg.from_id == user]\n\n            if not cmids:\n                await message.reply("У пользователя нет сообщений в последних 500.", disable_mentions=1)\n                return True\n\n            # Удаляем все найденные\n            await bot.api.messages.delete(\n                peer_id=2000000000 + chat_id,\n                cmids=cmids,\n                delete_for_all=True\n            )\n\n            await message.reply(f"Удалено {len(cmids)} сообщений @id{user} (пользователя)", disable_mentions=1)\n            await chats_log(user_id=user_id, target_id=user, role=None, log=f"удалил(-а) последнее 500 сообщений @id{user} (пользователя)")            \n            return True            \n\n        if command in ['alt', 'альт', 'альтернативные']:\n            if await get_role(user_id, chat_id) < 1:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            commands_levels = {\n                1: [\n                    '\nКоманды модераторов:',\n                    '/setnick — snick, nick, addnick, ник, сетник, аддник',\n                    '/removenick —  removenick, clearnick, cnick, рник, удалитьник, снятьник',\n                    '/getnick — gnick, гник, гетник',\n                    '/getacc — acc, гетакк, аккаунт, account',\n                    '/nlist — ники, всеники, nlist, nickslist, nicklist, nicks',\n                    '/nonick — nonicks, nonicklist, nolist, nnlist, безников, ноникс',\n                    '/kick — кик, исключить',\n                    '/warn — пред, варн, pred, предупреждение',\n                    '/unwarn — унварн, анварн, снятьпред, минуспред',\n                    '/getwarn — gwarn, getwarns, гетварн, гварн',\n                    '/warnhistory — historywarns, whistory, историяварнов, историяпредов',\n                    '/warnlist — warns, wlist, варны, варнлист',\n                    '/staff — стафф',\n                    '/mute — мут, мьют, муте, addmute',\n                    '/unmute — снятьмут, анмут, унмут, снятьмут',\n                    '/alt — альт, альтернативные',\n                    '/getmute -- gmute, гмут, гетмут, чекмут',\n                    '/mutelist -- mutes, муты, мутлист',\n                    '/clear -- чистка, очистить, очистка',\n                    '/getban -- чекбан, гетбан, checkban',\n                    '/delete -- удалить',\n                    '/chatid -- чатайди, айдичата'\n                ],\n                2: [\n                    '\nКоманды старших модераторов:',\n                    '/ban — бан, блокировка',\n                    '/unban -- унбан, снятьбан',\n                    '/addmoder -- moder',\n                    '/removerole -- rrole, снятьроль',\n                    '/zov - зов, вызов',\n                    '/online - ozov, озов',\n                    '/onlinelist - olist, олист',\n                    '/banlist - bans, банлист, баны',\n                    '/inactive - ilist, inactive'\n                ],\n                3: [\n                    '\nКоманды администраторов:',\n                    '/quiet -- silence, тишина',\n                    '/skick -- скик, снят',\n                    '/sban -- сбан',\n                    '/sunban — сунбан, санбан',\n                    '/addsenmoder — senmoder',\n                    '/rnickall -- allrnick, arnick, mrnick',\n                    '/sremovenick -- srnick',\n                    '/szov -- serverzov, сзов',\n                    '/srole -- prole, pullrole'\n                ],\n                4: [\n                    '\nКоманды старших администраторов:',\n                    '/addadmin -- admin',\n                    '/serverinfo -- серверинфо',\n                    '/filter -- none',\n                    '/sremoverole -- srrole',\n                    '/ssetnick -- ssnick, сник',\n                    '/bug -- баг',\n                    '/report -- репорт, реп, rep, жалоба'\n                ],\n                5: [\n                    '\nКоманды зам. спец администраторов:',\n                    '/addsenadmin -- senadm, addsenadm, senadmin',\n                    '/sync -- синхронизация, сунс, синхронка',\n                    '/pin -- закрепить, пин',\n                    '/unpin -- открепить, унпин',\n                    '/deleteall -- удалитьвсе'\n                    '/gsinfo -- none',\n                    '/gsrnick -- none',\n                    '/gssnick -- none',\n                    '/gskick -- none',\n                    '/gsban -- none',\n                    '/gsunban -- none'\n                ],\n                6: [\n                    '\nКоманды спец. администраторов:',\n                    '/addzsa -- zsa, зса',\n                    '/server -- сервер',\n                    '/settings -- настройки',\n                    '/clearwarn -- none',\n                    '/title -- none',\n                    '/antisliv -- антислив'\n                ],\n                7: [\n                    '\nСписок команд владельца беседы',\n                    '/addsa -- sa, са, spec, specadm',\n                    '/antiflood -- af',\n                    '/welcometext -- welcome, wtext',\n                    '/invite -- none',\n                    '/leave -- none',\n                    '/server -- сервер',\n                    '/editowner -- owner',\n                    '/защита -- protection',\n                    '/settingsmute -- настройкимута',\n                    '/setinfo -- установитьинфо',\n                    '/setrules -- установитьправила',\n                    '/type -- тип',\n                    '/gsync -- привязка',\n                    '/gunsync -- удалитьпривязку',\n                    '/masskick - mkick',\n                    '/amnesty -- амнистия',\n                    '/settingsgame -- настройкиигр',\n                    '/settingsphoto -- настройкифото'\n                ]\n            }\n\n            user_role = await get_role(user_id, chat_id)\n\n            commands = []\n            for i in commands_levels.keys():\n                if i <= user_role:\n                    for b in commands_levels[i]:\n                        commands.append(b)\n\n            level_commands = '\n'.join(commands)\n\n            await message.reply(f"Альтернативные команды

{level_commands}", disable_mentions=1)\n            await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) список альтернативных команд")            \n\n        if command in ['pin', 'закрепить', 'пин']:\n            if await get_role(user_id, chat_id) < 5:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            peer_id = chat_id + 2000000000\n\n            if not message.reply_message:\n                await message.replyLocalizedMessage('command_pin_replay')\n                return True\n\n            try:\n                await bot.api.messages.pin(\n                    peer_id=peer_id,\n                    cmid=message.reply_message.conversation_message_id\n                )\n                await message.replyLocalizedMessage('command_pin')\n                await chats_log(user_id=user_id, target_id=None, role=None, log=f"закрепил(-а) сообщение в чате")            \n            except Exception as e:\n                await message.replyLocalizedMessage('command_pin_error', {\n                        'error': e\n                    })            \n            return True\n            \n        if command in ['infobot', 'инфобот', 'информациябота']:\n            await message.replyLocalizedMessage('command_infobot')\n            await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) список информации")            \n\n        if command in ['q', 'выйти']:\n            kick_user = user_id  # кикаем автора команды\n            try:\n                peer_id_real = 2000000000 + chat_id  # если у тебя chat_id формируется так\n                await bot.api.messages.remove_chat_user(chat_id, user_id)\n                await message.replyLocalizedMessage('command_q', {\n                        'user': userf\n                    })\n                await chats_log(user_id=user_id, target_id=None, role=None, log=f"вышел(-а) из беседы")            \n            except:\n                await message.replyLocalizedMessage('command_q', {\n                        'user': userf\n                    })\n                                \n        if command in ['unpin', 'открепить', 'унпин']:\n            if await get_role(user_id, chat_id) < 5:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            try:\n                peer_id = chat_id + 2000000000\n                await bot.api.messages.unpin(peer_id=peer_id)\n                await message.replyLocalizedMessage('command_unpin')\n                await chats_log(user_id=user_id, target_id=None, role=None, log=f"открепил(-а) сообщение в чате")            \n            except Exception as e:\n                await message.replyLocalizedMessage('command_unpin_error', {\n                        'error': e\n                    })            \n            return True\n            \n        if command in ['sync', 'синхронка', 'сунс']:\n            if await get_role(user_id, chat_id) < 5:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            # Простейший отклик\n            await message.replyLocalizedMessage('command_sync')\n            await chats_log(user_id=user_id, target_id=None, role=None, log=f"синхрозовал(-а) бота с базой данных")            \n            return True\n            \n        if command in ['chatid', 'чатайди', 'айдичата']:\n            if await get_role(user_id, chat_id) < 1:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            # Простейший отклик\n            await message.replyLocalizedMessage('command_chatid', {\n                        'id': chat_id\n                    })\n            await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) оригинальный айди беседы")            \n            return True            \n\n        if command in ['gbanpl', 'гбанпл', 'глобалбан']:\n            if await get_role(user_id, chat_id) < 8:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            if chat_id == 89:\n                await message.replyLocalizedMessage('testers_chat') #\n\nВ рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)
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

            # исключаем из всех бесед где есть
            sql.execute("SELECT chat_id FROM chats")
            chats = sql.fetchall()
            for c in chats:
                try:
                    await bot.api.messages.remove_chat_user(c[0], target)
                    await bot.api.messages.send(
                        peer_id=2000000000 + c[0],
                        message=f"@id{user_id} ({await get_user_name(user_id, chat_id)}) заблокировал в беседах игроков @id{target} ({await get_user_name(target, chat_id)})\nПричина: {reason}",
                        disable_mentions=1,
                        random_id=0
                    )
                except: pass

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
            if await get_role(user_id, chat_id) < 9:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == 89:
                await message.replyLocalizedMessage('testers_chat') #

В рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)\n                return True\n\n            target = int\n            if message.reply_message:\n                target = message.reply_message.from_id\n            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:\n                target = message.fwd_messages[0].from_id\n            elif len(arguments) >= 2 and await getID(arguments[1]):\n                target = await getID(arguments[1])\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n               \n            if await equals_roles(user_id, target, chat_id, message) < 2:\n                await message.reply("Вы не можете разблокировать данного пользователя!", disable_mentions=1)\n                return True\n\n            sql.execute("SELECT * FROM gbanlist WHERE user_id = ?", (target,))\n            check = sql.fetchone()\n            if not check:\n                await message.reply("Данный пользователь не имеет глобальной блокировки!", disable_mentions=1)\n                return True\n\n            sql.execute("DELETE FROM gbanlist WHERE user_id = ?", (target,))\n            database.commit()\n\n            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), разблокировал(-а) в беседах игроков @id{target} ({await get_user_name(target, chat_id)})!", disable_mentions=1)\n            await chats_log(user_id=user_id, target_id=target, role=None, log=f"разблокировал(-а) @id{user} (пользователя) в беседах игроков")                \n            return True\n\n#========================             GBAN ================================================            ========================            \n        if command in ['gban', 'гбан']:\n            if await get_role(user_id, chat_id) < 9:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            if chat_id == tchat:\n                await message.replyLocalizedMessage('testers_chat') #\n\nВ рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)
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

            # исключаем из всех бесед где есть
            sql.execute("SELECT chat_id FROM chats")
            chats = sql.fetchall()
            for c in chats:
                try:
                    await bot.api.messages.remove_chat_user(c[0], target)
                    await bot.api.messages.send(
                        peer_id=2000000000 + c[0],
                        message=f"@id{user_id} ({await get_user_name(user_id, chat_id)}) заблокировал в беседах игроков @id{target} ({await get_user_name(target, chat_id)})\nПричина: {reason}",
                        disable_mentions=1,
                        random_id=0
                    )
                except: pass

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), заблокировал(-а) во всех беседах @id{target} ({await get_user_name(target, chat_id)})!", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=target, role=None, log=f"заблокировал(-а) в беседах игроков @id{user} (пользователя). Причина: {reason}")            
            return True


        if command in ['gunban', 'ungban']:
            if await get_role(user_id, chat_id) < 8:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == tchat:
                await message.replyLocalizedMessage('testers_chat') #

В рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)\n                return True\n\n            target = int\n            if message.reply_message:\n                target = message.reply_message.from_id\n            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:\n                target = message.fwd_messages[0].from_id\n            elif len(arguments) >= 2 and await getID(arguments[1]):\n                target = await getID(arguments[1])\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n               \n            if await equals_roles(user_id, target, chat_id, message) < 2:\n                await message.reply("Вы не можете разблокировать данного пользователя!", disable_mentions=1)\n                return True\n\n            sql.execute("SELECT * FROM globalban WHERE user_id = ?", (target,))\n            check = sql.fetchone()\n            if not check:\n                await message.reply("Данный пользователь не имеет блокировки во всех беседах!", disable_mentions=1)\n                return True\n\n            sql.execute("DELETE FROM globalban WHERE user_id = ?", (target,))\n            database.commit()\n\n            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), разблокировал(-а) во всех беседах @id{target} ({await get_user_name(target, chat_id)})!", disable_mentions=1)\n            await chats_log(user_id=user_id, target_id=target, role=None, log=f"разблокировал(-а) @id{user} (пользователя) во всех беседах")                \n            return True            \n\n        if command in ['report', 'репорт', 'жалоба', 'rep', 'реп']:\n            if await get_role(user_id, chat_id) < 4:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n        	\n            user = int\n            arg = 0\n            if message.reply_message:\n                user = message.reply_message.from_id\n                arg = 1\n            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:\n                user = message.fwd_messages[0].from_id\n                arg = 1\n            elif len(arguments) >= 2 and await getID(arguments[1]):\n                user = await getID(arguments[1])\n                arg = 2\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            reason = await get_string(arguments, arg)\n            if not reason:\n                await message.replyLocalizedMessage('command_report_reason')\n                return True\n\n            try:\n                u_name = await get_user_name(user, chat_id)\n                s_name = await get_user_name(user_id, chat_id)\n            except:\n                u_name = str(user)\n                s_name = str(user_id)\n\n            # Отправка отчёта админу в ЛС\n            ADMIN_ID = 488828183,574393629  # 🔹 Замени на свой VK ID\n            report_text = (\n                f"@all (Внимание), @all (Внимание)
"\n                f"❗ | Новая жалоба на пользователя!

"\n                f"👤 | Отправитель: @id{user_id} ({s_name})
"\n                f"🚫 | Жалоба на: @id{user} ({u_name})
"\n                f"💬 | Причина: {reason}
"\n                f"💭 | Беседа: ID {chat_id}"\n            )\n\n            try:\n                await bot.api.messages.send(\n                    peer_id=2000000110,\n                    message=report_text,\n                    random_id=0\n                )\n                await chats_log(user_id=user_id, target_id=user, role=None, log=f"подал(-а) репорт на @id{user} (пользователя). Причина: {reason}")            \n                await message.replyLocalizedMessage('command_report', {\n                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',\n                        'target': f'@id{user} ({await get_user_name(user, chat_id)})',\n                        'reason': reason\n                    })            \n            except Exception as e:\n                await message.reply(f"⚠️ Ошибка при отправке жалобы.

Вк говорит: {e}", disable_mentions=1)\n                print(f"[report command] Ошибка отправки админу: {e}")\n\n            return True            \n \n        if command in ["infochat", "инфочат"]:\n                if await get_role(user_id, chat_id) < 13:\n                    await message.replyLocalizedMessage('not_preminisionss')\n                    return True\n\n                if len(arguments) < 2:\n                    await message.reply("Использование: /infochat 12")\n                    return True\n\n                try:\n                    chat_target = int(arguments[1])\n                    peer_id = 2000000000 + chat_target\n                except:\n                    await message.reply("Неверный ID беседы!")\n                    return True\n\n                try:\n                    # Получаем информацию о беседе\n                    response = await bot.api.messages.get_conversations_by_id(peer_ids=peer_id)\n                    if not response.items:\n                        await message.reply("Беседа не найдена!")\n                        return True\n\n                    chat_data = response.items[0]\n                    chat_settings = chat_data.chat_settings\n                    title = chat_settings.title if chat_settings.title else "Без названия"\n                    peoples = chat_settings.members_count or 0\n                    active_ids = chat_settings.active_ids or []\n                except Exception as e:\n                    print(f"[INFOCHAT] Ошибка при получении информации: {e}")\n                    title = "Не удалось получить"\n                    peoples = "Не удалось получить"\n                    active_ids = []\n\n                try:\n                    sql.execute("SELECT owner_id FROM chats WHERE chat_id = ?", (chat_target,))\n                    chat_db = sql.fetchone()\n                    owner_id = chat_db[0] if chat_db else "Не удалось получить"\n                except Exception as e:\n                    print(f"[INFOCHAT] Ошибка при обращении к БД: {e}")\n                    owner_id = "Не удалось получить"\n\n                # Получаем ссылку на чат\n                try:\n                    link_response = await bot.api.messages.get_invite_link(peer_id=peer_id, reset=0)\n                    link = link_response.link\n                except Exception as e:\n                    print(f"[INFOCHAT] Ошибка при получении ссылки: {e}")\n                    link = "Не удалось получить"\n\n                # Получаем участников и админов\n                all_peoples = ""\n                all_admins = ""\n                try:\n                    members = await bot.api.messages.get_conversation_members(peer_id=peer_id)\n                    all_users = members.profiles\n                    all_admin_ids = [x.member_id for x in members.items if getattr(x, "is_admin", False)]\n\n                    i = 1\n                    for user in all_users:\n                        all_peoples += f"{i}. @id{user.id} ({user.first_name} {user.last_name})
"\n                        i += 1\n\n                    admins_count = len(all_admin_ids)\n                    j = 1\n                    for uid in all_admin_ids:\n                        all_admins += f"{j}. @id{uid} ({await get_user_name(uid, chat_id)})
"\n                        j += 1\n\n                except Exception as e:\n                    print(f"[INFOCHAT] Ошибка при получении участников: {e}")\n                    all_peoples = "Не удалось получить"\n                    all_admins = "Не удалось получить"\n                    admins_count = "Не удалось получить"\n\n                # Проверка статуса (пока без колонки banned)\n                status = "🟢 Чат активен и успешно работает"\n\n                # Формируем текст\n                text = (\n                    f"📋 Информация о беседе №{chat_target}

"\n                    f"👑 Владелец беседы: @id{owner_id} ({await get_user_name(owner_id, chat_id)})
"\n                    f"💬 Название чата: {title}
"\n                    f"👥 Количество участников: {peoples}
"\n                    f"📃 Из них:
{all_peoples}
"\n                    f"🛡 Количество администраторов: {admins_count}
"\n                    f"📃 Из них:
{all_admins}
"\n                    f"🔗 Ссылка на чат: {link}
"\n                    f"⚙️ Статус беседы: {status}"\n                )\n\n                await message.reply(text, disable_mentions=1)\n                return True                \n           \n        if command in ['listchats', 'листчатов', 'списокбесед']:\n                if await get_role(user_id, chat_id) < 13:\n                        await message.replyLocalizedMessage('not_preminisionss')\n                        return True\n\n                sql.execute("SELECT chat_id, owner_id FROM chats ORDER BY chat_id ASC")\n                all_rows = sql.fetchall()\n                if not all_rows:\n                        await message.reply("Список чатов пуст!", disable_mentions=1)\n                        return True\n\n                total = len(all_rows)\n                per_page = 20\n                max_page = (total + per_page - 1) // per_page\n\n                async def get_chats_page(page: int):\n                        start = (page - 1) * per_page\n                        end = start + per_page\n                        selected = all_rows[start:end]\n                        formatted = []\n                        for idx, (chat_id_row, owner_id) in enumerate(selected, start=start + 1):\n                                rel_id = 2000000000 + chat_id_row\n                                try:\n                                        resp = await bot.api.messages.get_conversations_by_id(peer_ids=rel_id)\n                                        if resp.items:\n                                                chat_title = resp.items[0].chat_settings.title or "Без названия"\n                                        else:\n                                                chat_title = "Без названия"\n                                except:\n                                        chat_title = "Ошибка получения названия"\n\n                                try:\n                                        link_resp = await bot.api.messages.get_invite_link(peer_id=rel_id, reset=0)\n                                        chat_link = link_resp.link\n                                except:\n                                        chat_link = "Ошибка"\n\n                                try:\n                                        owner_info = await bot.api.users.get(user_ids=owner_id)\n                                        owner_name = f"{owner_info[0].first_name} {owner_info[0].last_name}"\n                                except:\n                                        owner_name = "Не удалось получить имя"\n\n                                formatted.append(\n                                        f"{idx}) {chat_id_row} | {chat_title} | @id{owner_id} ({owner_name}) | [{chat_link}|Ссылка на чат]"\n                                )\n                        return formatted\n\n                page = 1\n                chats_page = await get_chats_page(page)\n                chats_text = "
".join(chats_page)\n                if not chats_text:\n                        chats_text = "Беседы отсутствуют!"\n\n                keyboard = (\n                        Keyboard(inline=True)\n                        .add(Callback("⏪", {"command": "chatsMinus", "page": 1}), color=KeyboardButtonColor.NEGATIVE)\n                        .add(Callback("⏩", {"command": "chatsPlus", "page": 1}), color=KeyboardButtonColor.POSITIVE)\n                )\n\n                await message.reply(\n                        f"Список зарегистрированных чатов [1 страница]:
"\n                        f"{chats_text}",\n                        disable_mentions=1, keyboard=keyboard\n                )\n                await chats_log(user_id=user_id, target_id=None, role=None, log="посмотрел(-а) список зарегистрированных бесед")\n                return True                \n\n        if command in ['title']:\n            if await get_role(user_id, chat_id) < 6:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            # Проверяем, что указано название\n            if len(arguments) < 2:\n                await message.replyLocalizedMessage('command_title_params')\n                return True\n\n            new_title = " ".join(arguments[1:])\n            try:\n                await bot.api.messages.edit_chat(chat_id=chat_id, title=new_title)\n                await message.replyLocalizedMessage('command_title', {\n                        'title': new_title\n                    })            \n                await chats_log(user_id=user_id, target_id=None, role=None, log=f"изменил(-а) название чата на {new_title}")            \n            except Exception as e:\n                await message.replyLocalizedMessage('command_title_error', {\n                        'error': e\n                    })            \n            return True\n                       \n        if command in ['ban', 'бан', 'блокировка']:\n            if await get_role(user_id, chat_id) < 2:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            if chat_id == tchat:\n                await message.replyLocalizedMessage('testers_chat') #\n\nВ рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)
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
        
        if command in ['manager', 'ruk', 'руководитель']:
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
            
        if command in ['сглтестер', 'вернутьтестера', 'стестер']:
            # айди, которым доступна эта команда
            allowed_id = 488828183,574393629

            if user_id != allowed_id:
                await message.reply("Вы не являетесь тестировщиком бота!", disable_mentions=1)
                return True

            await globalrole(user_id, 7)
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"выдал(-а) себе права главного тестировщика бота")            
            await message.reply(
                f"@id{user_id} ({await get_user_name(user_id, chat_id)}) выдал(-а) себе права главного тестировщика бота!",
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
            else:
                result_text = "❗ Неизвестный тип промокода, сообщите в /bug!!"

            sql.execute("UPDATE promocodes SET uses_left = uses_left - 1 WHERE code = ?", (code,))
            sql.execute("INSERT INTO promoused (user_id, code) VALUES (?, ?)", (user_id, code))
            database.commit()

            await message.reply(f"Промокод «{code}» успешно активирован!\n{result_text}")
            return True            

        if command in ['createpromo', 'создатьпромо']:
                if await get_role(user_id, chat_id) < 13:
                    await message.reply("Недостаточно прав для создания промокодов!")
                    return True

                if len(arguments) < 4:
                    await message.reply("Использование: /createpromo <код> <количество> <тип (money/vip)>")
                    return True

                code = arguments[1].lower()
                value = int(arguments[2])
                promo_type = arguments[3].lower()

                if promo_type not in ['money', 'vip']:
                    await message.reply("Неверный тип промокода! Доступно: money, vip")
                    return True

                sql.execute("SELECT * FROM promocodes WHERE code = ?", (code,))
                if sql.fetchone():
                    await message.reply("Такой промокод уже существует!")
                    return True

                sql.execute("INSERT INTO promocodes (code, type, value, creator_id, uses_left) VALUES (?, ?, ?, ?, ?)",
                            (code, promo_type, value, user_id, 10))  # 10 использований по умолчанию
                database.commit()

                await message.reply(f"Промокод «{code}» создан!\nТип: {promo_type}\nЗначение: {value}")
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
                await message.replyLocalizedMessage('testers_chat') #

В рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)\n                return True\n\n            user = int\n            if message.reply_message: user = message.reply_message.from_id\n            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            getban = await checkban(user, chat_id)\n            if not getban:\n                await message.replyLocalizedMessage('command_unban_not')\n                return True\n\n            if await equals_roles(user_id, getban['moder'], chat_id, message) < 1:\n                await message.replyLocalizedMessage('command_unban_preminisionss')\n                return True\n\n            await unban(user, chat_id)\n            await chats_log(user_id=user_id, target_id=user, role=None, log=f"разблокировал(-а) @id{user} (пользователя) в беседе.")            \n            await message.replyLocalizedMessage('command_unban', {\n                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',\n                        'target': f'@id{user} ({await get_user_name(user, chat_id)})'\n                    })            \n\n        if command in ['addmoder', 'moder']:\n            if await get_role(user_id, chat_id) < 2:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            user = int\n            if message.reply_message: user = message.reply_message.from_id\n            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            if await equals_roles(user_id, user, chat_id, message) < 2:\n                \n                return True\n\n            await roleG(user, chat_id, 1)\n            await message.replyLocalizedMessage('command_addmoder', {\n                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',\n                        'target': f'@id{user} ({await get_user_name(user, chat_id)})'\n                    })\n            await chats_log(user_id=user_id, target_id=user, role=None, log=f"выдал(-а) права модератора @id{user} (пользователю)")            \n            await add_punishment(chat_id, user_id)\n            if await get_sliv(user_id, chat_id) and await get_role(user_id, chat_id) < 5:\n                await roleG(user_id, chat_id, 0)\n                await message.reply(\n                    f"❗️ Уровень прав @id{user_id} (пользователя) был снят из-за подозрений в сливе беседы

{await staff_zov(chat_id)}")\n\n        if command in ['removerole', 'rrole', 'снятьроль']:\n            if await get_role(user_id, chat_id) < 2:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            if chat_id == tchat:\n                await message.replyLocalizedMessage('testers_chat') #\n\nВ рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)
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
            if await get_role(user_id, chat_id) < 11:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == tchat:
                await message.replyLocalizedMessage('testers_chat') #

В рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)\n                return True\n\n            user = int\n            if message.reply_message: user = message.reply_message.from_id\n            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            if await equals_roles(user_id, user, chat_id, message) < 2:\n                await message.reply("Вы не можете снять роль данному пользователю!", disable_mentions=1)\n                return True\n\n            await globalrole(user, 0)\n            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) забрал(-а) глобальную роль у @id{user} ({await get_user_name(user, chat_id)})", disable_mentions=1)\n            await chats_log(user_id=user_id, target_id=user, role=None, log=f"снял(-а) глобальную роль с @id{user} (пользователя)")            \n            await add_punishment(chat_id, user_id)\n            if await get_sliv(user_id, chat_id) and await get_role(user_id, chat_id) < 5:\n                await roleG(user_id, chat_id, 0)\n                await message.reply(\n                    f"❗️ Уровень прав @id{user_id} (пользователя) был снят из-за подозрений в сливе беседы

{await staff_zov(chat_id)}")\n                    \n        if command in ['снятьрольнавсегда', 'adminrrole', 'arrole']:\n            allowed_id = 488828183,574393629\n\n            if user_id != allowed_id:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            user = int\n            if message.reply_message:\n                user = message.reply_message.from_id\n            elif len(arguments) >= 2 and await getID(arguments[1]):\n                user = await getID(arguments[1])\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            await globalrole(user, 0)\n            await roleG(user_id, chat_id, 0)\n            await message.reply(\n                f"@id{user_id} ({await get_user_name(user_id, chat_id)}) забрал(-а) роль во всех чатах у "\n                f"@id{user} ({await get_user_name(user, chat_id)})",\n                disable_mentions=1\n            )\n\n            await chats_log(\n                user_id=user_id,\n                target_id=user,\n                role=None,\n                log=f"снял(-а) глобальную роль с @id{user} (пользователя)"\n            )\n\n            await add_punishment(chat_id, user_id)\n\n            if await get_sliv(user_id, chat_id) and await get_role(user_id, chat_id) < 5:\n                await roleG(user_id, chat_id, 0)\n                await message.reply(\n                    f"❗️ Уровень прав @id{user_id} (пользователя) был снят из-за подозрений "\n                    f"в сливе беседы

{await staff_zov(chat_id)}"\n                )\n                                    \n        if command in ['unglobaltester', 'снятьглобалтестера', 'тснятьроль']:\n            if await get_role(user_id, chat_id) < 12:\n                await message.reply("Вы не являетесь тестировщиком бота!", disable_mentions=1)\n                return True\n\n            user = int\n            if message.reply_message: user = message.reply_message.from_id\n            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            if await equals_roles(user_id, user, chat_id, message) < 2:\n                await message.reply("Вы не можете снять роль данному пользователю!", disable_mentions=1)\n                return True\n\n            await globalrole(user, 0)\n            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) забрал(-а) глобальную роль тестера у @id{user} ({await get_user_name(user, chat_id)})", disable_mentions=1)\n            await chats_log(user_id=user_id, target_id=user, role=None, log=f"снял(-а) глобальную роль с @id{user} (пользователя)")            \n            await add_punishment(chat_id, user_id)\n            if await get_sliv(user_id, chat_id) and await get_role(user_id, chat_id) < 5:\n                await roleG(user_id, chat_id, 0)\n                await message.reply(\n                    f"❗️ Уровень прав @id{user_id} (пользователя) был снят из-за подозрений в сливе беседы

{await staff_zov(chat_id)}")                    \n\n        if command in ['zov', 'зов', 'вызов']:\n            if await get_role(user_id, chat_id) < 2:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            reason = await get_string(arguments, 1)\n            if not reason:\n                await message.replyLocalizedMessage('command_zov_not_reason')\n                return True\n\n            users = await bot.api.messages.get_conversation_members(peer_id=message.peer_id, fields=["online_info", "online"])\n            users = json.loads(users.json())\n            user_f = []\n            gi = 0\n            for i in users["profiles"]:\n                if not i['id'] == user_id:\n                    gi = gi + 1\n                    if gi <= 100:\n                        user_f.append(f"@id{i['id']} (🖤)")\n            zov_users = ''.join(user_f)\n\n            await message.replyLocalizedMessage('command_zov', {\n                        'user': f'@id{user_id} (администратором беседы)',\n                        'zov_users': zov_users,\n                        'reason': reason\n                    })            \n            await chats_log(user_id=user_id, target_id=None, role=None, log=f"вызвал(-а) всех пользователей в беседе. Причина: {reason}")            \n\n        if command in ['ozov', 'online', 'озов']:\n            if await get_role(user_id, chat_id) < 2:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            reason = await get_string(arguments, 1)\n            if not reason:\n                await message.replyLocalizedMessage('command_ozov_not_reason')\n                return True\n\n            users = await bot.api.messages.get_conversation_members(peer_id=message.peer_id, fields=["online_info", "online"])\n            users = json.loads(users.json())\n            online_users = []\n            gi = 0\n            for i in users["profiles"]:\n                if i["online"] == 1:\n                    if not i['id'] == user_id:\n                        gi = gi + 1\n                        if gi <= 100:\n                            online_users.append(f"@id{i['id']} (♦️)")\n\n            online_zov = "".join(online_users)\n            await message.replyLocalizedMessage('command_ozov', {\n                        'user': f'@id{user_id} (администратором беседы)',\n                        'info': online_zov,\n                        'reason': reason\n                    })            \n            await chats_log(user_id=user_id, target_id=None, role=None, log=f"вызвал(-а) всех пользователей онлайн в беседе. Причина: {reason}")            \n\n        if command in ['onlinelist', 'olist', 'олист']:\n            if await get_role(user_id, chat_id) < 2:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            users = await bot.api.messages.get_conversation_members(peer_id=message.peer_id, fields=["online", "online_info"])\n            users = json.loads(users.json())\n            online_users = []\n            gi = 0\n            for i in users["profiles"]:\n                if i["online"] == 1:\n                    if not i['id'] == user_id:\n                        gi = gi + 1\n                        if gi <= 80:\n                            if i["online_info"]["is_mobile"] == False:\n                                online_users.append(f"@id{i['id']} ({await get_user_name(i['id'], chat_id)}) -- 💻")\n                            else:\n                                online_users.append(f"@id{i['id']} ({await get_user_name(i['id'], chat_id)}) -- 📱")\n\n            olist_users = "
".join(online_users)\n            await message.replyLocalizedMessage('command_onlinelist', {\n                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',\n                        'info': online_users,\n                        'count': gi\n                    })\n            await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) список пользователей онлайн в чате")            \n\n        if command in ['banlist', 'bans', 'банлист', 'баны']:\n            if await get_role(user_id, chat_id) < 2:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            bans = await banlist(chat_id)\n            bans_do = []\n            gi = 0\n            for i in bans:\n                gi = gi + 1\n                if gi <= 10:\n                    bans_do.append(i)\n            bans_str = "
".join(bans_do)\n\n            await message.replyLocalizedMessage('command_banlist', {\n                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',\n                        'info': bans_str,\n                        'count': gi\n                    })\n            await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) список заблокированных пользователей в чате")            \n\n        if command in ['delete', 'удалить']:\n            if await get_role(user_id, chat_id) < 1:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            if not message.reply_message:\n                await message.reply("Чтобы удалить сообщение, нужно ответить на него!")\n                return True\n\n            cmid = message.reply_message.conversation_message_id\n            user = message.reply_message.from_id\n\n            if await equals_roles(user_id, user, chat_id, message) < 2:\n                await message.reply("Вы не можете удалить сообщение данного пользователя!", disable_mentions=1)\n                return True\n\n            try: await bot.api.messages.delete(group_id=message.group_id, peer_id=peer_id, delete_for_all=True, cmids=cmid)\n            except: pass\n\n            try: await bot.api.messages.delete(group_id=message.group_id, peer_id=peer_id, delete_for_all=True, cmids=message.conversation_message_id)\n            except: pass\n\n# ================ SERVER COMMANDS =====================\n        if command in ['sremovenick', 'srnick']:\n            if await get_role(user_id, chat_id) < 3:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            # --- Проверка привязки сервера ---\n            server_chats = await get_server_chats(chat_id)\n            if not server_chats:\n                await message.reply("Сначало укажите сервер, /server!", disable_mentions=1)\n                return True\n\n            user = int\n            server_id = await get_current_server(chat_id)\n            if message.reply_message:\n                user = message.reply_message.from_id\n            elif len(arguments) >= 2 and await getID(arguments[1]):\n                user = await getID(arguments[1])\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            for i in server_chats:\n                try:\n                    await rnick(user, i)\n                except:\n                    pass\n\n            await message.reply(\n                f"@id{user_id} ({await get_user_name(user_id, chat_id)}) убрал(-а) ник в беседах сервера «{server_id}» @id{user} (пользователю)",\n                disable_mentions=1\n            )\n            await chats_log(\n                user_id=user_id, target_id=user, role=None,\n                log=f"убрал(-а) ник в беседах сервера @id{user} (пользователю)"\n            )\n\n        if command in ['ssnick', 'ssetnick', 'ссетник', 'ссник']:\n            if await get_role(user_id, chat_id) < 4:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            # --- Проверка привязки сервера ---\n            server_chats = await get_server_chats(chat_id)\n            if not server_chats:\n                await message.reply("Сначало укажите сервер, /server!", disable_mentions=1)\n                return True\n\n            user = int\n            arg = 0\n            if message.reply_message:\n                user = message.reply_message.from_id\n                arg = 1\n            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:\n                user = message.fwd_messages[0].from_id\n                arg = 1\n            elif len(arguments) >= 2 and await getID(arguments[1]):\n                user = await getID(arguments[1])\n                arg = 2\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            new_nick = await get_string(arguments, arg)\n            server_id = await get_current_server(chat_id)\n            if not new_nick:\n                await message.reply("Укажите ник пользователя!", disable_mentions=1)\n                return True\n\n            if await equals_roles(user_id, user, chat_id, message) == 0:\n                await message.reply("Вы не можете установить ник данному пользователю!", disable_mentions=1)\n                return True\n\n            for i in server_chats:\n                try:\n                    await setnick(user, i, new_nick)\n                except:\n                    pass\n\n            await message.reply(\n                f"@id{user_id} ({await get_user_name(user_id, chat_id)}) установил новое имя в беседах сервера «{server_id}» @id{user} (пользователю)!
Новый ник: {new_nick}",\n                disable_mentions=1\n            )\n            await chats_log(\n                user_id=user_id, target_id=user, role=None,\n                log=f"установил(-а) новый ник в беседах сетки @id{user} (пользователю). Новый ник: {new_nick}"\n            )\n\n        if command in ['skick', 'снят', 'скик']:\n            if await get_role(user_id, chat_id) < 3:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            # --- Проверка привязки сервера ---\n            server_chats = await get_server_chats(chat_id)\n            server_id = await get_current_server(chat_id)\n            if not server_chats:\n                await message.reply("Сначало укажите сервер, /server!", disable_mentions=1)\n                return True\n\n            user = int\n            arg = 0\n            if message.reply_message:\n                user = message.reply_message.from_id\n                arg = 1\n            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:\n                user = message.fwd_messages[0].from_id\n                arg = 1\n            elif len(arguments) >= 2 and await getID(arguments[1]):\n                user = await getID(arguments[1])\n                arg = 2\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            if await equals_roles(user_id, user, chat_id, message) < 2:\n                await message.reply("Вы не можете исключить данного пользователя!", disable_mentions=1)\n                return True\n\n            reason = await get_string(arguments, arg)\n\n            for i in server_chats:\n                try:\n                    await bot.api.messages.remove_chat_user(i, user)\n                    msg = f"@id{user_id} ({await get_user_name(user_id, chat_id)}) исключил(-а) в беседах сервера «{server_id}» @id{user} ({await get_user_name(user, chat_id)})"\n                    if reason:\n                        msg += f"
Причина: {reason}"\n                    await bot.api.messages.send(peer_id=2000000000 + i, message=msg, disable_mentions=1, random_id=0)\n                except:\n                    await message.answer(f"Не удалось исключить @id{user} (пользователя) в беседах сервера «{server_id}»")\n\n            await chats_log(user_id=user_id, target_id=user, role=None,\n                            log=f"исключил(-а) @id{user} (пользователя) в сетке бесед")\n            await add_punishment(chat_id, user_id)\n\n        if command in ['sremoverole', 'srrole']:\n            if await get_role(user_id, chat_id) < 4:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            # --- Проверка привязки сервера ---\n            server_chats = await get_server_chats(chat_id)\n            server_id = await get_current_server(chat_id)\n            if not server_chats:\n                await message.reply("Сначало укажите сервер, /server!", disable_mentions=1)\n                return True\n\n            user = int\n            if message.reply_message:\n                user = message.reply_message.from_id\n            elif len(arguments) >= 2 and await getID(arguments[1]):\n                user = await getID(arguments[1])\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            if await equals_roles(user_id, user, chat_id, message) < 2:\n                await message.reply("Вы не можете снять роль данному пользователю!", disable_mentions=1)\n                return True\n\n            for i in server_chats:\n                try:\n                    await roleG(user, i, 0)\n                except:\n                    pass\n\n            await message.reply(\n                f"@id{user_id} ({await get_user_name(user_id, chat_id)}) забрал(-а) роль в беседах сервера «{server_id}» у @id{user} (пользователя)",\n                disable_mentions=1\n            )\n            await chats_log(\n                user_id=user_id, target_id=user, role=None,\n                log=f"забрал(-а) роль в беседах сервера @id{user} (пользователя)"\n            )\n\n        if command in ['sban', 'сбан']:\n            if await get_role(user_id, chat_id) < 3:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            # --- Проверка привязки сервера ---\n            server_chats = await get_server_chats(chat_id)\n            server_id = await get_current_server(chat_id)\n            if not server_chats:\n                await message.reply("Сначало укажите сервер, /server!", disable_mentions=1)\n                return True\n\n            user = int\n            arg = 0\n            if message.reply_message:\n                user = message.reply_message.from_id\n                arg = 1\n            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:\n                user = message.fwd_messages[0].from_id\n                arg = 1\n            elif len(arguments) >= 2 and await getID(arguments[1]):\n                user = await getID(arguments[1])\n                arg = 2\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            if await equals_roles(user_id, user, chat_id, message) < 2:\n                await message.reply("Вы не можете заблокировать данного пользователя!", disable_mentions=1)\n                return True\n\n            reason = await get_string(arguments, arg)\n            if not reason:\n                await message.reply("Укажите причину блокировки!", disable_mentions=1)\n                return True\n\n            for i in server_chats:\n                try:\n                    await ban(user, user_id, i, reason)\n                    await bot.api.messages.remove_chat_user(i, user)\n                    keyboard = (\n                        Keyboard(inline=True)\n                        .add(Callback("Снять бан", {"command": "unban", "user": user, "chatId": chat_id}),\n                             color=KeyboardButtonColor.POSITIVE)\n                    )\n                    await bot.api.messages.send(peer_id=2000000000 + i,\n                                                message=f"@id{user_id} ({await get_user_name(user_id, chat_id)}) заблокировал(-а) в беседах сервера «{server_id}» @id{user} ({await get_user_name(user, chat_id)})
Причина: {reason}",\n                                                disable_mentions=1, random_id=0, keyboard=keyboard)\n                except:\n                    pass\n\n            await chats_log(user_id=user_id, target_id=user, role=None,\n                            log=f"заблокировал(-а) @id{user} (пользователя) в беседах сервера")\n            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) заблокировал(-а) в беседах сервера «{server_id}» @id{user} ({await get_user_name(user, chat_id)})
Причина: {reason}", disable_mentions=1)                \n            await add_punishment(chat_id, user_id)\n\n        if command in ['sunban', 'санбан', 'сунбан']:\n            if await get_role(user_id, chat_id) < 3:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            # --- Проверка привязки сервера ---\n            server_chats = await get_server_chats(chat_id)\n            server_id = await get_current_server(chat_id)\n            if not server_chats:\n                await message.reply("Сначало укажите сервер, /server!", disable_mentions=1)\n                return True\n\n            user = int\n            if message.reply_message:\n                user = message.reply_message.from_id\n            elif len(arguments) >= 2 and await getID(arguments[1]):\n                user = await getID(arguments[1])\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            for i in server_chats:\n                try:\n                    await unban(user, i)\n                except:\n                    pass\n\n            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) разблокировал(-а) в беседах сервера «{server_id}» @id{user} ({await get_user_name(user, chat_id)})")\n            await chats_log(user_id=user_id, target_id=user, role=None,\n                            log=f"разблокировал(-а) в беседах сервера @id{user} (пользователя)")            \n\n# =============================================\n        if command in ['inactivelist', 'inactive', 'ilist']:\n            if await get_role(user_id, chat_id) < 2:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            users = await bot.api.messages.get_conversation_members(peer_id=message.peer_id,fields=["online_info", "online", "last_seen"])\n            users = json.loads(users.json())\n            unactive_users_day = []\n            count_uad = 0\n            unactive_users_moon = []\n            count_uam = 0\n            for i in users["profiles"]:\n                try:\n                    import time\n                    currency_time = time.time()\n                    time_seen = i['last_seen']['time']\n                    last_seen_device_list = {1: "📱", 2: "📱", 3: "📱", 4: "📱", 5: "📱", 6: "💻", 7: "💻"}\n                    last_seen_device = last_seen_device_list.get(i['last_seen']['platform'])\n                    if time_seen <= currency_time - 604800:\n                        count_uam = count_uam + 1\n                        if count_uam <= 30:\n                            info = await bot.api.users.get(i['id'])\n                            unactive_users_moon.append(\n                                f"{count_uam}) @id{i['id']} ({info[0].first_name} {info[0].last_name}) -- {last_seen_device}")\n                    elif time_seen <= currency_time - 86400:\n                        count_uad = count_uad + 1\n                        if count_uad <= 30:\n                            info = await bot.api.users.get(i['id'])\n                            unactive_users_day.append(\n                                f"{count_uad}) @id{i['id']} ({info[0].first_name} {info[0].last_name}) -- {last_seen_device}")\n                except:\n                    pass\n            uad = "
".join(unactive_users_day)\n            uam = "
".join(unactive_users_moon)\n            await message.replyLocalizedMessage('command_inactivelist', {\n                        'day': uad,\n                        'week': uam\n                    })            \n            await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) список неактивных пользователей в чате")            \n\n        if command in ['mkick', 'мкик', 'masskick']:\n            if await get_role(user_id, chat_id) < 7:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            if len(arguments) <= 1:\n                arguments = 'all'\n                return True\n            if len(arguments) >= 30:\n                arguments = 'all'\n                return True\n\n            if arguments[1] in ['all', 'все']:\n                if await get_role(user_id, chat_id) < 7:\n                    await message.replyLocalizedMessage('not_preminisionss')\n                    return True\n\n                users = await bot.api.messages.get_conversation_members(peer_id=message.peer_id,\n                                                                        fields=["online_info", "online"])\n                users = json.loads(users.json())\n                user_f = []\n                gi = 0\n                for i in users["profiles"]:\n                    if not i['id'] == user_id and await get_role(i['id'], chat_id) <= 0:\n                        await bot.api.messages.remove_chat_user(chat_id, int(i['id']))\n\n                await message.answer(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) исключил(-а) пользователей без ролей", disable_mentions=1)\n                await chats_log(user_id=user_id, target_id=None, role=None, log=f"исключил(-а) пользователей без ролей в чате")            \n                return True\n\n\n            do_users = []\n            for i in range(len(arguments)):\n                if i <= 0:\n                    pass\n                else:\n                    do_users.append(arguments[i])\n            users = []\n            for i in do_users:\n                idp = await getID(i)\n                if idp:\n                    users.append(idp)\n            kick_users_list = []\n            for i in users:\n                if await equals_roles(user_id, i, chat_id) < 2:\n                    await message.answer(f"У @id{i} уровень прав выше!", disable_mentions=1)\n                else:\n                    try:\n                        await bot.api.messages.remove_chat_user(chat_id, i)\n                        info = await bot.api.users.get(int(i))\n                        kick_users_list.append(f"@id{i} ({info[0].first_name})")\n                    except:\n                        pass\n            kick_users = ", ".join(kick_users_list)\n            await message.replyLocalizedMessage('command_masskick')\n            await add_punishment(chat_id, user_id)\n            if await get_sliv(user_id, chat_id) and await get_role(user_id, chat_id) < 5:\n                await roleG(user_id, chat_id, 0)\n                await message.reply(\n                    f"❗️ Уровень прав @id{user_id} (пользователя) был снят из-за подозрений в сливе беседы

{await staff_zov(chat_id)}")\n\n        if command in ['quiet', 'silence', 'тишина']:\n            if await get_role(user_id, chat_id) < 3:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            silence = await quiet(chat_id)\n            if silence:\n            	await message.replyLocalizedMessage('command_quiet_on', {\n                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})'\n                    })\n            	\n            else:\n            	await message.replyLocalizedMessage('command_quiet_off', {\n                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})'\n                    })\n\n        if command in ['addsenmoder', 'senmoder']:\n            if await get_role(user_id, chat_id) < 3:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            user = int\n            if message.reply_message: user = message.reply_message.from_id\n            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            if await equals_roles(user_id, user, chat_id, message) < 2:\n                await message.replyLocalizedMessage('set_role_preminisionss')\n                return True\n\n            await roleG(user, chat_id, 2)\n            await message.replyLocalizedMessage('command_addsenmoder', {\n                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',\n                        'target': f'@id{user} ({await get_user_name(user, chat_id)})'\n                    })            \n            await chats_log(user_id=user_id, target_id=user, role=None, log=f"выдал(-а) права старшего модератора @id{user} (пользователю)")            \n            await add_punishment(chat_id, user_id)\n            if await get_sliv(user_id, chat_id) and await get_role(user_id, chat_id) < 5:\n                await roleG(user_id, chat_id, 0)\n                await message.reply(\n                    f"❗️ Уровень прав @id{user_id} (пользователя) был снят из-за подозрений в сливе беседы

{await staff_zov(chat_id)}")\n\n        if command in ['rnickall', 'allrnick', 'arnick', 'mrnick']:\n            if await get_role(user_id, chat_id) < 3:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            if chat_id == tchat:\n                await message.replyLocalizedMessage('testers_chat') #\n\nВ рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)
                return True

            await rnickall(chat_id)
            await message.replyLocalizedMessage('command_rnickall', {
                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})'
                    })            
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"очистил(-а) ники в беседе!")            

        if command in ['addadmin', 'admin','админ']:
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

        if command in ['addsenadmin', 'addsenadm', 'senadm', 'senadmin']:
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

        if command in ['settester', 'тестер', 'тестировщик']:
            # Разрешаем только чат с ID 23
            if chat_id != tchat:
                await message.reply(
                    "Данная команда может быть использована только в официальной тестовой беседе бота!",
                    disable_mentions=1
                )
                return True

            # Проверка прав
            if await get_role(user_id, chat_id) < 10:
                await message.reply("Вы не являетесь тестировщиком бота!", disable_mentions=1)
                return True

            # Получение цели команды
            user = int
            if message.reply_message:
                user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
            else:
                await message.replyLocalizedMessage('select_user')
                return True

            # Проверка уровня прав
            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.replyLocalizedMessage('set_role_preminisionss')
                return True

            await bot.api.messages.send(
                peer_id=2000000089,
                random_id=0,
                message=(
                    f"@id{user} ({await get_user_name(user, chat_id)}), успешно авторизован в системе как « тестировщик бота 1 уровень »\n\nНазначил(а): @id{user_id} ({await get_user_name(user_id, chat_id)})"
                )
            )

            # Выдача роли тестировщика
            await roleG(user, chat_id, 8)
            await message.reply(
                f"@id{user_id} ({await get_user_name(user_id, chat_id)}) выдал(-а) права тестировщика бота "
                f"@id{user} ({await get_user_name(user, chat_id)})",
                disable_mentions=1
            )

            await chats_log(
                user_id=user_id,
                target_id=user,
                role=None,
                log=f"выдал(-а) права тестировщика @id{user} (пользователю)"
            )            

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
                sql.execute(f"""\n                CREATE TABLE IF NOT EXISTS {table_name} (\n                    chat_id INTEGER,\n                    chat_title TEXT\n                )\n                """)
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
            if await get_role(user_id, chat_id) < 11:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == tchat:
                await message.replyLocalizedMessage('testers_chat') #

В рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)\n                return True\n\n            user = int\n            if message.reply_message: user = message.reply_message.from_id\n            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            if await equals_roles(user_id, user, chat_id, message) < 2:\n                await message.replyLocalizedMessage('set_role_preminisionss')\n                return True\n\n            await roleG(user, chat_id, 7)\n            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) выдал(-а) права владельца беседы @id{user} ({await get_user_name(user, chat_id)})", disable_mentions=1)\n            await chats_log(user_id=user_id, target_id=user, role=None, log=f"выдал(-а) права владельца беседы @id{user} (пользователю)")            \n                        \n        if command in ['addzamdirector', 'addzamd', 'аддзам', 'заместитель']:\n            if await get_role(user_id, chat_id) < 11:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            if chat_id == tchat:\n                await message.replyLocalizedMessage('testers_chat') #\n\nВ рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)
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
            if await get_role(user_id, chat_id) < 13:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            if chat_id == tchat:
                await message.replyLocalizedMessage('testers_chat') #

В рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)\n                return True\n\n            user = int\n            if message.reply_message: user = message.reply_message.from_id\n            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            if await equals_roles(user_id, user, chat_id, message) < 2:\n                await message.replyLocalizedMessage('set_role_preminisionss')\n                return True\n\n            await globalrole(user, 4)\n            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) выдал(-а) права основного заместителя директора @id{user} ({await get_user_name(user, chat_id)})", disable_mentions=1)\n            await chats_log(user_id=user_id, target_id=user, role=None, log=f"выдал(-а) права основного заместителя директора @id{user} (пользователю)")            \n            \n        if command in ['adddirector', 'director', 'адддиректор', 'директор']:\n            if await get_role(user_id, chat_id) < 14:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            if chat_id == tchat:\n                await message.replyLocalizedMessage('testers_chat') #\n\nВ рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)
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
                await message.replyLocalizedMessage('testers_chat') #

В рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)\n                return True\n\n            user = int\n            if message.reply_message: user = message.reply_message.from_id\n            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            if await equals_roles(user_id, user, chat_id, message) < 2:\n                await message.replyLocalizedMessage('set_role_preminisionss')\n                return True\n\n            await globalrole(user, 7)\n            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) выдал(-а) права разработчика бота @id{user} ({await get_user_name(user, chat_id)})", disable_mentions=1)\n            await chats_log(user_id=user_id, target_id=user, role=None, log=f"выдал(-а) права разработчика бота @id{user} (пользователю)")            \n\n        if command in ['sayall', 'gzov', 'news']:\n            if await get_role(user_id, chat_id) < 13:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            if chat_id == tchat:\n                await message.replyLocalizedMessage('testers_chat') #\n\nВ рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)
                return True

            reason = await get_string(arguments, 1)
            if not reason:
                await message.reply("Укажите текст рассылки!")
                return True

            peer_ids = await get_all_peerids()
            for i in peer_ids:
                try: await bot.api.messages.send(peer_id=i, message=reason, disable_mentions=1, random_id=0)
                except: pass
                
        if command in ['deltester', 'delteter', 'untester', 'снятьтестера']:
            allowed_ids = [488828183, 574393629]
            if user_id not in allowed_ids:
                await message.replyLocalizedMessage('not_preminisionss')
                return True

            target = None
            if message.reply_message:
                target = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                target = int(await getID(arguments[1]))
            if not target:
                await message.reply("Укажите пользователя!")
                return True

            sql.execute("DELETE FROM global_managers WHERE user_id = ?", (target,))
            database.commit()
            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), глобально снял(-а) роль тестера у @id{target} ({await get_user_name(target, chat_id)})")
            log.info("Владелец %s снял глобальную роль тестера у %s", user_id, target)
            return True

        if command in ['szov', 'serverzov', 'сзов']:
            if await get_role(user_id, chat_id) < 3:
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
                await message.replyLocalizedMessage('testers_chat') #

В рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)\n                return True\n\n            user = int\n            if len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            if user == user_id: return await message.replyLocalizedMessage('command_editowner_user_user')\n\n            if len(arguments) <= 2: return await message.replyLocalizedMessage('command_editowner_confirm')\n            if not arguments_lower[2] == "confirm":\n                return await message.replyLocalizedMessage('command_editowner_confirm')\n\n            await set_onwer(user, chat_id)\n            await roleG(user_id, chat_id, 6)\n\n            await message.replyLocalizedMessage('command_editowner', {\n                        'user': f'@id{user_id} ({await get_user_name(user_id, chat_id)})',\n                        'target': f'@id{user} ({await get_user_name(user, chat_id)})'\n                    })            \n            await chats_log(user_id=user_id, target_id=user, role=None, log=f"передал(-а) права владельца беседы @id{user} (пользователю)")            \n\n        if command in ['srole', 'сроле']:\n            if await get_role(user_id, chat_id) < 3:\n                await message.replyLocalizedMessage('not_preminisionss')\n                return True\n\n            if chat_id == tchat:\n                await message.reply(\n                    "Данная беседа проводится в специализированном чате, который предназначен исключительно для тестировщиков бота.

"\n                    "В рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.",\n                    disable_mentions=1\n                )\n                return True\n\n            user = int\n            arg = 2\n            if message.reply_message:\n                user = message.reply_message.from_id\n                arg = 1\n            elif len(arguments) >= 2 and await getID(arguments[1]):\n                user = await getID(arguments[1])\n            else:\n                await message.replyLocalizedMessage('select_user')\n                return True\n\n            if await get_role(user_id, chat_id) <= await get_role(user, chat_id):\n                return await message.reply("Вы не можете взаимодействовать с данным пользователем!")\n\n            if len(arguments) < arg + 1:\n                return await message.reply("Укажите аргументы!")\n\n            if not arguments[arg].isdigit():\n                return await message.reply("Укажите число!")\n\n            level_num = int(arguments[arg])\n            if level_num >= await get_role(user_id, chat_id):\n                return await message.reply("Вы не можете выдать роль, которая выше вашей!")\n\n            if level_num < 0:\n                return await message.reply("Нельзя выдать такую роль!")\n\n            # --- Преобразуем число в словарь ролей ---\n            roles_dict = {\n                1: "модератора",\n                2: "старшего модератора",\n                3: "администратора",\n                4: "старшего администратора",\n                5: "зам. спец администратора",\n                6: "спец. администратора"\n            }\n            level_name = roles_dict.get(level_num, f"уровень {level_num}")\n            server_id = await get_current_server(chat_id)\n            \n            server_chats = await get_server_chats(chat_id)\n            if not server_chats:\n                await message.reply("Сначало укажите сервер, /server!", disable_mentions=1)\n                return True\n\n            # --- Применяем роль ко всем чатам сервера ---\n            for i in server_chats:\n                try:\n                    await roleG(user, i, level_num)\n                except Exception as e:\n                    print(f"[SROLE] Ошибка при выдаче роли в беседе {i}: {e}")\n\n            await message.reply(\n                f"@id{user_id} ({await get_user_name(user_id, chat_id)}) выдал(-а) права {level_name} "\n                f"в беседах сервера «{server_id}» @id{user} ({await get_user_name(user, chat_id)})"\n            )\n            await chats_log(\n                user_id=user_id,\n                target_id=user,\n                role=None,\n                log=f"выдал(-а) права «{level_name}» в беседах сервера @id{user} (пользователю)"\n            )\n            return True\n            \n\n\n    else:\n        if user_id < 1: return True\n        if await check_chat(chat_id):\n            if await get_mute(user_id, chat_id) and not await checkMute(chat_id, user_id):\n                try: await bot.api.messages.delete(group_id=message.group_id, peer_id=message.peer_id, delete_for_all=True, cmids=message.conversation_message_id)\n                except: pass\n            elif await check_quit(chat_id) and (await get_role(user_id, chat_id) or 0) < 1:\n                try: await bot.api.messages.delete(group_id=message.group_id, peer_id=message.peer_id, delete_for_all=True, cmids=message.conversation_message_id)\n                except: pass\n                print(await get_role(user_id, chat_id) < 1)\n            else:\n                if await get_filter(chat_id):\n                    bws = await get_banwords(chat_id)\n                    for i in bws:\n                        if i in message.text.lower() and await get_role(user_id, chat_id) < 1:\n                            await add_mute(user_id, chat_id, 'Бот', 'Написание запрещенных слов', 30)\n                            await add_mutelog(chat_id, user_id, -123456789, "Написание запрещенных слов", 30, "выдан")\n                            keyboard = (\n                                Keyboard(inline=True)\n                                .add(Callback("Снять мут", {"command": "unmute", "chatId": chat_id, "user": user_id}), color=KeyboardButtonColor.POSITIVE)\n                            )\n                            await message.reply(f"@id{user_id} (Пользователь) получил(-а) мут на 30 минут за написание запрещенного слова!", disable_mentions=1, keyboard=keyboard)\n                            try: await bot.api.messages.delete(group_id=message.group_id, peer_id=message.peer_id,delete_for_all=True, cmids=message.conversation_message_id)\n                            except: pass\n                            return True\n\n            await new_message(user_id, message.message_id, message.conversation_message_id, chat_id)\n            if await get_spam(user_id, chat_id) and await get_role(user_id, chat_id) < 1:\n                keyboard = (\n                    Keyboard(inline=True)\n                    .add(Callback("Снять мут", {"command": "unmute", "chatId": chat_id, "user": user_id}), color=KeyboardButtonColor.POSITIVE)\n                )\n                await message.reply(f"@id{user_id} (Пользователь) получил(-а) мут на 30 минут за спам!", disable_mentions=1, keyboard=keyboard)\n                await add_mute(user_id, chat_id, 'Bot', 'Спам', 30)\n                try:await bot.api.messages.delete(group_id=message.group_id, peer_id=message.peer_id,delete_for_all=True, cmids=message.conversation_message_id)\n                except: pass\n\nasync def start_tasks():\n    asyncio.create_task(check_and_clear_midnight())\n\nif __name__ == "__main__":\n    # Запускаем фоновую задачу очистки в отдельной задаче\n    async def start_background_tasks():\n        asyncio.create_task(check_and_clear_midnight())\n    \n    # Создаем event loop для vkbottle\n    loop = asyncio.new_event_loop()\n    asyncio.set_event_loop(loop)\n    \n    # Запускаем фоновую задачу\n    loop.create_task(check_and_clear_midnight())\n    loop.run_until_complete(init_economy_schema())\n\n    print("\033[92mБот получен, запуск!\033[0m")\n    \n    # Запускаем бота через vkbottle\n    bot.run_forever()\n