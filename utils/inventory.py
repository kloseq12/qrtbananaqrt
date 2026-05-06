from typing import List, Dict, Optional
import aiosqlite
from utils.sqlite_utils import DB_WRITE_LOCK, connect_sqlite

DB_PATH = "database.db"


async def get_inventory(user_id: int) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, item_type, item_name, item_value FROM inventory WHERE user_id = ? ORDER BY id",
            (user_id,),
        )
        rows = await cur.fetchall()
        return [dict(row) for row in rows]


async def add_item(user_id: int, item_type: str, item_name: str, item_value: int = 0) -> None:
    async with DB_WRITE_LOCK:
        db = await connect_sqlite()
        try:
            await db.execute(
                "INSERT INTO inventory (user_id, item_type, item_name, item_value) VALUES (?, ?, ?, ?)",
                (user_id, item_type, item_name, item_value),
            )
            await db.commit()
        finally:
            await db.close()


async def get_item_by_id(user_id: int, item_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, item_type, item_name, item_value FROM inventory WHERE user_id = ? AND id = ?",
            (user_id, item_id),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def remove_item(user_id: int, item_id: int) -> None:
    async with DB_WRITE_LOCK:
        db = await connect_sqlite()
        try:
            await db.execute("DELETE FROM inventory WHERE user_id = ? AND id = ?", (user_id, item_id))
            await db.commit()
        finally:
            await db.close()


async def take_item_by_id(user_id: int, item_id: int) -> Optional[Dict]:
    item = await get_item_by_id(user_id, item_id)
    if not item:
        return None
    await remove_item(user_id, item_id)
    return item


async def apply_item_effect(user_id: int, item: Dict) -> int:
    bonus = int(item.get("item_value", 0))
    if bonus <= 0:
        return 0
    async with DB_WRITE_LOCK:
        db = await connect_sqlite()
        try:
            cur = await db.execute(
                "SELECT prize_bonus_percent FROM user_effects WHERE user_id = ?",
                (user_id,),
            )
            row = await cur.fetchone()
            current = int(row[0]) if row else 0
            updated = current + bonus
            await db.execute(
                "INSERT INTO user_effects (user_id, prize_bonus_percent) VALUES (?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET prize_bonus_percent = excluded.prize_bonus_percent, updated_at = CURRENT_TIMESTAMP",
                (user_id, updated),
            )
            await db.commit()
        finally:
            await db.close()
    return updated


async def get_prize_bonus_percent(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT prize_bonus_percent FROM user_effects WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return int(row[0]) if row else 0
