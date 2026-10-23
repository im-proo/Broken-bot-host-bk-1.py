# -*- coding: utf-8 -*-
# ──────────────────────────────────────────────────────────────────────────────
#  👑 CHAMPU MULTI-USERBOT MANAGER (usb.py)
# ──────────────────────────────────────────────────────────────────────────────
#  [CONFIGURATION]
#  API_ID / API_HASH : my.telegram.org se
#  BOT_TOKEN         : @BotFather se
# ──────────────────────────────────────────────────────────────────────────────

API_ID = 35372184
API_HASH = "f50bff5d1b5c1e9bda29e3ad8f190903"
BOT_TOKEN = "8771631600:AAEOtxPKcBA5L5xMMhpotu39vk8RVn9OmEI"

# ──────────────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────────────
#  AUTO-INSTALL: telethon + pyaes (host ke wheelhouse me pyaes nahi hota)
# ──────────────────────────────────────────────────────────────────────────────
import os as _os, sys as _sys, subprocess as _sp

_LIBS = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "_libs")
_os.makedirs(_LIBS, exist_ok=True)
if _LIBS not in _sys.path:
    _sys.path.insert(0, _LIBS)

def _ensure_telethon():
    try:
        import pyaes, rsa, telethon  # noqa
        return
    except ImportError:
        pass
    print("[SETUP] telethon/pyaes install ho raha hai...")
    cmd = [_sys.executable, "-m", "pip", "install", "--no-deps", "--quiet",
           "--disable-pip-version-check", "--target", _LIBS,
           "telethon", "pyaes", "rsa", "pyasn1"]
    try:
        _sp.check_call(cmd, env={k: v for k, v in _os.environ.items()
                                 if k not in ("PIP_NO_INDEX", "PIP_FIND_LINKS")})
    except Exception as _e:
        print(f"[SETUP ERROR] Install fail: {_e}")
        _sys.exit(1)

def _ensure_others():
    need = []
    for _mod, _pkg in (("requests", "requests"), ("aiohttp", "aiohttp"),
                       ("qrcode", "qrcode"), ("PIL", "pillow"),
                       ("gtts", "gTTS"), ("yt_dlp", "yt-dlp")):
        try:
            __import__(_mod)
        except ImportError:
            need.append(_pkg)
    if not need:
        return
    print(f"[SETUP] install ho raha hai: {', '.join(need)}")
    cmd = [_sys.executable, "-m", "pip", "install", "--quiet",
           "--disable-pip-version-check", "--target", _LIBS] + need
    try:
        _sp.check_call(cmd, env={k: v for k, v in _os.environ.items()
                                 if k not in ("PIP_NO_INDEX", "PIP_FIND_LINKS")})
    except Exception as _e:
        print(f"[SETUP ERROR] Install fail: {_e}")
        _sys.exit(1)

_ensure_telethon()
_ensure_others()

#BY YORICHI & TheChampu

# ────────────────────────────────────────────────
#                 STANDARD LIB
# ────────────────────────────────────────────────
import asyncio
import os
import time
import json
import random
import logging
logging.getLogger("telethon").setLevel(logging.CRITICAL)  # connection-reset spam band
import traceback
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Set, Optional
from io import BytesIO

# ────────────────────────────────────────────────
#                 THIRD PARTY
# ────────────────────────────────────────────────
import requests
import qrcode
from gtts import gTTS
import yt_dlp

# ────────────────────────────────────────────────
#                 TELETHON
# ────────────────────────────────────────────────
from telethon import TelegramClient, events, functions, types
# Newer telethon versions expose a different `types`/`functions`; force the raw TL ones
from telethon.tl import types, functions
from telethon import Button
from telethon.errors import (
    FloodWaitError, RPCError,
    SessionPasswordNeededError, PhoneCodeInvalidError,
    PhoneCodeExpiredError, PasswordHashInvalidError
)
from telethon.sessions import StringSession
import contextvars

# ────────────────────────────────────────────────
#                 BASIC PATH SETUP
# ────────────────────────────────────────────────
BASE_DIR = os.getcwd()

DOWNLOAD_PATH = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOAD_PATH, exist_ok=True)

TEMP_PATH = os.path.join(BASE_DIR, "temp")
os.makedirs(TEMP_PATH, exist_ok=True)

# ────────────────────────────────────────────────
#                 USERBOT & BOT CONFIG
# ────────────────────────────────────────────────
# ────────────────────────────────────────────────
#                 DYNAMIC CONFIGURATION
# ────────────────────────────────────────────────
try:
    _raw_api_id = globals().get("_OUTER_API_ID") or globals().get("API_ID") or 35372184
    API_ID = int(_raw_api_id)
except Exception:
    API_ID = 35372184

API_HASH = "f50bff5d1b5c1e9bda29e3ad8f190903"
BOT_TOKEN = str(globals().get("_OUTER_BOT_TOKEN") or globals().get("BOT_TOKEN") or "").strip()

# ⭐ Master Owner Telegram User ID
OWNER_ID = 7839813581
SESSION = "itsMyUserbot"

# ────────────────────────────────────────────────
#           MULTI-CLIENT PROXY ENGINE
# ────────────────────────────────────────────────
current_client_var: contextvars.ContextVar[Optional[TelegramClient]] = contextvars.ContextVar("current_client", default=None)
ACTIVE_CLIENTS: Dict[int, TelegramClient] = {}
primary_client: Optional[TelegramClient] = None

class TelethonClientProxy:
    def __getattr__(self, name):
        cl = current_client_var.get()
        if cl is None:
            cl = primary_client
        if cl is None and ACTIVE_CLIENTS:
            cl = next(iter(ACTIVE_CLIENTS.values()))
        if cl is None:
            raise RuntimeError("No active userbot client available")
        return getattr(cl, name)

    def __call__(self, *args, **kwargs):
        cl = current_client_var.get()
        if cl is None:
            cl = primary_client
        if cl is None and ACTIVE_CLIENTS:
            cl = next(iter(ACTIVE_CLIENTS.values()))
        if cl is None:
            raise RuntimeError("No active userbot client available")
        return cl(*args, **kwargs)

# Universal client proxy used by all 50+ userbot commands
bot = TelethonClientProxy()

# Manager bot client (started with BOT_TOKEN)
manager_bot = TelegramClient(
    StringSession(),
    API_ID,
    API_HASH,
    auto_reconnect=True,
    connection_retries=10,
    retry_delay=3,
)

# Multi-user sessions directory & storage
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)
USERS_DB_FILE = os.path.join(SESSIONS_DIR, "users.json")

def load_saved_users() -> dict:
    if not os.path.isfile(USERS_DB_FILE):
        return {}
    try:
        with open(USERS_DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def save_user_session(uid: int, data: dict):
    try:
        users = load_saved_users()
        users[str(uid)] = data
        with open(USERS_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[SAVE USER SESSION ERROR] {e}")

def remove_user_session(uid: int):
    try:
        users = load_saved_users()
        users.pop(str(uid), None)
        with open(USERS_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[REMOVE USER SESSION ERROR] {e}")

# ────────────────────────────────────────────────
#                 STORAGE FILES
# ────────────────────────────────────────────────
ADMINS_FILE = "admins.json"
NOTES_FILE = "notes.json"
BANNER_FILE = "banner_msg_id.txt"

# ────────────────────────────────────────────────
#                 CLONE ENGINE STATE
# ────────────────────────────────────────────────
CLONE_ACTIVE: bool = False
LAST_CLONE_ID: Optional[int] = None

CLONE_DATA: Dict[str, Optional[object]] = {
    "name": None,
    "username": None,
    "bio": None,
    "photo_bytes": None,
}

# ────────────────────────────────────────────────
#                 RUNTIME STATE
# ────────────────────────────────────────────────
admins: Set[int] = set()
notes: Dict[int, str] = {}

menu_banner_msg: Optional[tuple] = None
auto_react_emoji: Optional[str] = None

muted_users: Set[int] = set()
global_muted: Set[int] = set()

reply_users: Set[int] = set()
rr_users: Set[int] = set()
flag_users: Set[int] = set()
hrr_users: Set[int] = set()
replygod_users: Set[int] = set()

replyyorichi_users: Dict[int, Dict[str, object]] = {}

spray_tasks: Dict[int, asyncio.Task] = {}

group_locks: Set[int] = set()

START_TIME = time.time()

SPRAY_DELAY = 5

# ────────────────────────────────────────────────
#                 BOT ADD ENGINE
# ────────────────────────────────────────────────
ADD_BOTS_LIST = [
]

# ────────────────────────────────────────────────
#                 FASTGC ENGINE STATE
# ────────────────────────────────────────────────
FASTGC_STATE: Dict[str, Optional[object]] = {
    "active": False,
    "template": None,
    "task": None,
    "chat_id": None,
}

GC_FAST_INTERVAL = 1

GC_FAST_EMOJIS = [
    "❤️","🧡","💛","💚","💙","💜",
    "🖤","🤍","🤎","🩷","🩵","🩶",
    "💖","💘","💝","💗","💓","💞",
    "💕","💟","❣️","❤️‍🔥","❤️‍🩹"
]

# ────────────────────────────────────────────────
#                   HELPERS
# ────────────────────────────────────────────────
# ================= ADMIN STORAGE =================

def load_admins():
    global admins
    try:
        if not os.path.isfile(ADMINS_FILE):
            admins = set()
            return

        with open(ADMINS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        clean = set()

        if isinstance(data, list):
            for x in data:
                try:
                    clean.add(int(x))
                except:
                    continue

        admins = clean

    except Exception as e:
        print(f"[LOAD ADMINS ERROR] {str(e)[:80]}")
        admins = set()


def save_admins():
    try:
        tmp = sorted(set(int(x) for x in admins))
        with open(ADMINS_FILE, "w", encoding="utf-8") as f:
            json.dump(tmp, f, indent=2)
    except Exception as e:
        print(f"[SAVE ADMINS ERROR] {str(e)[:80]}")


def is_admin(uid: int) -> bool:
    if not uid:
        return False
    return uid == OWNER_ID or uid in admins


# ================= SAFE EDIT =================

async def safe_edit(event, text: str):

    if not text:
        return

    try:
        return await event.edit(text)

    except Exception:

        try:
            msg = await event.reply(text)
        except:
            return

        try:
            if event.out:
                await event.delete()
        except:
            pass

        return msg


# ================= NOTES STORAGE =================

def load_notes():
    global notes
    try:
        if not os.path.isfile(NOTES_FILE):
            notes = {}
            return

        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)

        clean = {}

        if isinstance(raw, dict):
            for k, v in raw.items():
                try:
                    clean[int(k)] = str(v)
                except:
                    continue

        notes = clean

    except Exception as e:
        print(f"[LOAD NOTES ERROR] {str(e)[:80]}")
        notes = {}


def save_notes():
    try:
        with open(NOTES_FILE, "w", encoding="utf-8") as f:
            json.dump(notes, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[SAVE NOTES ERROR] {str(e)[:80]}")


# ================= MENU BANNER STORAGE =================

def load_banner():
    global menu_banner_msg
    try:
        if not os.path.isfile(BANNER_FILE):
            menu_banner_msg = None
            return

        with open(BANNER_FILE, "r", encoding="utf-8") as f:
            raw = f.read().strip()

        if ":" not in raw:
            menu_banner_msg = None
            return

        chat, msg = raw.split(":", 1)

        menu_banner_msg = (int(chat), int(msg))

    except Exception as e:
        print(f"[LOAD BANNER ERROR] {str(e)[:80]}")
        menu_banner_msg = None


def save_banner():
    try:
        if not menu_banner_msg:
            if os.path.isfile(BANNER_FILE):
                os.remove(BANNER_FILE)
            return

        with open(BANNER_FILE, "w", encoding="utf-8") as f:
            f.write(f"{menu_banner_msg[0]}:{menu_banner_msg[1]}")

    except Exception as e:
        print(f"[SAVE BANNER ERROR] {str(e)[:80]}")


# ───── UNIVERSAL TARGET RESOLVER ─────
async def get_targets(event, arg: str = "") -> Set[int]:

    targets: Set[int] = set()

    # ⭐ reply resolver
    if event.is_reply:
        try:
            reply = await event.get_reply_message()
            if reply and reply.sender_id:
                targets.add(int(reply.sender_id))
        except:
            pass

    # ⭐ argument resolver
    if arg:
        for part in arg.strip().split():

            if not part:
                continue

            if part.isdigit():
                try:
                    targets.add(int(part))
                    continue
                except:
                    pass

            try:
                ent = await bot.get_entity(part)
                if ent and getattr(ent, "id", None):
                    targets.add(int(ent.id))
            except:
                pass

    # ⭐ self protection
    try:
        me = await bot.get_me()
        targets.discard(me.id)
    except:
        pass

    return targets


# ⭐ INITIAL LOAD
load_admins()
load_notes()
load_banner()
# ────────────────────────────────────────────────
#                   TEXT LISTS (Unchanged)
# ────────────────────────────────────────────────
reply_list = ["𝐊ʏᴀ 𝐑ᴇ 𝐑ᴀɴᴅɪᴋᴇ 𝐂ᴏᴏʟ 𝐁ᴀɴᴇɢᴀ 𝐓ᴜ 𝐂ʜᴀʟ 𝐀ʙ 𝐂ʜᴜᴅ 𝐀ᴘɴᴇ 𝐁ᴀᴀᴘ 𝐂ʜᴀᴍᴘᴜ 𝐒ᴇ - 🦢💘",
    "𝐊ɪ 𝐌ᴀᴀ 𝐌ᴀʀʀ 𝐆ᴀʏɪ 𝐘ᴀᴀʀ - 𝐉ᴀɪ 𝐂ʜᴀᴍᴘᴜ ! 🌙",
    "acha beta 😂🔥👊🏻 ? coi na me toh HATER codunga 😹💔🔥😆👊🏻💥",
    "chudke bhaga kaise 😂💥🤣🤘🏻",
    "ne toh 𝐂ʜᴀᴍᴘᴜ ka lun muh me lelia 😂🙏🏻😂🙏🏻",
    "try maa सूर्य☀ nikalte hi pel du 😹🔥💔",
    "mkl lun te vaj 😂✊🏻💦",
    "𝗧ᴍᴋ𝗕 pe 𝐂ʜᴀᴍᴘᴜ ka hamla 😂⚔🔥💥",
    "𝐂ʜʟ 𝐇ᴀʀᴍᴢᴀᴅ𝐈 𝐊ᴇ लड़के 💛🤍🩵",
    "oi 𝐓ᴇʀɪ 𝐌‌ᴀᴀ गुलाम ₰🖤",
    "chl rndyce chud ke dikha 😂💥🤣🔥",
    "𝐊ɪ 𝐌ᴀᴀ 𝐌ᴀʀʀ 𝐆ᴀʏɪ naacho 💃🏻💃🏻🕺🏻🎶😂😆💞🔥 !",
    "tera baap bass 𝐂ʜᴀᴍᴘᴜ hai 😂🎀",
    " try maa hagte hue paad mari -#😹🔥🥀",
    "  𝐓ᴇʀɪ 𝐌ᴜᴍᴍʏ 𝐂ʜᴏᴅ 𝐃ɪ 𝐂ʜᴀᴍᴘᴜ 𝐍ᴇ 𝐁ᴡᴀʜᴀʜᴀʜᴀ ⚜","𝐊ʏᴀ 𝐑ᴇ 𝐑ᴀɴᴅɪᴋᴇ 𝐂ᴏᴏʟ 𝐁ᴀɴᴇɢᴀ 𝐓ᴜ 𝐂ʜᴀʟ 𝐀ʙ 𝐂ʜᴜᴅ 𝐀ᴘɴᴇ 𝐁ᴀᴀᴘ 𝐂ʜᴀᴍᴘᴜ 𝐒ᴇ - 🦢💘",
    "𝐊ɪ 𝐌ᴀᴀ 𝐌ᴀʀʀ 𝐆ᴀʏɪ 𝐘ᴀᴀʀ - 𝐉ᴀɪ 𝐂ʜᴀᴍᴘᴜ ! 🌙",
    "acha beta 😂🔥👊🏻 ? coi na me toh HATER codunga 😹💔🔥😆👊🏻💥",
    "chudke bhaga kaise 😂💥🤣🤘🏻",
    "ne toh 𝐂ʜᴀᴍᴘᴜ ka lun muh me lelia 😂🙏🏻😂🙏🏻",
    "try maa सूर्य☀ nikalte hi pel du 😹🔥💔",
    "mkl lun te vaj 😂✊🏻💦",
    "𝗧ᴍᴋ𝗕 pe 𝐂ʜᴀᴍᴘᴜ ka hamla 😂⚔🔥💥",
    "𝐂ʜʟ 𝐇ᴀʀᴍᴢᴀᴅ𝐈 𝐊ᴇ लड़के 💛🤍🩵",
    "oi 𝐓ᴇʀɪ 𝐌‌ᴀᴀ गुलाम ₰🖤",
    "chl rndyce chud ke dikha 😂💥🤣🔥",
    "𝐊ɪ 𝐌ᴀᴀ 𝐌ᴀʀʀ 𝐆ᴀʏɪ naacho 💃🏻💃🏻🕺🏻🎶😂😆💞🔥 !",
    "tera baap bass 𝐂ʜᴀᴍᴘᴜ hai 😂🎀",
    " try maa hagte hue paad mari -#😹🔥🥀",
    "  𝐓ᴇʀɪ 𝐌ᴜᴍᴍʏ 𝐂ʜᴏᴅ 𝐃ɪ 𝐂ʜᴀᴍᴘᴜ 𝐍ᴇ 𝐁ᴡᴀʜᴀʜᴀʜᴀ ⚜"]

reply_texts = ["⋆｡ﾟ☁︎｡𝐂ʏᴜ 𝐑ᴇ मदरचोद 𝐂ʜᴀᴍᴘᴜ बाप के सामने 𝐅ʏᴛᴇʀ 𝐁ᴀɴᴇɢᴀ ⋆𓂃 ོ☼𓂃 😂🔥",
"नहीं नहीं तेरी मां को 𝐒ɪʀғ 𝐂ʜᴀᴍᴘᴜ बाप चोद सकता है ִֶָ𓂃 ࣪ ִֶָ👑་༘࿐ sᴀᴍᴊʜᴀ ʀᴀɴᴅɪᴋᴇ ???",
"तेरी मां का 𝐒ᴛʏʟɪsʜ भोसड़ा 😱",
"𝑻𝒆𝒓𝒚 𝒎𝒂𝒂 𝒓𝒂𝒏𝒅𝒂𝒍 𝒉 𝒃𝒂𝒔 𝒃𝒂𝒂𝒕 𝒌𝒉𝒂𝒕𝒂𝒎 😡🔥",
"सोच तेरी बहन को 𝐂ʜᴀᴍᴘᴜ बाप का गुलाम चोद रहा 😎🔥",
"Hello hello?? Oxygen aarahi है? रण्डी पुत्र 🧘🏻",
"Shut up रंडीके वरना दुनिया यही बोलेगी तेरी बहन 𝐂ʜᴀᴍᴘᴜ /\\~ 👑 बाप से सही chudi 🥵🔥",
"ᴛᴜ ᴏʀ ᴛᴇʀɪ ᴍᴀᴀ ᴅᴏɴᴏ 𝐂ʜᴀᴍᴘᴜ बाप के ʟɴᴅ sᴇ ᴋᴀʙʜɪ ᴜᴛʜ ɴʜɪ ᴘᴀʏᴇ 😂🔥",
"🇮🇳𝐵𝐻𝐴𝑅𝐴𝑇 𝐻𝐴𝑀𝐴𝑅𝐴 𝐷𝐸𝑆𝐻 𝐻 𝐴𝑈𝑅 𝑈𝑆 𝐷𝐸𝑆𝐻 𝑀𝐸 तेरी मां घर घर जाके MOAN करती है ! 🛐","⋆｡ﾟ☁︎｡𝐂ʏᴜ 𝐑ᴇ मदरचोद 𝐂ʜᴀᴍᴘᴜ बाप के सामने 𝐅ʏᴛᴇʀ 𝐁ᴀɴᴇɢᴀ ⋆𓂃 ོ☼𓂃 😂🔥",
"नहीं नहीं तेरी मां को 𝐒ɪʀғ 𝐂ʜᴀᴍᴘᴜ बाप चोद सकता है ִֶָ𓂃 ࣪ ִֶָ👑་༘࿐ sᴀᴍᴊʜᴀ ʀᴀɴᴅɪᴋᴇ ???",
"तेरी मां का 𝐒ᴛʏʟɪsʜ भोसड़ा 😱",
"𝑻𝒆𝒓𝒚 𝒎𝒂𝒂 𝒓𝒂𝒏𝒅𝒂𝒍 𝒉 𝒃𝒂𝒔 𝒃𝒂𝒂𝒕 𝒌𝒉𝒂𝒕𝒂𝒎 😡🔥",
"सोच तेरी बहन को 𝐂ʜᴀᴍᴘᴜ बाप का गुलाम चोद रहा 😎🔥",
"Hello hello?? Oxygen aarahi है? रण्डी पुत्र 🧘🏻",
"Shut up रंडीके वरना दुनिया यही बोलेगी तेरी बहन 𝐂ʜᴀᴍᴘᴜ /\\~ 👑 बाप से सही chudi 🥵🔥",
"ᴛᴜ ᴏʀ ᴛᴇʀɪ ᴍᴀᴀ ᴅᴏɴᴏ 𝐂ʜᴀᴍᴘᴜ बाप के ʟɴᴅ sᴇ ᴋᴀʙʜɪ ᴜᴛʜ ɴʜɪ ᴘᴀʏᴇ 😂🔥",
"🇮🇳𝐵𝐻𝐴𝑅𝐴𝑇 𝐻𝐴𝑀𝐴𝑅𝐴 𝐷𝐸𝑆𝐻 𝐻 𝐴𝑈𝑅 𝑈𝑆 𝐷𝐸𝑆𝐻 𝑀𝐸 तेरी मां घर घर जाके MOAN करती है ! 🛐","⋆｡ﾟ☁︎｡𝐂ʏᴜ 𝐑ᴇ मदरचोद 𝐂ʜᴀᴍᴘᴜ बाप के सामने 𝐅ʏᴛᴇʀ 𝐁ᴀɴᴇɢᴀ ⋆𓂃 ོ☼𓂃 😂🔥",
"नहीं नहीं तेरी मां को 𝐒ɪʀғ 𝐂ʜᴀᴍᴘᴜ बाप चोद सकता है ִֶָ𓂃 ࣪ ִֶָ👑་༘࿐ sᴀᴍᴊʜᴀ ʀᴀɴᴅɪᴋᴇ ???",
"तेरी मां का 𝐒ᴛʏʟɪsʜ भोसड़ा 😱",
"𝑻𝒆𝒓𝒚 𝒎𝒂𝒂 𝒓𝒂𝒏𝒅𝒂𝒍 𝒉 𝒃𝒂𝒔 𝒃𝒂𝒂𝒕 𝒌𝒉𝒂𝒕𝒂𝒎 😡🔥",
"सोच तेरी बहन को 𝐂ʜᴀᴍᴘᴜ बाप का गुलाम चोद रहा 😎🔥",
"Hello hello?? Oxygen aarahi है? रण्डी पुत्र 🧘🏻",
"Shut up रंडीके वरना दुनिया यही बोलेगी तेरी बहन 𝐂ʜᴀᴍᴘᴜ /\\~ 👑 बाप से सही chudi 🥵🔥",
"ᴛᴜ ᴏʀ ᴛᴇʀɪ ᴍᴀᴀ ᴅᴏɴᴏ 𝐂ʜᴀᴍᴘᴜ बाप के ʟɴᴅ sᴇ ᴋᴀʙʜɪ ᴜᴛʜ ɴʜɪ ᴘᴀʏᴇ 😂🔥",
"🇮🇳𝐵𝐻𝐴𝑅𝐴𝑇 𝐻𝐴𝑀𝐴𝑅𝐴 𝐷𝐸𝑆𝐻 𝐻 𝐴𝑈𝑅 𝑈𝑆 𝐷𝐸𝑆𝐻 𝑀𝐸 तेरी मां घर घर जाके MOAN करती है ! 🛐","⋆｡ﾟ☁︎｡𝐂ʏᴜ 𝐑ᴇ मदरचोद 𝐂ʜᴀᴍᴘᴜ बाप के सामने 𝐅ʏᴛᴇʀ 𝐁ᴀɴᴇɢᴀ ⋆𓂃 ོ☼𓂃 😂🔥",
"नहीं नहीं तेरी मां को 𝐒ɪʀғ 𝐂ʜᴀᴍᴘᴜ बाप चोद सकता है ִֶָ𓂃 ࣪ ִֶָ👑་༘࿐ sᴀᴍᴊʜᴀ ʀᴀɴᴅɪᴋᴇ ???",
"तेरी मां का 𝐒ᴛʏʟɪsʜ भोसड़ा 😱",
"𝑻𝒆𝒓𝒚 𝒎𝒂𝒂 𝒓𝒂𝒏𝒅𝒂𝒍 𝒉 𝒃𝒂𝒔 𝒃𝒂𝒂𝒕 𝒌𝒉𝒂𝒕𝒂𝒎 😡🔥",
"सोच तेरी बहन को 𝐂ʜᴀᴍᴘᴜ बाप का गुलाम चोद रहा 😎🔥",
"Hello hello?? Oxygen aarahi है? रण्डी पुत्र 🧘🏻",
"Shut up रंडीके वरना दुनिया यही बोलेगी तेरी बहन 𝐂ʜᴀᴍᴘᴜ /\\~ 👑 बाप से सही chudi 🥵🔥",
"ᴛᴜ ᴏʀ ᴛᴇʀɪ ᴍᴀᴀ ᴅᴏɴᴏ 𝐂ʜᴀᴍᴘᴜ बाप के ʟɴᴅ sᴇ ᴋᴀʙʜɪ ᴜᴛʜ ɴʜɪ ᴘᴀʏᴇ 😂🔥",
"🇮🇳𝐵𝐻𝐴𝑅𝐴𝑇 𝐻𝐴𝑀𝐴𝑅𝐴 𝐷𝐸𝑆𝐻 𝐻 𝐴𝑈𝑅 𝑈𝑆 𝐷𝐸𝑆𝐻 𝑀𝐸 तेरी मां घर घर जाके MOAN करती है ! 🛐"]

fun_texts = ["तेरे मां के दूदू के बीच मेरा lund fas gaya oops 🤪（ ͜.🍆 ͜.）",
"𝐓ᴇʀʏ 𝐁ʜᴇ𝐍 𝐊ᴇ ( ͜. ㅅ ͜. )🥛 ʏᴜᴍᴍʏ ",
"𓂃☁︎ 𓂃𝐒ɪᴅᴇ 𝐇ᴀᴛ 𝐆ᴜʟᴀᴍ 𝐓ᴇʀʏ 𝐌ᴀᴀ 𝐊ᴏ 𝐂ʜᴏᴅɴᴇ  मेरी रेलगाड़ी आ रही .-‘🚂-‘.ᯓᡣ𐭩______ 𓂃☁︎ 𓂃",
"˙✧˖°📷༘ ⋆｡° 𝐓ᴇʀʏ 𝐌ᴀ  𝐊ᴀ 𝐂ʜɪʟᴅ 𝐏ᴏʀɴ 𝐑ᴇᴄᴏʀᴅ 𝐇ᴏɢʏᴀ 𝐀ʙ 𝐓ᴏ 𝐒ɪᴅʜᴀ 𝐕ɪʀᴀʟ 𝐇ᴏɢᴀ 𝐘ᴇ ˙✧˖°📷༘ ⋆｡°",
"𓂃✍︎ 𝑵ʏ 𝑵ʏ 𝑨ʙ 𝑲ᴜᴄʜ 𝑵ʏ 𝑯ᴏ 𝑺ᴋᴛᴀ 𝑻ᴇʀɪ  𝑪ᴜᴅᴀɪ 𝑲ɪ 𝑺ᴄʀɪᴘᴛ 𝑨ʙ 𝑳ᴇᴀᴋ 𝑯ᴏᴋᴇ 𝑯ʏ 𝑴ᴀɴᴇɢɪ 𓂃✍︎",
"⋆⭒˚.⋆🔭 𝐒ʜᴜᴛ 𝐔ᴘ 𝐑ᴀɴᴅɪᴋᴇ 𝐓ᴇʀɪ 𝐌ᴀᴀ 𝐊ɪ 𝐂ʜᴜᴅᴀɪ 𝐄ɴᴊᴏʏ 𝐊ʀ 𝐑ᴀʜᴀ 𝐓ᴇʟᴇ𝐒ᴄᴏᴘᴇ 𝐒ᴇ⋆⭒˚.⋆🔭","तेरे मां के दूदू के बीच मेरा lund fas gaya oops 🤪（ ͜.🍆 ͜.）",
"𝐓ᴇʀʏ 𝐁ʜᴇ𝐍 𝐊ᴇ ( ͜. ㅅ ͜. )🥛 ʏᴜᴍᴍʏ ",
"𓂃☁︎ 𓂃𝐒ɪᴅᴇ 𝐇ᴀᴛ 𝐆ᴜʟᴀᴍ 𝐓ᴇʀʏ 𝐌ᴀᴀ 𝐊ᴏ 𝐂ʜᴏᴅɴᴇ  मेरी रेलगाड़ी आ रही .-‘🚂-‘.ᯓᡣ𐭩______ 𓂃☁︎ 𓂃",
"˙✧˖°📷༘ ⋆｡° 𝐓ᴇʀʏ 𝐌ᴀ  𝐊ᴀ 𝐂ʜɪʟᴅ 𝐏ᴏʀɴ 𝐑ᴇᴄᴏʀᴅ 𝐇ᴏɢʏᴀ 𝐀ʙ 𝐓ᴏ 𝐒ɪᴅʜᴀ 𝐕ɪʀᴀʟ 𝐇ᴏɢᴀ 𝐘ᴇ ˙✧˖°📷༘ ⋆｡°",
"𓂃✍︎ 𝑵ʏ 𝑵ʏ 𝑨ʙ 𝑲ᴜᴄʜ 𝑵ʏ 𝑯ᴏ 𝑺ᴋᴛᴀ 𝑻ᴇʀɪ  𝑪ᴜᴅᴀɪ 𝑲ɪ 𝑺ᴄʀɪᴘᴛ 𝑨ʙ 𝑳ᴇᴀᴋ 𝑯ᴏᴋᴇ 𝑯ʏ 𝑴ᴀɴᴇɢɪ 𓂃✍︎",
"⋆⭒˚.⋆🔭 𝐒ʜᴜᴛ 𝐔ᴘ 𝐑ᴀɴᴅɪᴋᴇ 𝐓ᴇʀɪ 𝐌ᴀᴀ 𝐊ɪ 𝐂ʜᴜᴅᴀɪ 𝐄ɴᴊᴏʏ 𝐊ʀ 𝐑ᴀʜᴀ 𝐓ᴇʟᴇ𝐒ᴄᴏᴘᴇ 𝐒ᴇ⋆⭒˚.⋆🔭","तेरे मां के दूदू के बीच मेरा lund fas gaya oops 🤪（ ͜.🍆 ͜.）",
"𝐓ᴇʀʏ 𝐁ʜᴇ𝐍 𝐊ᴇ ( ͜. ㅅ ͜. )🥛 ʏᴜᴍᴍʏ ",
"𓂃☁︎ 𓂃𝐒ɪᴅᴇ 𝐇ᴀᴛ 𝐆ᴜʟᴀᴍ 𝐓ᴇʀʏ 𝐌ᴀᴀ 𝐊ᴏ 𝐂ʜᴏᴅɴᴇ  मेरी रेलगाड़ी आ रही .-‘🚂-‘.ᯓᡣ𐭩______ 𓂃☁︎ 𓂃",
"˙✧˖°📷༘ ⋆｡° 𝐓ᴇʀʏ 𝐌ᴀ  𝐊ᴀ 𝐂ʜɪʟᴅ 𝐏ᴏʀɴ 𝐑ᴇᴄᴏʀᴅ 𝐇ᴏɢʏᴀ 𝐀ʙ 𝐓ᴏ 𝐒ɪᴅʜᴀ 𝐕ɪʀᴀʟ 𝐇ᴏɢᴀ 𝐘ᴇ ˙✧˖°📷༘ ⋆｡°",
"𓂃✍︎ 𝑵ʏ 𝑵ʏ 𝑨ʙ 𝑲ᴜᴄʜ 𝑵ʏ 𝑯ᴏ 𝑺ᴋᴛᴀ 𝑻ᴇʀɪ  𝑪ᴜᴅᴀɪ 𝑲ɪ 𝑺ᴄʀɪᴘᴛ 𝑨ʙ 𝑳ᴇᴀᴋ 𝑯ᴏᴋᴇ 𝑯ʏ 𝑴ᴀɴᴇɢɪ 𓂃✍︎",
"⋆⭒˚.⋆🔭 𝐒ʜᴜᴛ 𝐔ᴘ 𝐑ᴀɴᴅɪᴋᴇ 𝐓ᴇʀɪ 𝐌ᴀᴀ 𝐊ɪ 𝐂ʜᴜᴅᴀɪ 𝐄ɴᴊᴏʏ 𝐊ʀ 𝐑ᴀʜᴀ 𝐓ᴇʟᴇ𝐒ᴄᴏᴘᴇ 𝐒ᴇ⋆⭒˚.⋆🔭","तेरे मां के दूदू के बीच मेरा lund fas gaya oops 🤪（ ͜.🍆 ͜.）",
"𝐓ᴇʀʏ 𝐁ʜᴇ𝐍 𝐊ᴇ ( ͜. ㅅ ͜. )🥛 ʏᴜᴍᴍʏ ",
"𓂃☁︎ 𓂃𝐒ɪᴅᴇ 𝐇ᴀᴛ 𝐆ᴜʟᴀᴍ 𝐓ᴇʀʏ 𝐌ᴀᴀ 𝐊ᴏ 𝐂ʜᴏᴅɴᴇ  मेरी रेलगाड़ी आ रही .-‘🚂-‘.ᯓᡣ𐭩______ 𓂃☁︎ 𓂃",
"˙✧˖°📷༘ ⋆｡° 𝐓ᴇʀʏ 𝐌ᴀ  𝐊ᴀ 𝐂ʜɪʟᴅ 𝐏ᴏʀɴ 𝐑ᴇᴄᴏʀᴅ 𝐇ᴏɢʏᴀ 𝐀ʙ 𝐓ᴏ 𝐒ɪᴅʜᴀ 𝐕ɪʀᴀʟ 𝐇ᴏɢᴀ 𝐘ᴇ ˙✧˖°📷༘ ⋆｡°",
"𓂃✍︎ 𝑵ʏ 𝑵ʏ 𝑨ʙ 𝑲ᴜᴄʜ 𝑵ʏ 𝑯ᴏ 𝑺ᴋᴛᴀ 𝑻ᴇʀɪ  𝑪ᴜᴅᴀɪ 𝑲ɪ 𝑺ᴄʀɪᴘᴛ 𝑨ʙ 𝑳ᴇᴀᴋ 𝑯ᴏᴋᴇ 𝑯ʏ 𝑴ᴀɴᴇɢɪ 𓂃✍︎",
"⋆⭒˚.⋆🔭 𝐒ʜᴜᴛ 𝐔ᴘ 𝐑ᴀɴᴅɪᴋᴇ 𝐓ᴇʀɪ 𝐌ᴀᴀ 𝐊ɪ 𝐂ʜᴜᴅᴀɪ 𝐄ɴᴊᴏʏ 𝐊ʀ 𝐑ᴀʜᴀ 𝐓ᴇʟᴇ𝐒ᴄᴏᴘᴇ 𝐒ᴇ⋆⭒˚.⋆🔭" ]

flag_texts = [" ོ༘₊⁺🇮🇳 ₊⁺⋆.˚ 𝐓ᴇʀɪ 𝐌ᴀᴀ 𝐊ᴇ 𝐒ᴀᴛʜ 𝐂ʜᴀᴍᴘᴜ 𝐁ᴀᴀᴘ 𝐀ᴜʀ  𝐈ɴᴅɪᴀ 𝐖ᴀʟᴇ 𝐁ʜɪ 𝐂ʜɪʟʟ 𝐊ᴀʀ 𝐑ʜᴇ ོ༘₊⁺🇮🇳 ₊⁺⋆.˚",
" ོ༘₊⁺🇯🇵 ₊⁺⋆.˚ 𝐓ᴇʀɪ 𝐌ᴀᴀ 𝐊ᴇ 𝐒ᴀᴛʜ  𝐂ʜᴀᴍᴘᴜ 𝐁ᴀᴀᴘ 𝐀ᴜʀ 𝐉ᴀᴘᴀɴ 𝐖ᴀʟᴇ 𝐁ʜɪ 𝐂ʜɪʟʟ 𝐊ᴀʀ 𝐑ʜᴇ ོ༘₊⁺🇯🇵 ₊⁺⋆. " ,
" ₊⁺🇺🇸 ₊⁺⋆.˚ 𝐓ᴇʀɪ 𝐌ᴀᴀ 𝐊ᴇ 𝐒ᴀᴛʜ  𝐂ʜᴀᴍᴘᴜ 𝐁ᴀᴀᴘ 𝐀ᴜʀ 𝐔𝐒𝐀 𝐖ᴀʟᴇ 𝐁ʜɪ 𝐂ʜɪʟʟ 𝐊ᴀʀ 𝐑ʜᴇ ོ༘₊⁺🇺🇸 ₊⁺⋆.˚",
" ོ༘₊⁺🇬🇧 ₊⁺⋆.˚ 𝐓ᴇʀɪ 𝐌ᴀᴀ 𝐊ᴇ 𝐒ᴀᴛʜ  𝐂ʜᴀᴍᴘᴜ 𝐁ᴀᴀᴘ 𝐀ᴜʀ 𝐔𝐊 𝐖ᴀʟᴇ 𝐁ʜɪ 𝐂ʜɪʟʟ 𝐊ᴀʀ 𝐑ʜᴇ ོ༘₊⁺🇬🇧 ₊⁺⋆.˚", 
" ོ༘₊⁺🇰🇷 ₊⁺⋆.˚𝐓ᴇʀɪ 𝐌ᴀᴀ 𝐊ᴇ 𝐒ᴀᴛʜ   𝐂ʜᴀᴍᴘᴜ 𝐁ᴀᴀᴘ 𝐀ᴜʀ 𝐊ᴏʀᴇᴀ 𝐖ᴀʟᴇ 𝐁ʜɪ 𝐂ʜɪʟʟ 𝐊ᴀʀ 𝐑ʜᴇ ོ༘₊⁺🇰🇷 ₊⁺⋆.˚",
" ོ༘₊⁺🇩🇪 ₊⁺⋆.˚ 𝐓ᴇʀɪ 𝐌ᴀᴀ 𝐊ᴇ 𝐒ᴀᴛʜ  𝐂ʜᴀᴍᴘᴜ 𝐁ᴀᴀᴘ 𝐀ᴜʀ 𝐆ᴇʀᴍᴀɴʏ 𝐖ᴀʟᴇ 𝐁ʜɪ 𝐂ʜɪʟʟ 𝐊ᴀʀ 𝐑ʜᴇ ོ༘₊⁺🇩🇪 ₊⁺⋆.˚",
" ོ༘₊⁺🇫🇷 ₊⁺⋆.˚𝐓ᴇʀɪ 𝐌ᴀᴀ 𝐊ᴇ 𝐒ᴀᴛʜ   𝐂ʜᴀᴍᴘᴜ 𝐁ᴀᴀᴘ 𝐀ᴜʀ 𝐅ʀᴀɴᴄᴇ 𝐖ᴀʟᴇ 𝐁ʜɪ 𝐂ʜɪʟʟ 𝐊ᴀʀ 𝐑ʜᴇ ོ༘₊⁺🇫🇷 ₊⁺⋆.˚",
" ོ༘₊⁺🇮🇹 ₊⁺⋆.˚ 𝐓ᴇʀɪ 𝐌ᴀᴀ 𝐊ᴇ 𝐒ᴀᴛʜ  𝐂ʜᴀᴍᴘᴜ 𝐁ᴀᴀᴘ 𝐀ᴜʀ 𝐈ᴛᴀʟʏ 𝐖ᴀʟᴇ 𝐁ʜɪ 𝐂ʜɪʟʟ 𝐊ᴀʀ 𝐑ʜᴇ ོ༘₊⁺🇮🇹 ₊⁺⋆.˚",
" ོ༘₊⁺🇧🇷 ₊⁺⋆.˚𝐓ᴇʀɪ 𝐌ᴀᴀ 𝐊ᴇ 𝐒ᴀᴛʜ   𝐂ʜᴀᴍᴘᴜ 𝐁ᴀᴀᴘ 𝐀ᴜʀ 𝐁ʀᴀᴢɪʟ 𝐖ᴀʟᴇ 𝐁ʜɪ 𝐂ʜɪʟʟ 𝐊ᴀʀ 𝐑ʜᴇ ོ༘₊⁺🇧🇷 ₊⁺⋆.˚",
" ོ༘₊⁺🇨🇦 ₊⁺⋆.˚𝐓ᴇʀɪ 𝐌ᴀᴀ 𝐊ᴇ 𝐒ᴀᴛʜ  𝐂ʜᴀᴍᴘᴜ 𝐁ᴀᴀᴘ 𝐀ᴜʀ 𝐂ᴀɴᴀᴅᴀ 𝐖ᴀʟᴇ 𝐁ʜɪ 𝐂ʜɪʟʟ 𝐊ᴀʀ 𝐑ʜᴇ ོ༘₊⁺🇨🇦 ₊⁺⋆.˚"," ོ༘₊⁺🇮🇳 ₊⁺⋆.˚ 𝐓ᴇʀɪ 𝐌ᴀᴀ 𝐊ᴇ 𝐒ᴀᴛʜ 𝐂ʜᴀᴍᴘᴜ 𝐁ᴀᴀᴘ 𝐀ᴜʀ  𝐈ɴᴅɪᴀ 𝐖ᴀʟᴇ 𝐁ʜɪ 𝐂ʜɪʟʟ 𝐊ᴀʀ 𝐑ʜᴇ ོ༘₊⁺🇮🇳 ₊⁺⋆.˚",
" ོ༘₊⁺🇯🇵 ₊⁺⋆.˚ 𝐓ᴇʀɪ 𝐌ᴀᴀ 𝐊ᴇ 𝐒ᴀᴛʜ  𝐂ʜᴀᴍᴘᴜ 𝐁ᴀᴀᴘ 𝐀ᴜʀ 𝐉ᴀᴘᴀɴ 𝐖ᴀʟᴇ 𝐁ʜɪ 𝐂ʜɪʟʟ 𝐊ᴀʀ 𝐑ʜᴇ ོ༘₊⁺🇯🇵 ₊⁺⋆. " ,
" ₊⁺🇺🇸 ₊⁺⋆.˚ 𝐓ᴇʀɪ 𝐌ᴀᴀ 𝐊ᴇ 𝐒ᴀᴛʜ  𝐂ʜᴀᴍᴘᴜ 𝐁ᴀᴀᴘ 𝐀ᴜʀ 𝐔𝐒𝐀 𝐖ᴀʟᴇ 𝐁ʜɪ 𝐂ʜɪʟʟ 𝐊ᴀʀ 𝐑ʜᴇ ོ༘₊⁺🇺🇸 ₊⁺⋆.˚",
" ོ༘₊⁺🇬🇧 ₊⁺⋆.˚ 𝐓ᴇʀɪ 𝐌ᴀᴀ 𝐊ᴇ 𝐒ᴀᴛʜ  𝐂ʜᴀᴍᴘᴜ 𝐁ᴀᴀᴘ 𝐀ᴜʀ 𝐔𝐊 𝐖ᴀʟᴇ 𝐁ʜɪ 𝐂ʜɪʟʟ 𝐊ᴀʀ 𝐑ʜᴇ ོ༘₊⁺🇬🇧 ₊⁺⋆.˚", 
" ོ༘₊⁺🇰🇷 ₊⁺⋆.˚𝐓ᴇʀɪ 𝐌ᴀᴀ 𝐊ᴇ 𝐒ᴀᴛʜ   𝐂ʜᴀᴍᴘᴜ 𝐁ᴀᴀᴘ 𝐀ᴜʀ 𝐊ᴏʀᴇᴀ 𝐖ᴀʟᴇ 𝐁ʜɪ 𝐂ʜɪʟʟ 𝐊ᴀʀ 𝐑ʜᴇ ོ༘₊⁺🇰🇷 ₊⁺⋆.˚",
" ོ༘₊⁺🇩🇪 ₊⁺⋆.˚ 𝐓ᴇʀɪ 𝐌ᴀᴀ 𝐊ᴇ 𝐒ᴀᴛʜ  𝐂ʜᴀᴍᴘᴜ 𝐁ᴀᴀᴘ 𝐀ᴜʀ 𝐆ᴇʀᴍᴀɴʏ 𝐖ᴀʟᴇ 𝐁ʜɪ 𝐂ʜɪʟʟ 𝐊ᴀʀ 𝐑ʜᴇ ོ༘₊⁺🇩🇪 ₊⁺⋆.˚",
" ོ༘₊⁺🇫🇷 ₊⁺⋆.˚𝐓ᴇʀɪ 𝐌ᴀᴀ 𝐊ᴇ 𝐒ᴀᴛʜ   𝐂ʜᴀᴍᴘᴜ 𝐁ᴀᴀᴘ 𝐀ᴜʀ 𝐅ʀᴀɴᴄᴇ 𝐖ᴀʟᴇ 𝐁ʜɪ 𝐂ʜɪʟʟ 𝐊ᴀʀ 𝐑ʜᴇ ོ༘₊⁺🇫🇷 ₊⁺⋆.˚",
" ོ༘₊⁺🇮🇹 ₊⁺⋆.˚ 𝐓ᴇʀɪ 𝐌ᴀᴀ 𝐊ᴇ 𝐒ᴀᴛʜ  𝐂ʜᴀᴍᴘᴜ 𝐁ᴀᴀᴘ 𝐀ᴜʀ 𝐈ᴛᴀʟʏ 𝐖ᴀʟᴇ 𝐁ʜɪ 𝐂ʜɪʟʟ 𝐊ᴀʀ 𝐑ʜᴇ ོ༘₊⁺🇮🇹 ₊⁺⋆.˚",
" ོ༘₊⁺🇧🇷 ₊⁺⋆.˚𝐓ᴇʀɪ 𝐌ᴀᴀ 𝐊ᴇ 𝐒ᴀᴛʜ   𝐂ʜᴀᴍᴘᴜ 𝐁ᴀᴀᴘ 𝐀ᴜʀ 𝐁ʀᴀᴢɪʟ 𝐖ᴀʟᴇ 𝐁ʜɪ 𝐂ʜɪʟʟ 𝐊ᴀʀ 𝐑ʜᴇ ོ༘₊⁺🇧🇷 ₊⁺⋆.˚",
" ོ༘₊⁺🇨🇦 ₊⁺⋆.˚𝐓ᴇʀɪ 𝐌ᴀᴀ 𝐊ᴇ 𝐒ᴀᴛʜ  𝐂ʜᴀᴍᴘᴜ 𝐁ᴀᴀᴘ 𝐀ᴜʀ 𝐂ᴀɴᴀᴅᴀ 𝐖ᴀʟᴇ 𝐁ʜɪ 𝐂ʜɪʟʟ 𝐊ᴀʀ 𝐑ʜᴇ ོ༘₊⁺🇨🇦 ₊⁺⋆.˚"]

heart_replies = ["𓂃˖˳·˖ ִֶָ ⋆❤️͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚❤️ ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆🧡͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚🧡 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆💛͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚💛 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆💚͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚💚 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆💙͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚💙 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆💜͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚💜 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆🖤͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚🖤 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆🤍͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚🤍 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆🤎͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚🤎 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆💖͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚💖 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆💗͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚💗 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆💓͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚💓 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆💞͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚💞 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆💕͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚💕 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆💘͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚💘 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆💝͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚💝 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆💟͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚💟 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆❣️͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚❣️ ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆❤️‍🔥͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚❤️‍🔥 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆❤️‍🩹͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚❤️‍🩹 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆❤️͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚❤️ ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆🧡͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚🧡 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆💛͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚💛 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆💚͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚💚 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆💙͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚💙 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆💜͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚💜 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆🖤͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚🖤 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆🤍͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚🤍 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆🤎͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚🤎 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆💖͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚💖 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆💗͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚💗 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆💓͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚💓 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆💞͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚💞 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆💕͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚💕 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆💘͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚💘 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆💝͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚💝 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆💟͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚💟 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆❣️͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚❣️ ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆❤️‍🔥͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚❤️‍🔥 ݁˖⭑.ᐟ",
"𓂃˖˳·˖ ִֶָ ⋆❤️‍🩹͙⋆ ִֶָ˖·˳˖𓂃 ִֶָ⁀➴༯ sꪶꪖꪜꫀ ִֶָ. ..𓂃 ࣪ ִֶָ🌈་༘࿐ 𝗟𝗡𝗗 𝗖𝗛𝗢𝗢𝗦 -/- ⋆˚❤️‍🩹 ݁˖⭑.ᐟ"]

# ────────────────────────────────────────────────
#                   DECORATOR
# ────────────────────────────────────────────────
# ================= COMMAND REGISTRY =================

commands = {}

def register_cmd(name: str, needs_reply: bool = False, group_only: bool = False):

    def decorator(func):

        key = (name or "").lower().strip()

        if not key:
            raise ValueError("Command name cannot be empty")

        if key in commands:
            raise ValueError(f"Duplicate command registered: {key}")

        commands[key] = {
            "func": func,
            "needs_reply": bool(needs_reply),
            "group_only": bool(group_only),
        }

        return func

    return decorator


# ================= FASTGC ENGINE =================

async def fast_title_edit(chat_id, title):

    safe_title = (title or "").strip()[:255]

    if not safe_title:
        return False

    try:
        await bot(functions.channels.EditTitleRequest(
            channel=chat_id,
            title=safe_title
        ))
        return True

    except Exception:

        try:
            await bot(functions.messages.EditChatTitleRequest(
                chat_id=chat_id,
                title=safe_title
            ))
            return True

        except Exception as e:
            print(f"[FastGC] Title edit failed → {str(e)[:80]}")
            return False


async def gc_fast_loop(chat_id):

    try:

        while True:

            # ⭐ state validation
            if not FASTGC_STATE.get("active"):
                break

            template = FASTGC_STATE.get("template")
            if not template:
                break

            try:
                emoji = random.choice(GC_FAST_EMOJIS)
            except:
                emoji = "⚡"

            try:
                new_title = template.replace("{emoji}", emoji)
            except:
                await asyncio.sleep(2)
                continue

            ok = await fast_title_edit(chat_id, new_title)

            # ⭐ adaptive delay engine
            try:
                if ok:
                    await asyncio.sleep(max(1, GC_FAST_INTERVAL))
                else:
                    await asyncio.sleep(5)
            except:
                await asyncio.sleep(3)

    except asyncio.CancelledError:
        # ⭐ silent cancel safe
        return

    except Exception as e:
        print(f"[FastGC Loop Crash] → {str(e)[:80]}")

# ────────────────────────────────────────────────
#                   MENU (STYLISH) - UNCHANGED
# ────────────────────────────────────────────────
@register_cmd("menu")
async def cmd_menu(event, _):
    global menu_banner_msg
    menu = """━━━〔 ✦ 𝐂ʜᴀᴍᴘᴜ 𝐆ᴏᴅ 𝐔sᴇʀʙᴏᴛ ✦ 〕━━━

              👑 𝐎ᴡɴᴇʀ : 𝐂ʜᴀᴍᴘᴜ 👑

╭─〔 👑 𝐀ᴅᴍɪɴ 𝐂ᴏᴍᴍᴀɴᴅs 〕─╮
➤ .𝐀ᴅᴍɪɴs → sʜᴏᴡ ᴀᴅᴍɪɴ ʟɪsᴛ  
➤ .𝐀ᴅᴅᴀᴅᴍɪɴ <reply / @id> → ᴀᴅᴅ ᴀᴅᴍɪɴ  
➤ .𝐃ᴇʟᴀᴅᴍɪɴ <reply / @id> → ʀᴇᴍᴏᴠᴇ ᴀᴅᴍɪɴ  
╰────────────────────╯

╭─〔 🔇 𝐌ᴜᴛᴇ & 𝐑ᴇsᴛʀɪᴄᴛ 〕─╮
➤ .𝐌ᴜᴛᴇ <reply / @id> → ʟᴏᴄᴀʟ ᴍᴜᴛᴇ  
➤ .𝐔ɴᴍᴜᴛᴇ <reply / @id> → ʟᴏᴄᴀʟ ᴜɴᴍᴜᴛᴇ  
➤ .𝐆ᴍᴜᴛᴇ <reply / @id> → ɢʟᴏʙᴀʟ ᴍᴜᴛᴇ  
➤ .𝐆ᴜɴᴍᴜᴛᴇ <reply / @id> → ɢʟᴏʙᴀʟ ᴜɴᴍᴜᴛᴇ  
➤ .𝐌ᴜᴛᴇʟɪsᴛ → sʜᴏᴡ ᴍᴜᴛᴇ sᴛᴀᴛᴜs  
➤ .𝐋ᴏᴄᴋ → ʟᴏᴄᴋ ɢʀᴏᴜᴘ  
➤ .𝐔ɴʟᴏᴄᴋ → ᴜɴʟᴏᴄᴋ ɢʀᴏᴜᴘ  
╰────────────────────╯

╭─〔 🧹 𝐆ʀᴏᴜᴘ 𝐌ᴏᴅ 〕─╮
➤ .𝐏ᴜʀɢᴇ <count> → ᴅᴇʟᴇᴛᴇ ᴍᴇssᴀɢᴇs  
➤ .𝐓ʜʀᴏᴡ <reply / @id> → ᴋɪᴄᴋ ᴜsᴇʀ  
➤ .𝐀ᴅᴅʙᴏᴛs <number> → ᴀᴅᴅ ʏᴏʀɪᴄʜɪ ʙᴏᴛs  
╰────────────────────╯

╭─〔 ⚔️ 𝐑ᴀɪᴅ 𝐄ɴɢɪɴᴇ 〕─╮
➤ .𝐑ᴇᴘʟʏ <reply / @id> → sᴛᴀʀᴛ ʀᴇᴘʟʏ ʀᴀɪᴅ  
➤ .𝐒ʀᴇᴘʟʏ <reply / @id> → sᴛᴏᴘ ʀᴇᴘʟʏ ʀᴀɪᴅ  
➤ .𝐑ʀ <reply / @id> → ʀʀ + 🤣 ʀᴇᴀᴄᴛ  
➤ .𝐒ʀʀ <reply / @id> → sᴛᴏᴘ ʀʀ  
➤ .𝐅ʟᴀɢ <reply / @id> → ғʟᴀɢ ʀᴀɪᴅ  
➤ .𝐒ғʟᴀɢ <reply / @id> → sᴛᴏᴘ ғʟᴀɢ  
➤ .𝐇ʀʀ <reply / @id> → ʜᴇᴀʀᴛ ʀᴀɪᴅ  
➤ .𝐒ʜʀʀ <reply / @id> → sᴛᴏᴘ ʜᴇᴀʀᴛ  
➤ .𝐑ᴇᴘʟʏɢᴏᴅ <reply / @id> → ɢᴏᴅ ʀᴀɪᴅ  
➤ .𝐒ɢᴏᴅ <reply / @id> → sᴛᴏᴘ ɢᴏᴅ  
➤ .𝐑ᴇᴘʟʏʏᴏʀɪᴄʜɪ <text> <count> → ʟɪᴍɪᴛ ʀᴀɪᴅ  
➤ .𝐒ʏᴏʀɪᴄʜɪ <reply / @id> → sᴛᴏᴘ ʟɪᴍɪᴛ  
╰────────────────────╯

╭─〔 💣 𝐒ᴘᴀᴍ & ⚡ 𝐅ᴀsᴛ 〕─╮
➤ .𝐒ᴘʀᴀʏ <text> → sᴛᴀʀᴛ sᴘᴀᴍ  
➤ .𝐃sᴘʀᴀʏ → sᴛᴏᴘ sᴘᴀᴍ  
➤ .𝐅ᴀsᴛɢᴄ sᴇᴛ <template {emoji}> → ғᴀsᴛ ᴛɪᴛʟᴇ  
➤ .𝐅ᴀsᴛɢᴄ sᴛᴏᴘ → sᴛᴏᴘ ғᴀsᴛ  
╰────────────────────╯

╭─〔 ❤️ 𝐀ᴜᴛᴏ 𝐒ʏsᴛᴇᴍ 〕─╮
➤ .𝐀ʀ <emoji> → ᴀᴜᴛᴏ ʀᴇᴀᴄᴛ  
➤ .𝐒ᴀʀ → sᴛᴏᴘ ᴀᴜᴛᴏ ʀᴇᴀᴄᴛ  
╰────────────────────╯

╭─〔 👤 𝐏ʀᴏғɪʟᴇ 𝐒ʏsᴛᴇᴍ 〕─╮
➤ .𝐂ᴏᴘʏ <reply / @id> → ᴄʟᴏɴᴇ ᴘʀᴏғɪʟᴇ  
➤ .𝐍ᴏʀᴍᴀʟ → ʀᴇsᴛᴏʀᴇ ᴏʀɪɢɪɴᴀʟ ᴘʀᴏғɪʟᴇ  
╰────────────────────╯

╭─〔 🛠️ 𝐓ᴏᴏʟ𝐬 〕─╮
➤ .𝐓ᴛs <text> → ᴠᴏɪᴄᴇ ᴍsɢ  
➤ .𝐐ʀᴄᴏᴅᴇ <text> → ɢᴇɴᴇʀᴀᴛᴇ ǫʀ  
➤ .𝐅ᴀɴᴄʏ <text> → ғᴀɴᴄʏ sᴛʏʟᴇ  
➤ .𝐒ᴛʏʟᴇ <text> → ᴛᴇxᴛ ғᴏʀᴍᴀᴛ  
➤ .𝐄ᴍᴏᴊɪ <text> → ᴇᴍᴏᴊɪ sᴛʏʟᴇ  
➤ .𝐂ᴀʟᴄ <expression> → ᴄᴀʟᴄᴜʟᴀᴛᴏʀ  
➤ .𝐖ᴇᴀᴛʜᴇʀ <city> → ᴡᴇᴀᴛʜᴇʀ ʀᴇᴘᴏʀᴛ  
➤ .𝐈ᴘ <ip> → ɪᴘ ʟᴏᴏᴋᴜᴘ  
➤ .𝐒ʜᴏʀᴛ <url> → sʜᴏʀᴛ ʟɪɴᴋ  
➤ .𝐌ᴜsɪᴄ <song> → ᴅᴏᴡɴʟᴏᴀᴅ ᴍᴜsɪᴄ  
╰────────────────────╯

╭─〔 🧠 𝐍ᴏᴛᴇs 〕─╮
➤ .𝐍ᴏᴛᴇsᴀᴅᴅ <text> → sᴀᴠᴇ ɴᴏᴛᴇ  
➤ .𝐍ᴏᴛᴇsʟɪsᴛ → ʟɪsᴛ ɴᴏᴛᴇs  
➤ .𝐍ᴏᴛᴇsᴅᴇʟᴇᴛᴇ <id> → ᴅᴇʟᴇᴛᴇ ɴᴏᴛᴇ  
╰────────────────────╯

╭─〔 🎮 𝐅ᴜɴ 〕─╮
➤ .𝐏ɪɴɢ → ᴄʜᴇᴄᴋ ʟᴀᴛᴇɴᴄʏ  
➤ .𝐒ᴛᴀᴛᴜs → ᴜsᴇʀʙᴏᴛ sᴛᴀᴛᴜs  
➤ .𝐅ʟɪᴘ → ᴄᴏɪɴ ғʟɪᴘ  
➤ .𝐃ɪᴄᴇ → ʀᴏʟʟ ᴅɪᴄᴇ  
➤ .𝐈ɴғᴏ <reply / @id> → ᴜsᴇʀ ɪɴғᴏ  
╰────────────────────╯

╭─〔 ⚔️ 𝐁ᴀᴋᴀ 𝐆ᴀᴍᴇ 〕─╮
➤ .𝐁ᴀᴋᴀ → ᴀᴜᴛᴏ ᴋɪʟʟ + ʀᴏʙ ᴀʟʟ ᴀᴄᴛɪᴠᴇ  
➤ .𝐁ᴀᴋᴀʀᴏʙ → sᴛᴇᴀʟᴛʜ ʀᴏʙ (ɴᴏ ᴋɪʟʟs)  
➤ .𝐁ᴀᴋᴀᴋɪʟʟ → ᴋɪʟʟ ᴏɴʟʏ ʀᴀɪᴅ  
➤ .𝐁ᴀᴋᴀʙᴀʟ <reply/@id> → ᴄʜᴇᴄᴋ ʙᴀʟᴀɴᴄᴇ  
➤ .𝐒ᴛᴏᴘʙᴀᴋᴀ → ɪɴsᴛᴀɴᴛʟʏ sᴛᴏᴘ ʀᴀɪᴅ  
➤ .𝐁ᴀᴋᴀsᴛᴀᴛs → ʟᴀsᴛ ʀᴀɪᴅ sᴛᴀᴛs  
╰────────────────────╯

╭─〔 🖼️ 𝐁ᴀɴɴᴇʀ 〕─╮
➤ .𝐁ᴀɴɴᴇʀ <reply media> → sᴇᴛ ᴍᴇɴᴜ ʙᴀɴɴᴇʀ  
➤ .𝐑ᴇᴍʙᴀɴɴᴇʀ → ʀᴇᴍᴏᴠᴇ ʙᴀɴɴᴇʀ  
╰────────────────────╯

✦━━━━━━━━━━━━━━━━━━━━✦
🔥 𝐏ᴏᴡᴇʀᴇᴅ ʙʏ 𝐂ʜᴀᴍᴘᴜ 🔥
✦━━━━━━━━━━━━━━━━━━━━✦"""

    await safe_edit(event, menu)
    
    if menu_banner_msg:
        chat_id, msg_id = menu_banner_msg
        try:
            msg = await bot.get_messages(chat_id, ids=msg_id)
            await bot.send_file(
                event.chat_id,
                file=msg.media,
                caption="𝐂ʜᴀᴍᴘᴜ 𝐆ᴀᴡᴅ 𝐄ɴᴛᴇʀs ❤️‍🔥"
            )
        except:
            pass
            
# ────────────────────────────────────────────────
#                   COMMANDS
# ────────────────────────────────────────────────

# Banner
@register_cmd("banner", needs_reply=True)
async def cmd_banner(event, _):
    global menu_banner_msg

    reply = await event.get_reply_message()

    # ─── MEDIA VALIDATION ENGINE ───
    if not reply:
        return await safe_edit(
            event,
            "❌ 𝐍ᴏ 𝐑ᴇᴘʟʏ\n👉 𝐑ᴇᴘʟʏ 𝐓ᴏ 𝐏ʜᴏᴛᴏ / 𝐕ɪᴅᴇᴏ"
        )

    if not reply.media:
        return await safe_edit(
            event,
            "❌ 𝐈ɴᴠᴀʟɪᴅ 𝐌ᴇᴅɪᴀ\n👉 𝐎ɴʟʏ 𝐏ʜᴏᴛᴏ / 𝐕ɪᴅᴇᴏ"
        )

    await safe_edit(
        event,
        "⚡ 𝐏ʀᴏᴄᴇssɪɴɢ 𝐁ᴀɴɴᴇʀ...\n━━━━━━━━━━━━━━━"
    )

    try:
        # ─── FORWARD TRY FIRST (FAST PATH) ───
        try:
            saved = await reply.forward_to("me")
        except Exception:
            # ⭐ FORWARD RESTRICTED FALLBACK
            file = await reply.download_media(file=bytes)
            if not file:
                return await safe_edit(event,
                    "❌ 𝐌ᴇᴅɪᴀ 𝐃ᴏᴡɴʟᴏᴀᴅ 𝐅ᴀɪʟ"
                )

            bio = BytesIO(file)
            bio.name = "banner"
            saved = await bot.send_file("me", bio)

        menu_banner_msg = (saved.chat_id, saved.id)
        save_banner()

        text = (
            "🖼️ 𝐁ᴀɴɴᴇʀ 𝐒ᴇᴛ\n"
            "━━━━━━━━━━━━━━━\n"
            f"📌 𝐒ᴀᴠᴇᴅ 𝐈ᴅ → `{saved.id}`"
        )

        if event.out:
            await safe_edit(event, text)
        else:
            await event.reply(text)

    except FloodWaitError as fw:
        await safe_edit(event,
            f"⏳ 𝐅ʟᴏᴏᴅ 𝐖ᴀɪᴛ → {fw.seconds}s"
        )

    except RPCError as e:
        await safe_edit(event,
            f"❌ 𝐓ɢ 𝐄ʀʀ → `{str(e)[:40]}`"
        )

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐁ᴀɴɴᴇʀ 𝐄ʀʀ → `{str(e)[:50]}`"
        )


@register_cmd("rembanner")
async def cmd_rembanner(event, _):
    global menu_banner_msg

    if not menu_banner_msg:
        return await safe_edit(event,
            "⚠️ 𝐍ᴏ 𝐁ᴀɴɴᴇʀ 𝐒ᴇᴛ"
        )

    await safe_edit(
        event,
        "⚡ 𝐑ᴇᴍᴏᴠɪɴɢ 𝐁ᴀɴɴᴇʀ...\n━━━━━━━━━━━━━━━"
    )

    try:
        chat_id, msg_id = menu_banner_msg

        try:
            await bot.delete_messages(chat_id, [msg_id])
        except Exception:
            # ⭐ banner already manually deleted
            pass

        menu_banner_msg = None
        save_banner()

        text = (
            "🗑️ 𝐁ᴀɴɴᴇʀ 𝐑ᴇᴍᴏᴠᴇᴅ\n"
            "━━━━━━━━━━━━━━━"
        )

        if event.out:
            await safe_edit(event, text)
        else:
            await event.reply(text)

    except FloodWaitError as fw:
        await safe_edit(event,
            f"⏳ 𝐅ʟᴏᴏᴅ → {fw.seconds}s"
        )

    except RPCError as e:
        await safe_edit(event,
            f"❌ 𝐓ɢ 𝐄ʀʀ → `{str(e)[:40]}`"
        )

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐑ᴇᴍᴏᴠᴇ 𝐄ʀʀ → `{str(e)[:50]}`"
        )
        
# Admin Commands (Updated)
@register_cmd("addadmin", needs_reply=True)
async def cmd_addadmin(event, arg):
    try:
        targets = await get_targets(event, arg)

        if not targets:
            return await safe_edit(
                event,
                "❌ 𝐍ᴏ 𝐕ᴀʟɪᴅ 𝐓ᴀʀɢᴇᴛ\n👉 𝐑ᴇᴘʟʏ / @username / ID"
            )

        await safe_edit(
            event,
            "⚡ 𝐏ʀᴏᴄᴇssɪɴɢ 𝐀ᴅᴍɪɴ 𝐀ᴅᴅ...\n━━━━━━━━━━━━━━━"
        )

        added = []
        already = []
        skipped_owner = []

        for uid in targets:
            try:
                uid = int(uid)
            except:
                continue

            if uid == OWNER_ID:
                skipped_owner.append(str(uid))
                continue

            if uid in admins:
                already.append(str(uid))
            else:
                admins.add(uid)
                added.append(str(uid))

        try:
            save_admins()
        except Exception:
            pass

        parts = []

        if added:
            parts.append(
                f"✅ 𝐀ᴅᴍɪɴ 𝐀ᴅᴅᴇᴅ → `{', '.join(added)}`"
            )

        if already:
            parts.append(
                f"⚠️ 𝐀ʟʀᴇᴀᴅʏ 𝐀ᴅᴍɪɴ → `{', '.join(already)}`"
            )

        if skipped_owner:
            parts.append(
                f"👑 𝐎ᴡɴᴇʀ 𝐒ᴋɪᴘᴘᴇᴅ → `{', '.join(skipped_owner)}`"
            )

        if not parts:
            parts.append("❌ 𝐍ᴏ 𝐂ʜᴀɴɢᴇs 𝐌ᴀᴅᴇ")

        text = "\n".join(parts)

        if event.out:
            await safe_edit(event, text)
        else:
            await event.reply(text)

    except FloodWaitError as fw:
        await safe_edit(event,
            f"⏳ 𝐅ʟᴏᴏᴅ → {fw.seconds}s"
        )
    except RPCError as e:
        await safe_edit(event,
            f"❌ 𝐓ɢ 𝐄ʀʀ → `{str(e)[:40]}`"
        )
    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐀ᴅᴍɪɴ 𝐀ᴅᴅ 𝐄ʀʀ → `{str(e)[:50]}`"
        )


@register_cmd("deladmin", needs_reply=True)
async def cmd_deladmin(event, arg):
    try:
        targets = await get_targets(event, arg)

        if not targets:
            return await safe_edit(
                event,
                "❌ 𝐍ᴏ 𝐕ᴀʟɪᴅ 𝐓ᴀʀɢᴇᴛ\n👉 𝐑ᴇᴘʟʏ / @username / ID"
            )

        await safe_edit(
            event,
            "⚡ 𝐏ʀᴏᴄᴇssɪɴɢ 𝐀ᴅᴍɪɴ 𝐑ᴇᴍᴏᴠᴇ...\n━━━━━━━━━━━━━━━"
        )

        removed = []
        not_admin = []
        skipped_owner = []

        for uid in targets:
            try:
                uid = int(uid)
            except:
                continue

            if uid == OWNER_ID:
                skipped_owner.append(str(uid))
                continue

            if uid in admins:
                admins.remove(uid)
                removed.append(str(uid))
            else:
                not_admin.append(str(uid))

        try:
            save_admins()
        except Exception:
            pass

        parts = []

        if removed:
            parts.append(
                f"🗑️ 𝐀ᴅᴍɪɴ 𝐑ᴇᴍᴏᴠᴇᴅ → `{', '.join(removed)}`"
            )

        if not_admin:
            parts.append(
                f"⚠️ 𝐍ᴏᴛ 𝐀ᴅᴍɪɴ → `{', '.join(not_admin)}`"
            )

        if skipped_owner:
            parts.append(
                f"👑 𝐎ᴡɴᴇʀ 𝐏ʀᴏᴛᴇᴄᴛᴇᴅ → `{', '.join(skipped_owner)}`"
            )

        if not parts:
            parts.append("❌ 𝐍ᴏ 𝐂ʜᴀɴɢᴇs 𝐌ᴀᴅᴇ")

        text = "\n".join(parts)

        if event.out:
            await safe_edit(event, text)
        else:
            await event.reply(text)

    except FloodWaitError as fw:
        await safe_edit(event,
            f"⏳ 𝐅ʟᴏᴏᴅ → {fw.seconds}s"
        )
    except RPCError as e:
        await safe_edit(event,
            f"❌ 𝐓ɢ 𝐄ʀʀ → `{str(e)[:40]}`"
        )
    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐀ᴅᴍɪɴ 𝐑ᴇᴍᴏᴠᴇ 𝐄ʀʀ → `{str(e)[:50]}`"
        )


@register_cmd("admins")
async def cmd_admins(event, _):
    try:
        await safe_edit(
            event,
            "⚡ 𝐅ᴇᴛᴄʜɪɴɢ 𝐀ᴅᴍɪɴ 𝐋ɪsᴛ...\n━━━━━━━━━━━━━━━"
        )

        if admins:
            admin_list = "\n".join(
                f"• `{a}`" for a in sorted(admins)
            )
        else:
            admin_list = "⚠️ 𝐍ᴏ 𝐄xᴛʀᴀ 𝐀ᴅᴍɪɴs"

        txt = (
            "👑 𝐀ᴅᴍɪɴ 𝐋ɪsᴛ\n"
            "━━━━━━━━━━━━━━━\n"
            f"👑 𝐎ᴡɴᴇʀ → `{OWNER_ID}`\n\n"
            f"{admin_list}\n\n"
            f"📊 𝐓ᴏᴛᴀʟ → `{len(admins)}`"
        )

        await safe_edit(event, txt)

    except FloodWaitError as fw:
        await safe_edit(event,
            f"⏳ 𝐅ʟᴏᴏᴅ → {fw.seconds}s"
        )
    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐀ᴅᴍɪɴ 𝐋ɪsᴛ 𝐄ʀʀ → `{str(e)[:50]}`"
        )

# Basic Commands (Unchanged)
@register_cmd("ping")
async def cmd_ping(event, _):
    try:
        t0 = time.perf_counter()

        # ─── MESSAGE DISPATCH SAFE ───
        try:
            if event.out:
                msg = await event.edit("🏓 𝐏ɪɴɢ...")
            else:
                msg = await event.reply("🏓 𝐏ɪɴɢ...")
        except:
            msg = None

        t1 = time.perf_counter()
        ms = round((t1 - t0) * 1000)

        # ─── RESPONSE EDIT SAFE ───
        try:
            if msg:
                await msg.edit(f"🏓 𝐏ᴏɴɢ → `{ms} ms`")
            else:
                await event.reply(f"🏓 𝐏ᴏɴɢ → `{ms} ms`")
        except:
            pass

    except FloodWaitError as fw:
        await safe_edit(event, f"⏳ 𝐅ʟᴏᴏᴅ → {fw.seconds}s")
    except Exception as e:
        await safe_edit(event, f"❌ 𝐏ɪɴɢ 𝐄ʀʀ → `{str(e)[:40]}`")


@register_cmd("status")
async def cmd_status(event, _):
    try:
        now = time.time()

        # ─── START TIME CORRUPTION SAFE ───
        try:
            uptime = int(now - START_TIME)
            if uptime < 0:
                uptime = 0
        except:
            uptime = 0

        # ─── ADMIN STORAGE SAFE ───
        try:
            admin_count = len(admins)
        except:
            admin_count = 0

        txt = (
            "✅ 𝐔sᴇʀʙᴏᴛ 𝐒ᴛᴀᴛᴜs\n"
            "━━━━━━━━━━━━━━━\n"
            f"⏱️ 𝐔ᴘᴛɪᴍᴇ → `{uptime}s`\n"
            f"👑 𝐀ᴅᴍɪɴs → `{admin_count}`\n"
            f"⚙️ 𝐌ᴏᴅᴇ → `Operational`"
        )

        try:
            if event.out:
                await safe_edit(event, txt)
            else:
                await event.reply(txt)
        except:
            pass

    except FloodWaitError as fw:
        await safe_edit(event, f"⏳ 𝐅ʟᴏᴏᴅ → {fw.seconds}s")
    except Exception as e:
        await safe_edit(event, f"❌ 𝐒ᴛᴀᴛᴜs 𝐄ʀʀ → `{str(e)[:40]}`")


@register_cmd("flip")
async def cmd_flip(event, _):
    try:
        # ─── RANDOM SAFE ───
        try:
            result = random.choice(["🪙 𝐇ᴇᴀᴅs", "🪙 𝐓ᴀɪʟs"])
        except:
            result = "🪙 𝐇ᴇᴀᴅs"

        text = (
            "🎲 𝐂ᴏɪɴ 𝐅ʟɪᴘ\n"
            "━━━━━━━━━━━━━━━\n"
            f"👉 𝐑ᴇsᴜʟᴛ → {result}"
        )

        try:
            if event.out:
                await safe_edit(event, text)
            else:
                await event.reply(text)
        except:
            pass

    except FloodWaitError as fw:
        await safe_edit(event, f"⏳ 𝐅ʟᴏᴏᴅ → {fw.seconds}s")
    except Exception as e:
        await safe_edit(event, f"❌ 𝐅ʟɪᴘ 𝐄ʀʀ → `{str(e)[:40]}`")


@register_cmd("dice")
async def cmd_dice(event, _):
    try:
        # ─── RANDOM SAFE ───
        try:
            num = random.randint(1, 6)
        except:
            num = 1

        text = (
            "🎲 𝐃ɪᴄᴇ 𝐑ᴏʟʟ\n"
            "━━━━━━━━━━━━━━━\n"
            f"👉 𝐑ᴇsᴜʟᴛ → `{num}`"
        )

        try:
            if event.out:
                await safe_edit(event, text)
            else:
                await event.reply(text)
        except:
            pass

    except FloodWaitError as fw:
        await safe_edit(event, f"⏳ 𝐅ʟᴏᴏᴅ → {fw.seconds}s")
    except Exception as e:
        await safe_edit(event, f"❌ 𝐃ɪᴄᴇ 𝐄ʀʀ → `{str(e)[:40]}`")

# Raid Commands
@register_cmd("reply", needs_reply=True)
async def cmd_reply(event, arg):
    try:
        targets = await get_targets(event, arg)

        if not targets:
            return await safe_edit(event,
                "❌ 𝐍ᴏ 𝐕ᴀʟɪᴅ 𝐓ᴀʀɢᴇᴛ"
            )

        await safe_edit(event,
            "⚡ 𝐄ɴᴀʙʟɪɴɢ 𝐑ᴇᴘʟʏ 𝐑ᴀɪᴅ (𝐆ʟᴏʙᴀʟ)...\n━━━━━━━━━━━━━━━"
        )

        added, already = [], []

        for uid in targets:
            try:
                uid = int(uid)
            except:
                continue

            if uid in reply_users:
                already.append(str(uid))
            else:
                reply_users.add(uid)
                added.append(str(uid))

        parts = []

        if added:
            parts.append(f"🔥 𝐑ᴇᴘʟʏ 𝐑ᴀɪᴅ 𝐎ɴ → `{', '.join(added)}`")

        if already:
            parts.append(f"⚠️ 𝐀ʟʀᴇᴀᴅʏ 𝐀ᴄᴛɪᴠᴇ → `{', '.join(already)}`")

        if not parts:
            parts.append("❌ 𝐍ᴏ 𝐂ʜᴀɴɢᴇ")

        msg = "\n".join(parts)

        if event.out:
            await safe_edit(event, msg)
        else:
            await event.reply(msg)

    except FloodWaitError as fw:
        await safe_edit(event, f"⏳ 𝐅ʟᴏᴏᴅ → {fw.seconds}s")
    except Exception as e:
        await safe_edit(event, f"❌ 𝐑ᴇᴘʟʏ 𝐑ᴀɪᴅ 𝐄ʀʀ → `{str(e)[:40]}`")


@register_cmd("rr", needs_reply=True)
async def cmd_rr(event, arg):
    try:
        targets = await get_targets(event, arg)

        if not targets:
            return await safe_edit(event,
                "❌ 𝐍ᴏ 𝐕ᴀʟɪᴅ 𝐓ᴀʀɢᴇᴛ"
            )

        await safe_edit(event,
            "⚡ 𝐄ɴᴀʙʟɪɴɢ 𝐑𝐑 𝐑ᴀɪᴅ (𝐆ʟᴏʙᴀʟ)...\n━━━━━━━━━━━━━━━"
        )

        added, already = [], []

        for uid in targets:
            try:
                uid = int(uid)
            except:
                continue

            if uid in rr_users:
                already.append(str(uid))
            else:
                rr_users.add(uid)
                added.append(str(uid))

        parts = []

        if added:
            parts.append(f"⚡ 𝐑𝐑 𝐎ɴ → `{', '.join(added)}`")

        if already:
            parts.append(f"⚠️ 𝐀ʟʀᴇᴀᴅʏ → `{', '.join(already)}`")

        if not parts:
            parts.append("❌ 𝐍ᴏ 𝐂ʜᴀɴɢᴇ")

        msg = "\n".join(parts)

        if event.out:
            await safe_edit(event, msg)
        else:
            await event.reply(msg)

    except FloodWaitError as fw:
        await safe_edit(event, f"⏳ 𝐅ʟᴏᴏᴅ → {fw.seconds}s")
    except Exception as e:
        await safe_edit(event, f"❌ 𝐑𝐑 𝐄ʀʀ → `{str(e)[:40]}`")


@register_cmd("flag", needs_reply=True)
async def cmd_flag(event, arg):
    try:
        targets = await get_targets(event, arg)

        if not targets:
            return await safe_edit(event,
                "❌ 𝐍ᴏ 𝐕ᴀʟɪᴅ 𝐓ᴀʀɢᴇᴛ"
            )

        await safe_edit(event,
            "⚡ 𝐄ɴᴀʙʟɪɴɢ 𝐅ʟᴀɢ 𝐑ᴀɪᴅ (𝐆ʟᴏʙᴀʟ)...\n━━━━━━━━━━━━━━━"
        )

        added, already = [], []

        for uid in targets:
            try:
                uid = int(uid)
            except:
                continue

            if uid in flag_users:
                already.append(str(uid))
            else:
                flag_users.add(uid)
                added.append(str(uid))

        parts = []

        if added:
            parts.append(f"🌊 𝐅ʟᴀɢ 𝐎ɴ → `{', '.join(added)}`")

        if already:
            parts.append(f"⚠️ 𝐀ʟʀᴇᴀᴅʏ → `{', '.join(already)}`")

        if not parts:
            parts.append("❌ 𝐍ᴏ 𝐂ʜᴀɴɢᴇ")

        msg = "\n".join(parts)

        if event.out:
            await safe_edit(event, msg)
        else:
            await event.reply(msg)

    except FloodWaitError as fw:
        await safe_edit(event, f"⏳ 𝐅ʟᴏᴏᴅ → {fw.seconds}s")
    except Exception as e:
        await safe_edit(event, f"❌ 𝐅ʟᴀɢ 𝐄ʀʀ → `{str(e)[:40]}`")


@register_cmd("hrr", needs_reply=True)
async def cmd_hrr(event, arg):
    try:
        targets = await get_targets(event, arg)

        if not targets:
            return await safe_edit(event,
                "❌ 𝐍ᴏ 𝐕ᴀʟɪᴅ 𝐓ᴀʀɢᴇᴛ"
            )

        await safe_edit(event,
            "⚡ 𝐄ɴᴀʙʟɪɴɢ 𝐇ᴇᴀʀᴛ 𝐑ᴀɪᴅ (𝐆ʟᴏʙᴀʟ)...\n━━━━━━━━━━━━━━━"
        )

        added, already = [], []

        for uid in targets:
            try:
                uid = int(uid)
            except:
                continue

            if uid in hrr_users:
                already.append(str(uid))
            else:
                hrr_users.add(uid)
                added.append(str(uid))

        parts = []

        if added:
            parts.append(f"💜 𝐇ᴇᴀʀᴛ 𝐑ᴀɪᴅ → `{', '.join(added)}`")

        if already:
            parts.append(f"⚠️ 𝐀ʟʀᴇᴀᴅʏ → `{', '.join(already)}`")

        if not parts:
            parts.append("❌ 𝐍ᴏ 𝐂ʜᴀɴɢᴇ")

        msg = "\n".join(parts)

        if event.out:
            await safe_edit(event, msg)
        else:
            await event.reply(msg)

    except FloodWaitError as fw:
        await safe_edit(event, f"⏳ 𝐅ʟᴏᴏᴅ → {fw.seconds}s")
    except Exception as e:
        await safe_edit(event, f"❌ 𝐇𝐑𝐑 𝐄ʀʀ → `{str(e)[:40]}`")


@register_cmd("replygod", needs_reply=True)
async def cmd_replygod(event, arg):
    try:
        targets = await get_targets(event, arg)

        if not targets:
            return await safe_edit(event,
                "❌ 𝐍ᴏ 𝐕ᴀʟɪᴅ 𝐓ᴀʀɢᴇᴛ"
            )

        await safe_edit(event,
            "⚡ 𝐄ɴᴀʙʟɪɴɢ 𝐑ᴇᴘʟʏ𝐆ᴏᴅ (𝐆ʟᴏʙᴀʟ)...\n━━━━━━━━━━━━━━━"
        )

        added, already = [], []

        for uid in targets:
            try:
                uid = int(uid)
            except:
                continue

            if uid in replygod_users:
                already.append(str(uid))
            else:
                replygod_users.add(uid)
                added.append(str(uid))

        parts = []

        if added:
            parts.append(f"💥 𝐑ᴇᴘʟʏ𝐆ᴏᴅ → `{', '.join(added)}`")

        if already:
            parts.append(f"⚠️ 𝐀ʟʀᴇᴀᴅʏ → `{', '.join(already)}`")

        if not parts:
            parts.append("❌ 𝐍ᴏ 𝐂ʜᴀɴɢᴇ")

        msg = "\n".join(parts)

        if event.out:
            await safe_edit(event, msg)
        else:
            await event.reply(msg)

    except FloodWaitError as fw:
        await safe_edit(event, f"⏳ 𝐅ʟᴏᴏᴅ → {fw.seconds}s")
    except Exception as e:
        await safe_edit(event, f"❌ 𝐑𝐆 𝐄ʀʀ → `{str(e)[:40]}`")


@register_cmd("replyyorichi", needs_reply=True)
async def cmd_replyyorichi(event, arg):
    try:
        if not arg or len(arg.split()) < 2:
            return await safe_edit(event,
                "❌ 𝐈ɴᴠᴀʟɪᴅ 𝐅ᴏʀᴍᴀᴛ\n👉 `.replyyorichi <text> <count>`"
            )

        text, count = arg.rsplit(" ", 1)

        try:
            count = int(count)
        except:
            return await safe_edit(event,
                "❌ 𝐂ᴏᴜɴᴛ 𝐌ᴜsᴛ 𝐁ᴇ 𝐍ᴜᴍʙᴇʀ"
            )

        if count <= 0:
            count = 1
        if count > 100:
            count = 100

        targets = await get_targets(event, "")

        if not targets:
            return await safe_edit(event,
                "❌ 𝐍ᴏ 𝐕ᴀʟɪᴅ 𝐓ᴀʀɢᴇᴛ"
            )

        await safe_edit(event,
            "⚡ 𝐒ᴇᴛᴛɪɴɢ 𝐑ᴇᴘʟʏ𝐂ʜᴀᴍᴘᴜ (𝐆ʟᴏʙᴀʟ)...\n━━━━━━━━━━━━━━━"
        )

        added, overridden = [], []

        for uid in targets:
            try:
                uid = int(uid)
            except:
                continue

            if uid in replyyorichi_users:
                overridden.append(str(uid))

            replyyorichi_users[uid] = {
                "text": text,
                "count": count
            }
            added.append(str(uid))

        parts = []

        if added:
            parts.append(f"☄️ 𝐑𝐘 → `{', '.join(added)}` × `{count}`")

        if overridden:
            parts.append(f"⚠️ 𝐎ᴠᴇʀʀɪᴅᴇ → `{', '.join(overridden)}`")

        msg = "\n".join(parts)

        if event.out:
            await safe_edit(event, msg)
        else:
            await event.reply(msg)

    except FloodWaitError as fw:
        await safe_edit(event, f"⏳ 𝐅ʟᴏᴏᴅ → {fw.seconds}s")
    except Exception as e:
        await safe_edit(event, f"❌ 𝐑𝐘 𝐄ʀʀ → `{str(e)[:40]}`")

@register_cmd("spray")
async def cmd_spray(event, arg):
    try:
        if not arg:
            return await safe_edit(
                event,
                "❌ 𝐍ᴏ 𝐓ᴇxᴛ 𝐆ɪᴠᴇɴ\n"
                "👉 𝐔sᴀɢᴇ: `.spray <text>`"
            )

        chat = event.chat_id

        # ─── HUGE TEXT GUARD ───
        if len(arg) > 4000:
            arg = arg[:4000]

        # ─── ALREADY ACTIVE GUARD ───
        if chat in spray_tasks and not spray_tasks[chat].done():
            msg = "⚠️ 𝐒ᴘʀᴀʏ 𝐀ʟʀᴇᴀᴅʏ 𝐀ᴄᴛɪᴠᴇ"
            if event.out:
                return await safe_edit(event, msg)
            else:
                return await event.reply(msg)

        await safe_edit(
            event,
            "⚡ 𝐈ɴɪᴛɪᴀʟɪᴢɪɴɢ 𝐒ᴘʀᴀʏ...\n━━━━━━━━━━━━━━━"
        )

        async def spray_loop():
            try:
                while True:
                    # stop condition
                    if chat not in spray_tasks:
                        break

                    try:
                        await bot.send_message(chat, arg)
                    except FloodWaitError as fw:
                        await asyncio.sleep(fw.seconds)
                    except RPCError:
                        # permission lost / banned / readonly
                        spray_tasks.pop(chat, None)
                        break
                    except Exception:
                        # network / msg send fail
                        await asyncio.sleep(2)

                    await asyncio.sleep(SPRAY_DELAY)

            except asyncio.CancelledError:
                pass
            finally:
                spray_tasks.pop(chat, None)

        spray_tasks[chat] = asyncio.create_task(spray_loop())

        text = (
            "💣 𝐒ᴘʀᴀʏ 𝐒ᴛᴀʀᴛᴇᴅ\n"
            "━━━━━━━━━━━━━━━\n"
            f"📢 𝐓ᴇxᴛ → `{arg[:40]}`"
        )

        if event.out:
            await safe_edit(event, text)
        else:
            await event.reply(text)

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐒ᴘʀᴀʏ 𝐄ʀʀ → `{str(e)[:40]}`"
        )


@register_cmd("dspray")
async def cmd_dspray(event, _):
    try:
        chat = event.chat_id

        if chat not in spray_tasks:
            msg = "⚠️ 𝐍ᴏ 𝐀ᴄᴛɪᴠᴇ 𝐒ᴘʀᴀʏ"
            if event.out:
                return await safe_edit(event, msg)
            else:
                return await event.reply(msg)

        await safe_edit(
            event,
            "⚡ 𝐒ᴛᴏᴘᴘɪɴɢ 𝐒ᴘʀᴀʏ...\n━━━━━━━━━━━━━━━"
        )

        try:
            spray_tasks[chat].cancel()
        except:
            pass

        spray_tasks.pop(chat, None)

        text = (
            "🛑 𝐒ᴘʀᴀʏ 𝐒ᴛᴏᴘᴘᴇᴅ\n"
            "━━━━━━━━━━━━━━━"
        )

        if event.out:
            await safe_edit(event, text)
        else:
            await event.reply(text)

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐃𝐒ᴘʀᴀʏ 𝐄ʀʀ → `{str(e)[:40]}`"
        )

# Mute Commands
@register_cmd("mute", needs_reply=True)
async def cmd_mute(event, arg):
    try:
        targets = await get_targets(event, arg)

        if not targets:
            return await safe_edit(
                event,
                "❌ 𝐍ᴏ 𝐓ᴀʀɢᴇᴛ\n👉 `.mute` (reply / @username / id)"
            )

        await safe_edit(
            event,
            "⚡ 𝐏ʀᴏᴄᴇssɪɴɢ 𝐌ᴜᴛᴇ...\n━━━━━━━━━━━━━━━"
        )

        added, already = [], []

        for uid in targets:
            try:
                uid = int(uid)
            except:
                continue

            if uid in muted_users:
                already.append(str(uid))
            else:
                muted_users.add(uid)
                added.append(str(uid))

        parts = []

        if added:
            parts.append(f"🔇 𝐌ᴜᴛᴇ → `{', '.join(added)}`")

        if already:
            parts.append(f"⚠️ 𝐀ʟʀᴇᴀᴅʏ 𝐌ᴜᴛᴇᴅ → `{', '.join(already)}`")

        if not parts:
            parts.append("❌ 𝐍ᴏ 𝐂ʜᴀɴɢᴇ")

        msg = "\n".join(parts)

        if event.out:
            await safe_edit(event, msg)
        else:
            await event.reply(msg)

    except FloodWaitError as fw:
        await safe_edit(event, f"⏳ 𝐅ʟᴏᴏᴅ → {fw.seconds}s")
    except Exception as e:
        await safe_edit(event, f"❌ 𝐌ᴜᴛᴇ 𝐄ʀʀ → `{str(e)[:40]}`")


@register_cmd("unmute", needs_reply=True)
async def cmd_unmute(event, arg):
    try:
        targets = await get_targets(event, arg)

        if not targets:
            return await safe_edit(
                event,
                "❌ 𝐍ᴏ 𝐓ᴀʀɢᴇᴛ\n👉 `.unmute` (reply / @username / id)"
            )

        await safe_edit(
            event,
            "⚡ 𝐏ʀᴏᴄᴇssɪɴɢ 𝐔ɴᴍᴜᴛᴇ...\n━━━━━━━━━━━━━━━"
        )

        removed, not_muted = [], []

        for uid in targets:
            try:
                uid = int(uid)
            except:
                continue

            if uid in muted_users:
                muted_users.remove(uid)
                removed.append(str(uid))
            else:
                not_muted.append(str(uid))

        parts = []

        if removed:
            parts.append(f"🗣️ 𝐔ɴᴍᴜᴛᴇ → `{', '.join(removed)}`")

        if not_muted:
            parts.append(f"⚠️ 𝐍ᴏᴛ 𝐌ᴜᴛᴇᴅ → `{', '.join(not_muted)}`")

        if not parts:
            parts.append("❌ 𝐍ᴏ 𝐂ʜᴀɴɢᴇ")

        msg = "\n".join(parts)

        if event.out:
            await safe_edit(event, msg)
        else:
            await event.reply(msg)

    except FloodWaitError as fw:
        await safe_edit(event, f"⏳ 𝐅ʟᴏᴏᴅ → {fw.seconds}s")
    except Exception as e:
        await safe_edit(event, f"❌ 𝐔ɴᴍᴜᴛᴇ 𝐄ʀʀ → `{str(e)[:40]}`")


@register_cmd("gmute", needs_reply=True)
async def cmd_gmute(event, arg):
    try:
        targets = await get_targets(event, arg)

        if not targets:
            return await safe_edit(
                event,
                "❌ 𝐍ᴏ 𝐓ᴀʀɢᴇᴛ\n👉 `.gmute` (reply / @username / id)"
            )

        await safe_edit(
            event,
            "⚡ 𝐏ʀᴏᴄᴇssɪɴɢ 𝐆ᴍᴜᴛᴇ...\n━━━━━━━━━━━━━━━"
        )

        added, already = [], []

        for uid in targets:
            try:
                uid = int(uid)
            except:
                continue

            if uid in global_muted:
                already.append(str(uid))
            else:
                global_muted.add(uid)
                added.append(str(uid))

        parts = []

        if added:
            parts.append(f"🔕 𝐆ᴍᴜᴛᴇ → `{', '.join(added)}`")

        if already:
            parts.append(f"⚠️ 𝐀ʟʀᴇᴀᴅʏ 𝐆ᴍᴜᴛᴇᴅ → `{', '.join(already)}`")

        if not parts:
            parts.append("❌ 𝐍ᴏ 𝐂ʜᴀɴɢᴇ")

        msg = "\n".join(parts)

        if event.out:
            await safe_edit(event, msg)
        else:
            await event.reply(msg)

    except FloodWaitError as fw:
        await safe_edit(event, f"⏳ 𝐅ʟᴏᴏᴅ → {fw.seconds}s")
    except Exception as e:
        await safe_edit(event, f"❌ 𝐆ᴍᴜᴛᴇ 𝐄ʀʀ → `{str(e)[:40]}`")


@register_cmd("gunmute", needs_reply=True)
async def cmd_gunmute(event, arg):
    try:
        targets = await get_targets(event, arg)

        if not targets:
            return await safe_edit(
                event,
                "❌ 𝐍ᴏ 𝐓ᴀʀɢᴇᴛ\n👉 `.gunmute` (reply / @username / id)"
            )

        await safe_edit(
            event,
            "⚡ 𝐏ʀᴏᴄᴇssɪɴɢ 𝐆ᴜɴᴍᴜᴛᴇ...\n━━━━━━━━━━━━━━━"
        )

        removed, not_muted = [], []

        for uid in targets:
            try:
                uid = int(uid)
            except:
                continue

            if uid in global_muted:
                global_muted.remove(uid)
                removed.append(str(uid))
            else:
                not_muted.append(str(uid))

        parts = []

        if removed:
            parts.append(f"🔊 𝐆ᴜɴᴍᴜᴛᴇ → `{', '.join(removed)}`")

        if not_muted:
            parts.append(f"⚠️ 𝐍ᴏᴛ 𝐆ᴍᴜᴛᴇᴅ → `{', '.join(not_muted)}`")

        if not parts:
            parts.append("❌ 𝐍ᴏ 𝐂ʜᴀɴɢᴇ")

        msg = "\n".join(parts)

        if event.out:
            await safe_edit(event, msg)
        else:
            await event.reply(msg)

    except FloodWaitError as fw:
        await safe_edit(event, f"⏳ 𝐅ʟᴏᴏᴅ → {fw.seconds}s")
    except Exception as e:
        await safe_edit(event, f"❌ 𝐆𝐔𝐍𝐌𝐔𝐓𝐄 𝐄ʀʀ → `{str(e)[:40]}`")

# Group Mod
@register_cmd("purge")
async def cmd_purge(event, arg):
    try:
        try:
            count = int(arg) if arg else 50
        except:
            count = 50

        # ─── HARD LIMIT ENGINE ───
        if count < 1:
            count = 1
        if count > 200:
            count = 200

        await safe_edit(
            event,
            "⚡ 𝐏ᴜʀɢɪɴɢ 𝐌ᴇssᴀɢᴇs...\n━━━━━━━━━━━━━━━"
        )

        msgs = []
        async for m in bot.iter_messages(event.chat_id, limit=count + 1):
            msgs.append(m.id)

        if not msgs:
            return await safe_edit(event,
                "⚠️ 𝐍ᴏ 𝐌ᴇssᴀɢᴇs 𝐅ᴏᴜɴᴅ"
            )

        # ─── SAFE DELETE BATCH ───
        try:
            await bot.delete_messages(event.chat_id, msgs)
        except FloodWaitError as fw:
            await asyncio.sleep(fw.seconds)
            await bot.delete_messages(event.chat_id, msgs)
        except RPCError:
            # readonly / no rights / protected msgs
            pass

        text = (
            "🧹 𝐏ᴜʀɢᴇ 𝐂ᴏᴍᴘʟᴇᴛᴇ\n"
            "━━━━━━━━━━━━━━━\n"
            f"🗑️ 𝐃ᴇʟᴇᴛᴇᴅ → `{max(len(msgs)-1,0)}`"
        )

        if event.out:
            await safe_edit(event, text)
        else:
            await event.reply(text)

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐏ᴜʀɢᴇ 𝐄ʀʀ → `{str(e)[:40]}`"
        )


@register_cmd("throw", needs_reply=True, group_only=True)
async def cmd_throw(event, arg):
    try:
        targets = await get_targets(event, arg)

        if not targets:
            return await safe_edit(event,
                "❌ 𝐍ᴏ 𝐓ᴀʀɢᴇᴛ"
            )

        # ─── ADMIN CHECK SAFE ───
        try:
            perms = await bot.get_permissions(event.chat_id, 'me')
            if not perms.is_admin:
                return await safe_edit(event,
                    "❌ 𝐍ᴏ 𝐀ᴅᴍɪɴ 𝐑ɪɢʜᴛs"
                )
        except:
            return await safe_edit(event,
                "❌ 𝐏ᴇʀᴍ𝐢ssɪᴏɴ 𝐂ʜᴇᴄᴋ 𝐅ᴀɪʟ"
            )

        await safe_edit(
            event,
            "⚡ 𝐊ɪᴄᴋɪɴɢ 𝐓ᴀʀɢᴇᴛs...\n━━━━━━━━━━━━━━━"
        )

        kicked, failed, skipped = [], [], []

        me = await bot.get_me()

        for uid in targets:
            try:
                uid = int(uid)
            except:
                continue

            if uid == me.id:
                skipped.append(str(uid))
                continue

            try:
                await bot.kick_participant(event.chat_id, uid)
                kicked.append(str(uid))
            except:
                failed.append(str(uid))

        parts = []

        if kicked:
            parts.append(f"👞 𝐊ɪᴄᴋᴇᴅ → `{', '.join(kicked)}`")

        if failed:
            parts.append(f"⚠️ 𝐅ᴀɪʟᴇᴅ → `{', '.join(failed)}`")

        if skipped:
            parts.append(f"👑 𝐒ᴇʟғ 𝐒ᴋɪᴘ → `{', '.join(skipped)}`")

        if not parts:
            parts.append("❌ 𝐍ᴏ 𝐀ᴄᴛɪᴏɴ")

        msg = "\n".join(parts)

        if event.out:
            await safe_edit(event, msg)
        else:
            await event.reply(msg)

    except FloodWaitError as fw:
        await safe_edit(event, f"⏳ 𝐅ʟᴏᴏᴅ → {fw.seconds}s")
    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐓ʜʀᴏᴡ 𝐄ʀʀ → `{str(e)[:40]}`"
        )


@register_cmd("sreply")
async def cmd_sreply(event, arg):
    try:
        targets = await get_targets(event, arg)

        if targets:
            stopped, not_active = [], []

            for uid in targets:
                try:
                    uid = int(uid)
                except:
                    continue

                if uid in reply_users:
                    reply_users.discard(uid)
                    stopped.append(str(uid))
                else:
                    not_active.append(str(uid))

            parts = []

            if stopped:
                parts.append(f"🛑 𝐑ᴇᴘʟʏ 𝐎ғғ → `{', '.join(stopped)}`")

            if not_active:
                parts.append(f"⚠️ 𝐍ᴏᴛ 𝐀ᴄᴛɪᴠᴇ → `{', '.join(not_active)}`")

            if not parts:
                parts.append("❌ 𝐍ᴏ 𝐂ʜᴀɴɢᴇ")

            text = "\n".join(parts)

        else:
            reply_users.clear()
            text = (
                "🛑 𝐑ᴇᴘʟʏ 𝐎ғғ\n"
                "━━━━━━━━━━━━━━━\n"
                "👉 𝐀ʟʟ 𝐔sᴇʀs"
            )

        if event.out:
            await safe_edit(event, text)
        else:
            await event.reply(text)

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐒𝐑𝐄𝐏𝐋𝐘 𝐄ʀʀ → `{str(e)[:40]}`"
        )


@register_cmd("srr")
async def cmd_srr(event, arg):
    try:
        targets = await get_targets(event, arg)

        if targets:
            stopped, not_active = [], []

            for uid in targets:
                try:
                    uid = int(uid)
                except:
                    continue

                if uid in rr_users:
                    rr_users.discard(uid)
                    stopped.append(str(uid))
                else:
                    not_active.append(str(uid))

            parts = []

            if stopped:
                parts.append(f"🛑 𝐑𝐑 𝐎ғғ → `{', '.join(stopped)}`")

            if not_active:
                parts.append(f"⚠️ 𝐍ᴏᴛ 𝐀ᴄᴛɪᴠᴇ → `{', '.join(not_active)}`")

            if not parts:
                parts.append("❌ 𝐍ᴏ 𝐂ʜᴀɴɢᴇ")

            text = "\n".join(parts)

        else:
            rr_users.clear()

            text = (
                "🛑 𝐑𝐑 𝐎ғғ\n"
                "━━━━━━━━━━━━━━━\n"
                "👉 𝐀ʟʟ 𝐔sᴇʀs"
            )

        if event.out:
            await safe_edit(event, text)
        else:
            await event.reply(text)

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐒𝐑𝐑 𝐄ʀʀ → `{str(e)[:40]}`"
        )


@register_cmd("sflag")
async def cmd_sflag(event, arg):
    try:
        targets = await get_targets(event, arg)

        if targets:
            stopped, not_active = [], []

            for uid in targets:
                try:
                    uid = int(uid)
                except:
                    continue

                if uid in flag_users:
                    flag_users.discard(uid)
                    stopped.append(str(uid))
                else:
                    not_active.append(str(uid))

            parts = []

            if stopped:
                parts.append(f"🛑 𝐅ʟᴀɢ 𝐎ғғ → `{', '.join(stopped)}`")

            if not_active:
                parts.append(f"⚠️ 𝐍ᴏᴛ 𝐀ᴄᴛɪᴠᴇ → `{', '.join(not_active)}`")

            if not parts:
                parts.append("❌ 𝐍ᴏ 𝐂ʜᴀɴɢᴇ")

            text = "\n".join(parts)

        else:
            flag_users.clear()

            text = (
                "🛑 𝐅ʟᴀɢ 𝐎ғғ\n"
                "━━━━━━━━━━━━━━━\n"
                "👉 𝐀ʟʟ 𝐔sᴇʀs"
            )

        if event.out:
            await safe_edit(event, text)
        else:
            await event.reply(text)

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐒𝐅𝐋𝐀𝐆 𝐄ʀʀ → `{str(e)[:40]}`"
        )


@register_cmd("shrr")
async def cmd_shrr(event, arg):
    try:
        targets = await get_targets(event, arg)

        if targets:
            await safe_edit(
                event,
                "⚡ 𝐃ɪsᴀʙʟɪɴɢ 𝐇ᴇᴀʀᴛ 𝐑ᴀɪᴅ (𝐆ʟᴏʙᴀʟ)...\n━━━━━━━━━━━━━━━"
            )

            stopped, not_active = [], []

            for uid in targets:
                try:
                    uid = int(uid)
                except:
                    continue

                if uid in hrr_users:
                    hrr_users.discard(uid)
                    stopped.append(str(uid))
                else:
                    not_active.append(str(uid))

            parts = []

            if stopped:
                parts.append(
                    f"🛑 𝐇ᴇᴀʀᴛ 𝐎ғғ → `{', '.join(stopped)}`"
                )

            if not_active:
                parts.append(
                    f"⚠️ 𝐍ᴏᴛ 𝐀ᴄᴛɪᴠᴇ → `{', '.join(not_active)}`"
                )

            if not parts:
                parts.append("❌ 𝐍ᴏ 𝐂ʜᴀɴɢᴇ")

            text = "\n".join(parts)

        else:
            hrr_users.clear()

            text = (
                "🛑 𝐇ᴇᴀʀᴛ 𝐎ғғ\n"
                "━━━━━━━━━━━━━━━\n"
                "👉 𝐀ʟʟ 𝐔sᴇʀs"
            )

        if event.out:
            await safe_edit(event, text)
        else:
            await event.reply(text)

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐒𝐇𝐑𝐑 𝐄ʀʀ → `{str(e)[:40]}`"
        )


@register_cmd("sgod")
async def cmd_sgod(event, arg):
    try:
        targets = await get_targets(event, arg)

        if targets:
            await safe_edit(
                event,
                "⚡ 𝐃ɪsᴀʙʟɪɴɢ 𝐑ᴇᴘʟʏ𝐆ᴏᴅ (𝐆ʟᴏʙᴀʟ)...\n━━━━━━━━━━━━━━━"
            )

            stopped, not_active = [], []

            for uid in targets:
                try:
                    uid = int(uid)
                except:
                    continue

                if uid in replygod_users:
                    replygod_users.discard(uid)
                    stopped.append(str(uid))
                else:
                    not_active.append(str(uid))

            parts = []

            if stopped:
                parts.append(
                    f"🛑 𝐑𝐆 𝐎ғғ → `{', '.join(stopped)}`"
                )

            if not_active:
                parts.append(
                    f"⚠️ 𝐍ᴏᴛ 𝐀ᴄᴛɪᴠᴇ → `{', '.join(not_active)}`"
                )

            if not parts:
                parts.append("❌ 𝐍ᴏ 𝐂ʜᴀɴɢᴇ")

            text = "\n".join(parts)

        else:
            replygod_users.clear()

            text = (
                "🛑 𝐑𝐆 𝐎ғғ\n"
                "━━━━━━━━━━━━━━━\n"
                "👉 𝐀ʟʟ 𝐔sᴇʀs"
            )

        if event.out:
            await safe_edit(event, text)
        else:
            await event.reply(text)

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐒𝐆𝐎𝐃 𝐄ʀʀ → `{str(e)[:40]}`"
        )


@register_cmd("syorichi")
async def cmd_syorichi(event, arg):
    try:
        targets = await get_targets(event, arg)

        if targets:
            await safe_edit(
                event,
                "⚡ 𝐃ɪsᴀʙʟɪɴɢ 𝐑𝐘 (𝐆ʟᴏʙᴀʟ)...\n━━━━━━━━━━━━━━━"
            )

            stopped, not_active = [], []

            for uid in targets:
                try:
                    uid = int(uid)
                except:
                    continue

                if uid in replyyorichi_users:
                    replyyorichi_users.pop(uid, None)
                    stopped.append(str(uid))
                else:
                    not_active.append(str(uid))

            parts = []

            if stopped:
                parts.append(
                    f"🛑 𝐑𝐘 𝐎ғғ → `{', '.join(stopped)}`"
                )

            if not_active:
                parts.append(
                    f"⚠️ 𝐍ᴏᴛ 𝐀ᴄᴛɪᴠᴇ → `{', '.join(not_active)}`"
                )

            if not parts:
                parts.append("❌ 𝐍ᴏ 𝐂ʜᴀɴɢᴇ")

            text = "\n".join(parts)

        else:
            replyyorichi_users.clear()

            text = (
                "🛑 𝐑𝐘 𝐎ғғ\n"
                "━━━━━━━━━━━━━━━\n"
                "👉 𝐀ʟʟ 𝐔sᴇʀs"
            )

        if event.out:
            await safe_edit(event, text)
        else:
            await event.reply(text)

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐒𝐘𝐎𝐑𝐈𝐂𝐇𝐈 𝐄ʀʀ → `{str(e)[:40]}`"
        )

# Lock / Unlock
@register_cmd("lock", group_only=True)
async def cmd_lock(event, _):
    try:
        chat = event.chat_id

        # ─── ADMIN CHECK ───
        try:
            perms = await bot.get_permissions(chat, 'me')
            if not perms.is_admin:
                return await safe_edit(event,
                    "❌ 𝐍ᴏ 𝐀ᴅᴍɪɴ 𝐑ɪɢʜᴛs"
                )
        except:
            pass

        if chat in group_locks:
            msg = "⚠️ 𝐆ʀᴏᴜᴘ 𝐀ʟʀᴇᴀᴅʏ 𝐋ᴏᴄᴋᴇᴅ"
            if event.out:
                return await safe_edit(event, msg)
            else:
                return await event.reply(msg)

        await safe_edit(
            event,
            "⚡ 𝐀ᴘᴘʟʏɪɴɢ 𝐋ᴏᴄᴋ...\n━━━━━━━━━━━━━━━"
        )

        group_locks.add(chat)

        text = (
            "🔒 𝐆ʀᴏᴜᴘ 𝐋ᴏᴄᴋᴇᴅ\n"
            "━━━━━━━━━━━━━━━\n"
            "🚫 𝐍ᴏɴ-𝐀ᴅᴍɪɴ 𝐌ᴇssᴀɢᴇs 𝐁ʟᴏᴄᴋᴇᴅ"
        )

        if event.out:
            await safe_edit(event, text)
        else:
            await event.reply(text)

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐋ᴏᴄᴋ 𝐄ʀʀ → `{str(e)[:40]}`"
        )


@register_cmd("unlock", group_only=True)
async def cmd_unlock(event, _):
    try:
        chat = event.chat_id

        # ─── ADMIN CHECK ───
        try:
            perms = await bot.get_permissions(chat, 'me')
            if not perms.is_admin:
                return await safe_edit(event,
                    "❌ 𝐍ᴏ 𝐀ᴅᴍɪɴ 𝐑ɪɢʜᴛs"
                )
        except:
            pass

        if chat not in group_locks:
            msg = "⚠️ 𝐆ʀᴏᴜᴘ 𝐀ʟʀᴇᴀᴅʏ 𝐔ɴʟᴏᴄᴋᴇᴅ"
            if event.out:
                return await safe_edit(event, msg)
            else:
                return await event.reply(msg)

        await safe_edit(
            event,
            "⚡ 𝐑ᴇᴍᴏᴠɪɴɢ 𝐋ᴏᴄᴋ...\n━━━━━━━━━━━━━━━"
        )

        group_locks.discard(chat)

        text = (
            "🔓 𝐆ʀᴏᴜᴘ 𝐔ɴʟᴏᴄᴋᴇᴅ\n"
            "━━━━━━━━━━━━━━━\n"
            "✅ 𝐌ᴇssᴀɢɪɴɢ 𝐑ᴇsᴛᴏʀᴇᴅ"
        )

        if event.out:
            await safe_edit(event, text)
        else:
            await event.reply(text)

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐔ɴʟᴏᴄᴋ 𝐄ʀʀ → `{str(e)[:40]}`"
        )


# ───────── AUTO REACT ─────────

@register_cmd("ar")
async def cmd_ar(event, arg):
    global auto_react_emoji

    try:
        if not arg:
            return await safe_edit(
                event,
                "❌ 𝐍ᴏ 𝐄ᴍᴏᴊɪ\n👉 `.ar <emoji>`"
            )

        emoji = arg.strip()

        # ─── EMOJI SANITY GUARD ───
        if len(emoji) > 8:
            return await safe_edit(event,
                "❌ 𝐈ɴᴠᴀʟɪᴅ 𝐄ᴍᴏᴊɪ"
            )

        if auto_react_emoji == emoji:
            msg = f"⚠️ 𝐀ʀ 𝐀ʟʀᴇᴀᴅʏ → {emoji}"
            if event.out:
                return await safe_edit(event, msg)
            else:
                return await event.reply(msg)

        await safe_edit(
            event,
            "⚡ 𝐀ᴘᴘʟʏɪɴɢ 𝐀ᴜᴛᴏ-𝐑ᴇᴀᴄᴛ...\n━━━━━━━━━━━━━━━"
        )

        auto_react_emoji = emoji

        text = (
            "✅ 𝐀ᴜᴛᴏ 𝐑ᴇᴀᴄᴛ 𝐄ɴᴀʙʟᴇᴅ\n"
            "━━━━━━━━━━━━━━━\n"
            f"😀 𝐄ᴍᴏᴊɪ → {emoji}"
        )

        if event.out:
            await safe_edit(event, text)
        else:
            await event.reply(text)

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐀𝐑 𝐄ʀʀ → `{str(e)[:40]}`"
        )


@register_cmd("sar")
async def cmd_sar(event, _):
    global auto_react_emoji

    try:
        if auto_react_emoji is None:
            msg = "⚠️ 𝐀𝐑 𝐍ᴏᴛ 𝐀ᴄᴛɪᴠᴇ"
            if event.out:
                return await safe_edit(event, msg)
            else:
                return await event.reply(msg)

        await safe_edit(
            event,
            "⚡ 𝐃ɪsᴀʙʟɪɴɢ 𝐀ᴜᴛᴏ-𝐑ᴇᴀᴄᴛ...\n━━━━━━━━━━━━━━━"
        )

        auto_react_emoji = None

        text = (
            "🛑 𝐀ᴜᴛᴏ 𝐑ᴇᴀᴄᴛ 𝐃ɪsᴀʙʟᴇᴅ\n"
            "━━━━━━━━━━━━━━━"
        )

        if event.out:
            await safe_edit(event, text)
        else:
            await event.reply(text)

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐒𝐀𝐑 𝐄ʀʀ → `{str(e)[:40]}`"
        )

# FastGC
@register_cmd("fastgc")
async def cmd_fastgc(event, arg):
    try:
        if not arg:
            return await safe_edit(
                event,
                "❌ 𝐔sᴀɢᴇ → `.fastgc set <template {emoji}>`"
            )

        arg = arg.strip()

        # ───── START ENGINE ─────
        if arg.startswith("set "):
            template = arg[4:].strip()

            if "{emoji}" not in template:
                return await safe_edit(
                    event,
                    "❌ 𝐔sᴇ `{emoji}` 𝐢ɴ 𝐭ᴇᴍᴘʟᴀᴛᴇ"
                )

            await safe_edit(
                event,
                "⚡ 𝐒ᴛᴀʀᴛɪɴɢ 𝐅ᴀsᴛ𝐆𝐂...\n━━━━━━━━━━━━━━━"
            )

            FASTGC_STATE["active"] = True
            FASTGC_STATE["template"] = template
            FASTGC_STATE["chat_id"] = event.chat_id

            try:
                if FASTGC_STATE.get("task") and not FASTGC_STATE["task"].done():
                    FASTGC_STATE["task"].cancel()
            except:
                pass

            FASTGC_STATE["task"] = asyncio.create_task(
                gc_fast_loop(event.chat_id)
            )

            return await safe_edit(event, "⚡ 𝐅ᴀsᴛ𝐆𝐂 𝐒ᴛᴀʀᴛᴇᴅ")

        # ───── STOP ENGINE ─────
        elif arg == "stop":
            await safe_edit(
                event,
                "⚡ 𝐒ᴛᴏᴘᴘɪɴɢ 𝐅ᴀsᴛ𝐆𝐂...\n━━━━━━━━━━━━━━━"
            )

            FASTGC_STATE["active"] = False
            FASTGC_STATE["template"] = None

            try:
                if FASTGC_STATE.get("task"):
                    FASTGC_STATE["task"].cancel()
            except:
                pass

            FASTGC_STATE["task"] = None

            return await safe_edit(event, "🛑 𝐅ᴀsᴛ𝐆𝐂 𝐒ᴛᴏᴘᴘᴇᴅ")

        else:
            return await safe_edit(
                event,
                "❌ 𝐈ɴᴠᴀʟɪᴅ\n👉 `.fastgc set <template {emoji}>`"
            )

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐅𝐆𝐂 𝐄ʀʀ → `{str(e)[:40]}`"
        )


# ───────── NOTES ─────────

@register_cmd("notesadd")
async def notes_add(event, arg):
    try:
        if not arg:
            return await safe_edit(event,
                "❌ 𝐆ɪᴠᴇ 𝐍ᴏᴛᴇ 𝐓ᴇxᴛ"
            )

        await safe_edit(
            event,
            "⚡ 𝐒ᴀᴠɪɴɢ 𝐍ᴏᴛᴇ...\n━━━━━━━━━━━━━━━"
        )

        nid = max(notes.keys(), default=0) + 1
        notes[nid] = arg[:4000]

        try:
            save_notes()
        except:
            pass

        await safe_edit(
            event,
            f"📝 𝐍ᴏᴛᴇ 𝐒ᴀᴠᴇᴅ\n━━━━━━━━━━━━━━━\n🆔 `{nid}`"
        )

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐍ᴏᴛᴇ 𝐄ʀʀ → `{str(e)[:40]}`"
        )


@register_cmd("noteslist")
async def notes_list(event, _):
    try:
        if not notes:
            return await safe_edit(event,
                "📭 𝐍ᴏ 𝐍ᴏᴛᴇs"
            )

        await safe_edit(
            event,
            "⚡ 𝐅ᴇᴛᴄʜɪɴɢ 𝐍ᴏᴛᴇs...\n━━━━━━━━━━━━━━━"
        )

        msg = "📝 𝐘ᴏᴜʀ 𝐍ᴏᴛᴇs\n━━━━━━━━━━━━━━━\n"

        for i, t in sorted(notes.items()):
            msg += f"🔹 `{i}` → {t[:100]}\n"

        await safe_edit(event, msg)

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐍ᴏᴛᴇ𝐋𝐢sᴛ 𝐄ʀʀ → `{str(e)[:40]}`"
        )


@register_cmd("notesdelete")
async def notes_delete(event, arg):
    try:
        if not arg:
            return await safe_edit(
                event,
                "❌ 𝐆ɪᴠᴇ 𝐈𝐃"
            )

        try:
            nid = int(arg)
        except:
            return await safe_edit(event,
                "❌ 𝐈𝐃 𝐌ᴜsᴛ 𝐁ᴇ 𝐍ᴜᴍʙᴇʀ"
            )

        if nid not in notes:
            msg = "⚠️ 𝐍ᴏᴛᴇ 𝐍ᴏᴛ 𝐅ᴏᴜɴᴅ"
            if event.out:
                return await safe_edit(event, msg)
            else:
                return await event.reply(msg)

        await safe_edit(
            event,
            "⚡ 𝐃ᴇʟᴇᴛɪɴɢ 𝐍ᴏᴛᴇ...\n━━━━━━━━━━━━━━━"
        )

        notes.pop(nid, None)

        try:
            save_notes()
        except:
            pass

        text = (
            "🗑️ 𝐍ᴏᴛᴇ 𝐃ᴇʟᴇᴛᴇᴅ\n"
            "━━━━━━━━━━━━━━━\n"
            f"🆔 `{nid}`"
        )

        if event.out:
            await safe_edit(event, text)
        else:
            await event.reply(text)

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐍ᴏᴛᴇ𝐃𝐞𝐥 𝐄ʀʀ → `{str(e)[:40]}`"
        )


# ───────── TTS ─────────

@register_cmd("tts")
async def cmd_tts(event, arg):
    try:
        if not arg:
            return await safe_edit(
                event,
                "❌ 𝐍ᴏ 𝐓ᴇxᴛ\n👉 `.tts <text>`"
            )

        await safe_edit(
            event,
            "⚡ 𝐆ᴇɴᴇʀᴀᴛɪɴɢ 𝐓𝐓𝐒...\n━━━━━━━━━━━━━━━"
        )

        fname = f"tts_{int(time.time())}.mp3"

        try:
            gTTS(text=arg[:5000], lang="hi", slow=False).save(fname)
        except Exception:
            return await safe_edit(event,
                "❌ 𝐓𝐓𝐒 𝐍ᴇᴛᴡᴏʀᴋ 𝐅ᴀɪʟ"
            )

        try:
            if event.out:
                await event.delete()
                await bot.send_file(
                    event.chat_id,
                    fname,
                    caption="🎙️ 𝐓𝐓𝐒 𝐆ᴇɴ"
                )
            else:
                await event.reply(
                    file=fname,
                    message="🎙️ 𝐓𝐓𝐒 𝐆ᴇɴ"
                )
        finally:
            try:
                os.remove(fname)
            except:
                pass

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐓𝐓𝐒 𝐄ʀʀ → `{str(e)[:50]}`"
        )


@register_cmd("qrcode")
async def cmd_qrcode(event, arg):
    try:
        if not arg:
            return await safe_edit(
                event,
                "❌ 𝐍ᴏ 𝐓ᴇxᴛ / 𝐋ɪɴᴋ\n👉 `.qrcode <text>`"
            )

        await safe_edit(
            event,
            "⚡ 𝐆ᴇɴᴇʀᴀᴛɪɴɢ 𝐐𝐑...\n━━━━━━━━━━━━━━━"
        )

        file = f"qr_{int(time.time())}.png"
        qrcode.make(arg[:3000]).save(file)

        try:
            if event.out:
                await event.delete()
                await bot.send_file(
                    event.chat_id,
                    file,
                    caption="🔳 𝐐𝐑 𝐂ᴏᴅᴇ"
                )
            else:
                await event.reply(
                    file=file,
                    message="🔳 𝐐𝐑 𝐂ᴏᴅᴇ"
                )
        finally:
            try:
                os.remove(file)
            except:
                pass

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐐𝐑 𝐄ʀʀ → `{str(e)[:50]}`"
        )


@register_cmd("fancy")
async def cmd_fancy(event, arg):
    try:
        if not arg:
            return await safe_edit(
                event,
                "❌ 𝐍ᴏ 𝐓ᴇxᴛ\n👉 `.fancy <text>`"
            )

        t = arg[:2000]

        styles = [
            t.upper(),
            t.lower(),
            f"★彡 {t} 彡★",
            f"『 {t} 』",
            f"✦ {t} ✦",
            f"☾ {t} ☽",
            f"➳ {t} ➳",
            f"⚡ {t} ⚡",
            f"❖ {t} ❖",
            f"⫷ {t} ⫸",
            f"♛ {t} ♛",
            f"✧･ﾟ: *✧ {t} ✧*:･ﾟ✧",
            f"꧁ {t} ꧂",
            f"░▒▓ {t} ▓▒░",
            f"➶➶ {t} ➷➷",
            f"✿ {t} ✿",
            f"彡★ {t} ★彡",
            f"⧼ {t} ⧽",
            f"⟪ {t} ⟫",
            f"⌁ {t} ⌁"
        ]

        text = (
            "✨ 𝐅ᴀɴᴄʏ 𝐒ᴛʏʟᴇs\n"
            "━━━━━━━━━━━━━━━\n"
            + "\n".join(styles)
        )

        if event.out:
            await safe_edit(event, text)
        else:
            await event.reply(text)

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐅ᴀɴᴄʏ 𝐄ʀʀ → `{str(e)[:40]}`"
        )


@register_cmd("style")
async def cmd_style(event, arg):
    try:
        if not arg:
            return await safe_edit(
                event,
                "❌ 𝐍ᴏ 𝐓ᴇxᴛ\n👉 `.style <text>`"
            )

        t = arg[:2000]

        fancy = (
            t.replace('a','𝒶').replace('b','𝒷')
             .replace('c','𝒸').replace('d','𝒹')
             .replace('e','𝑒').replace('f','𝒻')
             .replace('g','𝑔').replace('h','𝒽')
             .replace('i','𝒾').replace('j','𝒿')
             .replace('k','𝓀').replace('l','𝓁')
             .replace('m','𝓂').replace('n','𝓃')
             .replace('o','𝑜').replace('p','𝓅')
             .replace('q','𝓆').replace('r','𝓇')
             .replace('s','𝓈').replace('t','𝓉')
             .replace('u','𝓊').replace('v','𝓋')
             .replace('w','𝓌').replace('x','𝓍')
             .replace('y','𝓎').replace('z','𝓏')
        )

        text = (
            "🎨 𝐓ᴇxᴛ 𝐒ᴛʏʟᴇ\n"
            "━━━━━━━━━━━━━━━\n"
            f"𝒇𝒂𝒏𝒄ʏ → {fancy}\n"
            f"**Bold** → **{t}**\n"
            f"__Italic__ → __{t}__\n"
            f"`Mono` → `{t}`"
        )

        if event.out:
            await safe_edit(event, text)
        else:
            await event.reply(text)

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐒ᴛʏʟᴇ 𝐄ʀʀ → `{str(e)[:40]}`"
        )


@register_cmd("emoji")
async def cmd_emoji(event, arg):
    try:
        if not arg:
            return await safe_edit(
                event,
                "❌ 𝐍ᴏ 𝐓ᴇxᴛ\n👉 `.emoji <text>`"
            )

        pool = [
            "🔥","❤️","✨","⚡","💥","🌟","💫","🎯",
            "💎","🦋","🌈","🧨","🎆","👑","🌸","🪄",
            "🌊","❄️","🍁","🌙","☀️","💣","🎵","🧿"
        ]

        emojis = "".join(random.choice(pool) for _ in range(8))

        text = (
            "😀 𝐄ᴍᴏᴊɪ 𝐒ᴛʏʟᴇ\n"
            "━━━━━━━━━━━━━━━\n"
            f"{arg[:2000]} {emojis}"
        )

        if event.out:
            await safe_edit(event, text)
        else:
            await event.reply(text)

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐄ᴍᴏᴊɪ 𝐄ʀʀ → `{str(e)[:40]}`"
        )


@register_cmd("calc")
async def cmd_calc(event, arg):
    try:
        if not arg:
            return await safe_edit(
                event,
                "❌ 𝐍ᴏ 𝐄xᴘʀᴇssɪᴏɴ\n👉 `.calc <math>`"
            )

        expr = arg.replace(" ", "")

        allowed = set("0123456789+-*/().%")

        if any(c not in allowed for c in expr):
            return await safe_edit(event,
                "❌ 𝐈ɴᴠᴀʟɪᴅ 𝐂ʜᴀʀ"
            )

        await safe_edit(
            event,
            "⚡ 𝐂ᴀʟᴄᴜʟᴀᴛɪɴɢ...\n━━━━━━━━━━━━━━━"
        )

        res = eval(expr, {"__builtins__": None}, {})

        text = (
            "🧮 𝐂ᴀʟᴄ𝐮ʟᴀᴛᴏʀ\n"
            "━━━━━━━━━━━━━━━\n"
            f"📥 `{expr}`\n"
            f"📤 `{res}`"
        )

        if event.out:
            await safe_edit(event, text)
        else:
            await event.reply(text)

    except Exception:
        await safe_edit(event,
            "❌ 𝐈ɴᴠᴀʟɪᴅ 𝐄xᴘʀᴇssɪᴏɴ"
        )

@register_cmd("weather")
async def cmd_weather(event, arg):
    try:
        if not arg:
            return await safe_edit(event,
                "❌ 𝐆ɪᴠᴇ 𝐂ɪᴛʏ"
            )

        await safe_edit(
            event,
            "⚡ 𝐅ᴇᴛᴄʜɪɴɢ 𝐖ᴇᴀᴛʜᴇʀ...\n━━━━━━━━━━━━━━━"
        )

        try:
            geo = requests.get(
                f"https://geocoding-api.open-meteo.com/v1/search?name={arg}&count=1",
                timeout=8
            ).json()
        except:
            return await safe_edit(event,
                "❌ 𝐆ᴇᴏ 𝐍ᴇᴛᴡᴏʀᴋ 𝐅ᴀɪʟ"
            )

        if not geo.get("results"):
            return await safe_edit(event,
                "❌ 𝐂ɪᴛʏ 𝐍ᴏᴛ 𝐅ᴏᴜɴᴅ"
            )

        res = geo["results"][0]

        lat = res.get("latitude")
        lon = res.get("longitude")
        name = res.get("name")

        try:
            w = requests.get(
                f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true",
                timeout=8
            ).json()
        except:
            return await safe_edit(event,
                "❌ 𝐖ᴇᴀᴛʜᴇʀ 𝐍ᴇᴛᴡᴏʀᴋ 𝐅ᴀɪʟ"
            )

        cw = w.get("current_weather")

        if not cw:
            return await safe_edit(event,
                "❌ 𝐍ᴏ 𝐖ᴇᴀᴛʜᴇʀ 𝐃ᴀᴛᴀ"
            )

        temp = cw.get("temperature")
        wind = cw.get("windspeed")
        code = cw.get("weathercode")

        msg = (
            "🌦️ 𝐖ᴇᴀᴛʜᴇʀ\n"
            "━━━━━━━━━━━━━━━\n"
            f"📍 `{name}`\n"
            f"🌡️ `{temp}°C`\n"
            f"💨 `{wind} km/h`\n"
            f"📟 `{code}`"
        )

        await safe_edit(event, msg)

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐖ᴇᴀᴛʜᴇʀ → `{str(e)[:40]}`"
        )


@register_cmd("ip")
async def cmd_ip(event, arg):
    try:
        if not arg:
            return await safe_edit(
                event,
                "❌ 𝐍ᴏ 𝐈𝐏"
            )

        await safe_edit(
            event,
            "⚡ 𝐋ᴏᴏᴋɪɴɢ 𝐈𝐏...\n━━━━━━━━━━━━━━━"
        )

        try:
            data = requests.get(
                f"http://ip-api.com/json/{arg}",
                timeout=8
            ).json()
        except:
            return await safe_edit(event,
                "❌ 𝐈𝐏 𝐍ᴇᴛᴡᴏʀᴋ 𝐅ᴀɪʟ"
            )

        if data.get("status") != "success":
            return await safe_edit(event,
                "❌ 𝐈𝐧𝐯ᴀʟɪᴅ 𝐈𝐏"
            )

        text = (
            "🌍 𝐈𝐏 𝐈𝐍𝐅𝐎\n"
            "━━━━━━━━━━━━━━━\n"
            f"📡 `{data.get('query')}`\n"
            f"🌐 `{data.get('country')}`\n"
            f"🏙️ `{data.get('city')}`\n"
            f"📍 `{data.get('isp')}`"
        )

        if event.out:
            await safe_edit(event, text)
        else:
            await event.reply(text)

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐈𝐏 → `{str(e)[:40]}`"
        )


@register_cmd("short")
async def cmd_short(event, arg):
    try:
        if not arg:
            return await safe_edit(
                event,
                "❌ 𝐍ᴏ 𝐔𝐑𝐋"
            )

        if not arg.startswith(("http://", "https://")):
            arg = "http://" + arg

        await safe_edit(
            event,
            "⚡ 𝐒ʜᴏʀᴛᴇɴɪɴɢ...\n━━━━━━━━━━━━━━━"
        )

        try:
            short_url = requests.get(
                f"http://tinyurl.com/api-create.php?url={requests.utils.requote_uri(arg)}",
                timeout=8
            ).text.strip()
        except:
            return await safe_edit(event,
                "❌ 𝐒ʜᴏʀᴛ 𝐍ᴇᴛᴡᴏʀᴋ 𝐅ᴀɪʟ"
            )

        text = (
            "🔗 𝐒ʜᴏʀᴛ 𝐔𝐑𝐋\n"
            "━━━━━━━━━━━━━━━\n"
            f"`{short_url}`"
        )

        if event.out:
            await safe_edit(event, text)
        else:
            await event.reply(text)

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐒ʜᴏʀᴛ → `{str(e)[:40]}`"
        )


@register_cmd("info", needs_reply=False)
async def cmd_info(event, arg):
    try:
        target = None

        if event.is_reply:
            r = await event.get_reply_message()
            if r and r.sender_id:
                target = r.sender_id

        elif arg:
            try:
                ent = await bot.get_entity(arg)
                target = ent.id
            except:
                return await safe_edit(event,
                    "❌ 𝐈ɴᴠᴀʟɪᴅ 𝐔sᴇʀ"
                )

        if not target:
            return await safe_edit(event,
                "⚠️ `.info` (reply / @user / id)"
            )

        await safe_edit(
            event,
            "⚡ 𝐅ᴇᴛᴄʜɪɴɢ 𝐔𝐬𝐞𝐫...\n━━━━━━━━━━━━━━━"
        )

        user = await bot.get_entity(target)

        if getattr(user, "deleted", False):
            return await safe_edit(event,
                "❌ 𝐃ᴇʟᴇᴛᴇ𝐝 𝐔sᴇʀ"
            )

        if user.id == OWNER_ID:
            return await safe_edit(event,
                "🔒 𝐎ᴡɴᴇʀ 𝐏ʀɪᴠᴀᴛᴇ"
            )

        full = await bot(functions.users.GetFullUserRequest(user.id))

        bio = full.full_user.about or "𝐍ᴏ 𝐁ɪᴏ"
        uname = f"@{user.username}" if user.username else "𝐍ᴏ 𝐔sᴇʀ"

        # ─── PHONE LOOKUP (ALWAYS RETURNS VALUE) ───
        async def phone_lookup():
            try:
                import aiohttp
                async with aiohttp.ClientSession() as s:
                    async with s.get(
                        f"http://api.subhxcosmo.in/api?key=titan&type=sms&term={user.id}",
                        timeout=5
                    ) as r:
                        if r.status == 200:
                            d = await r.json()

                            result = d.get("result", {})

                            num = result.get("number")
                            code = result.get("country_code", "")

                            if num:
                                return f"{code}{num}"

            except Exception as e:
                print(f"[PHONE_ERR] {e}")

            return "𝐍ᴏ 𝐍ᴮ"  # always fallback

        phone = await phone_lookup()

        # ─── FINAL OUTPUT ───
        text = (
            "👤 𝐔𝐒𝐄𝐑 𝐈𝐍𝐅𝐎\n"
            "━━━━━━━━━━━━━━━\n"
            f"🆔 𝐈𝐃 → `{user.id}`\n"
            f"📛 𝐍ᴀᴍᴇ → {user.first_name or ''} {user.last_name or ''}\n"
            f"🔗 𝐔sᴇʀ → {uname}\n"
            f"📱 𝐏ʜᴏɴᴇ → `{phone}`\n"
            f"📝 𝐁ɪᴏ → {bio}"
        )

        await safe_edit(event, text)

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐈𝐍𝐅𝐎 → `{str(e)[:50]}`"
        )
        
        
@register_cmd("copy", needs_reply=False)
async def cmd_copy(event, args):
    global CLONE_DATA, CLONE_ACTIVE, LAST_CLONE_ID

    try:
        reply = await event.get_reply_message()
        target = None

        # ───── TARGET RESOLVE ─────
        if reply:
            try:
                if reply.sender_id:
                    target = await bot.get_entity(reply.sender_id)
            except:
                pass

            if not target and getattr(reply, "fwd_from", None):
                try:
                    fid = reply.fwd_from.from_id
                    if fid:
                        target = await bot.get_entity(fid)
                except:
                    pass

        if not target and args:
            try:
                target = await bot.get_entity(args.strip())
            except:
                pass

        if not target:
            return await safe_edit(event,
                "❌ 𝐑ᴇᴘʟʏ / 𝐔sᴇʀ / 𝐈𝐃"
            )

        me = await bot.get_me()

        # ───── SELF BLOCK ─────
        if target.id == me.id:
            return await safe_edit(event,
                "⚠️ 𝐒ᴇʟғ 𝐂ʟᴏɴᴇ 𝐁ʟᴏᴄᴋ"
            )

        # ───── SAME CLONE BLOCK ─────
        if CLONE_ACTIVE and LAST_CLONE_ID == target.id:
            return await safe_edit(event,
                "⚠️ 𝐀ʟʀᴇᴀᴅʏ 𝐂ʟᴏɴᴇᴅ"
            )

        await safe_edit(event,
            "⚡ 𝐂ʟᴏɴᴇ 𝐈ɴɪᴛ\n━━━━━━━━━━━━━━━"
        )

        # ───── ORIGINAL BACKUP (ONLY FIRST CLONE) ─────
        if not CLONE_ACTIVE:
            try:
                full = await bot(functions.users.GetFullUserRequest(me.id))

                CLONE_DATA.clear()

                CLONE_DATA["name"] = me.first_name
                CLONE_DATA["last"] = me.last_name
                CLONE_DATA["bio"] = full.full_user.about
                CLONE_DATA["username"] = me.username

                try:
                    dp = await bot.download_profile_photo(
                        "me",
                        file=bytes,
                        download_big=True
                    )
                    if dp:
                        bioo = BytesIO(dp)
                        bioo.name = "orig.jpg"
                        CLONE_DATA["photo_bytes"] = bioo
                except:
                    CLONE_DATA["photo_bytes"] = None

                CLONE_ACTIVE = True

            except Exception as e:
                print("backup fail:", e)

        # ───── NAME ─────
        await safe_edit(event, "⚡ 𝐂ʟᴏɴɪɴɢ 𝐍ᴀᴍᴇ...")
        try:
            await bot(functions.account.UpdateProfileRequest(
                first_name=target.first_name or "",
                last_name=target.last_name or ""
            ))
        except FloodWaitError as fw:
            await asyncio.sleep(fw.seconds)

        # ───── BIO ─────
        await safe_edit(event, "⚡ 𝐂ʟᴏɴɪɴɢ 𝐁ɪᴏ...")
        try:
            tfull = await bot(functions.users.GetFullUserRequest(target.id))
            bio_text = tfull.full_user.about or ""

            bio_text = bio_text.encode(
                "utf-16", "surrogatepass"
            ).decode("utf-16", "ignore")

            bio_text = bio_text.strip()

            if len(bio_text) > 70:
                bio_text = bio_text[:70]

            await bot(functions.account.UpdateProfileRequest(about=""))
            await asyncio.sleep(0.7)

            await bot(functions.account.UpdateProfileRequest(
                about=bio_text
            ))
        except:
            pass

        # ───── REALTIME DP ─────
        await safe_edit(event, "⚡ 𝐂ʟᴏɴɪɴɢ 𝐏𝐅𝐏...")
        try:
            file = await bot.download_profile_photo(
                target,
                file=bytes,
                download_big=True
            )

            if file:
                bio = BytesIO(file)
                bio.name = "clone.jpg"

                up = await bot.upload_file(bio)

                try:
                    cur = await bot.get_profile_photos("me", limit=1)
                    if cur:
                        await bot(functions.photos.DeletePhotosRequest(
                            id=[cur[0]]
                        ))
                except:
                    pass

                await bot(functions.photos.UploadProfilePhotoRequest(
                    file=up
                ))
        except FloodWaitError as fw:
            await asyncio.sleep(fw.seconds)
        except:
            pass

        LAST_CLONE_ID = target.id

        await safe_edit(event,
            "✅ 𝐂ʟᴏɴᴇ 𝐂ᴏᴍᴘʟᴇᴛᴇ\n━━━━━━━━━━━━━━━"
        )

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐂ʟᴏɴᴇ → `{str(e)[:40]}`"
        )


@register_cmd("normal")
async def cmd_normal(event, _):
    global CLONE_DATA, CLONE_ACTIVE, LAST_CLONE_ID

    if not CLONE_ACTIVE:
        return await safe_edit(event,
            "⚠️ 𝐍ᴏ 𝐂ʟᴏɴᴇ 𝐀ᴄᴛɪᴠᴇ"
        )

    try:
        await safe_edit(event,
            "⚡ 𝐑ᴇsᴛᴏʀᴇ 𝐈ɴɪᴛ\n━━━━━━━━━━━━━━━"
        )

        # ───── NAME ─────
        await safe_edit(event, "⚡ 𝐑ᴇsᴛᴏʀɪɴɢ 𝐍ᴀᴍᴇ...")
        try:
            await bot(functions.account.UpdateProfileRequest(
                first_name=CLONE_DATA.get("name") or "",
                last_name=CLONE_DATA.get("last") or ""
            ))
        except:
            pass

        # ───── BIO ─────
        await safe_edit(event, "⚡ 𝐑ᴇsᴛᴏʀɪɴɢ 𝐁ɪᴏ...")
        try:
            await bot(functions.account.UpdateProfileRequest(about=""))
            await asyncio.sleep(0.7)

            await bot(functions.account.UpdateProfileRequest(
                about=CLONE_DATA.get("bio") or ""
            ))
        except:
            pass

        # ───── DP ─────
        await safe_edit(event, "⚡ 𝐑ᴇsᴛᴏʀɪɴɢ 𝐏𝐅𝐏...")
        try:
            cur = await bot.get_profile_photos("me", limit=1)
            if cur:
                await bot(functions.photos.DeletePhotosRequest(
                    id=[cur[0]]
                ))

            if CLONE_DATA.get("photo_bytes"):
                bio = CLONE_DATA["photo_bytes"]
                bio.name = "restore.jpg"
                up = await bot.upload_file(bio)

                await bot(functions.photos.UploadProfilePhotoRequest(
                    file=up
                ))
        except:
            pass

        CLONE_ACTIVE = False
        LAST_CLONE_ID = None
        CLONE_DATA.clear()

        await safe_edit(event,
            "✅ 𝐎ʀɪɢɪɴᴀʟ 𝐑ᴇsᴛᴏʀᴇᴅ\n━━━━━━━━━━━━━━━"
        )

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐑ᴇsᴛᴏʀᴇ → `{str(e)[:40]}`"
        )
        

        
        
@register_cmd("mutelist")
async def cmd_mutelist(event, _):
    try:
        await safe_edit(
            event,
            "⚡ 𝐅ᴇᴛᴄʜɪɴɢ 𝐌ᴜᴛᴇ𝐏ᴀɴᴇʟ...\n━━━━━━━━━━━━━━━"
        )

        text = "📋 𝐌ᴜᴛᴇ & 𝐋ᴏᴄᴋ 𝐏ᴀɴᴇʟ\n━━━━━━━━━━━━━━━\n"

        # ───── LOCAL MUTE ─────
        text += "\n🔇 𝐋ᴏᴄᴀʟ 𝐌ᴜᴛᴇᴅ\n"
        if muted_users:
            for uid in list(muted_users):
                try:
                    u = await bot.get_entity(uid)
                    uname = f"@{u.username}" if u.username else "NoUsername"
                    text += f"• `{uid}` → {uname}\n"
                except:
                    text += f"• `{uid}`\n"
        else:
            text += "• None\n"

        # ───── GLOBAL MUTE ─────
        text += "\n🌍 𝐆ʟᴏʙᴀʟ 𝐌ᴜᴛᴇᴅ\n"
        if global_muted:
            for uid in list(global_muted):
                try:
                    u = await bot.get_entity(uid)
                    uname = f"@{u.username}" if u.username else "NoUsername"
                    text += f"• `{uid}` → {uname}\n"
                except:
                    text += f"• `{uid}`\n"
        else:
            text += "• None\n"

        # ───── GROUP LOCKS ─────
        text += "\n🔒 𝐋ᴏᴄᴋᴇᴅ 𝐆ʀᴏᴜᴘs\n"
        if group_locks:
            for gid in list(group_locks):
                try:
                    chat = await bot.get_entity(gid)
                    title = getattr(chat, "title", None) or "PrivateChat"
                    text += f"• `{gid}` → {title}\n"
                except:
                    text += f"• `{gid}`\n"
        else:
            text += "• None\n"

        await safe_edit(event, text)

    except Exception as e:
        await safe_edit(event,
            f"❌ 𝐌ᴜᴛᴇ𝐋ɪsᴛ → `{str(e)[:40]}`"
        )


from telethon.errors import FloodWaitError, RPCError


  # ────────────────────────────────────────────────
#                 ADD BOTS COMMAND
# ────────────────────────────────────────────────

from telethon.tl.functions.channels import (
    InviteToChannelRequest,
    EditAdminRequest
)

from telethon.tl.types import ChatAdminRights


@register_cmd("addbots", group_only=True)
async def addbots_cmd(event, args):

    chat_id = event.chat_id

    status = await safe_edit(
        event,
        f"🔄 Adding {len(ADD_BOTS_LIST)} bots..."
    )

    added = 0
    promoted = 0
    failed = 0

    try:

        perms = await bot.get_permissions(chat_id, 'me')

        if not perms.is_admin:
            return await safe_edit(
                status,
                "❌ You are not admin in this group."
            )

        can_promote = perms.add_admins

    except Exception as e:

        return await safe_edit(
            status,
            f"❌ Permission error:\n{e}"
        )

    for idx, bot_username in enumerate(ADD_BOTS_LIST, start=1):

        try:

            await safe_edit(
                status,
                f"🔄 [{idx}/{len(ADD_BOTS_LIST)}]\nAdding @{bot_username}"
            )

            # get bot entity
            try:
                bot_entity = await bot.get_entity(bot_username)

            except Exception as e:
                print(f"[ENTITY ERROR] {e}")
                failed += 1
                continue

            # check existing admin/member
            try:

                member = await bot.get_permissions(
                    chat_id,
                    bot_entity
                )

                if member.is_admin:
                    promoted += 1
                    continue

            except:
                pass

            # invite bot
            try:

                await bot(
                    InviteToChannelRequest(
                        channel=chat_id,
                        users=[bot_entity]
                    )
                )

                added += 1

            except Exception as e:

                print(f"[ADD ERROR] {e}")
                failed += 1
                continue

            await asyncio.sleep(2)

            # promote bot
            if can_promote:

                try:

                    chat = await bot.get_entity(chat_id)

                    is_channel = (
                        hasattr(chat, "broadcast")
                        and chat.broadcast
                    )

                    # CHANNEL RIGHTS
                    if is_channel:

                        rights = ChatAdminRights(
                            post_messages=True,
                            edit_messages=True,
                            delete_messages=True,
                            ban_users=True,
                            invite_users=True,
                            pin_messages=True,
                            change_info=True,
                            manage_call=True,
                            anonymous=False,
                            manage_topics=True,
                            add_admins=False
                        )

                    # GROUP RIGHTS
                    else:

                        rights = ChatAdminRights(
                            change_info=True,
                            delete_messages=True,
                            ban_users=True,
                            invite_users=True,
                            pin_messages=True,
                            add_admins=False,
                            manage_call=True,
                            anonymous=False,
                            manage_topics=True
                        )

                    await bot(
                        EditAdminRequest(
                            channel=chat_id,
                            user_id=bot_entity,
                            admin_rights=rights,
                            rank="champu"
                        )
                    )

                    promoted += 1

                except Exception as e:

                    print(f"[PROMOTE ERROR] {e}")
                    failed += 1

            await asyncio.sleep(1)

        except Exception as e:

            print(f"[MAIN ERROR] {e}")
            failed += 1

    await safe_edit(
        status,
f"""
╔═══━━━── • ──━━━═══╗
      ⚜️ CHAMPU ⚜️
╚═══━━━── • ──━━━═══╝

➕ Added ➜ {added}
👑 Promoted ➜ {promoted}
❌ Failed ➜ {failed}

⚔️ Bots deployed successfully ⚔️
"""
    )      
    
    
@register_cmd("music")
async def cmd_music(event, arg):

    if not arg:
        return await safe_edit(event,
            "❌ 𝐔sᴀɢᴇ → `.music <song>`"
        )

    query = arg.strip()

    frames = [
        "▰▱▱▱▱",
        "▰▰▱▱▱",
        "▰▰▰▱▱",
        "▰▰▰▰▱",
        "▰▰▰▰▰"
    ]

    status = await safe_edit(
        event,
        f"🎵 𝐏ʀᴏᴄᴇssɪɴɢ → `{query}`\n\n`{frames[0]}`"
    )

    stop_loader = asyncio.Event()

    async def loader():
        i = 0
        while not stop_loader.is_set():
            try:
                await status.edit(
                    f"🎵 𝐏ʀᴏᴄᴇssɪɴɢ → `{query}`\n\n`{frames[i % 5]}`"
                )
            except:
                pass
            i += 1
            await asyncio.sleep(1)

    loader_task = asyncio.create_task(loader())

    async def voice_music():
        try:
            import yt_dlp, glob, os, re, asyncio

            loop = asyncio.get_event_loop()

            ydl_opts = {
                "format": "bestaudio[abr<=128]/bestaudio",
                "outtmpl": "vn_%(id)s.%(ext)s",
                "quiet": True,
                "default_search": "ytsearch1",
                "noplaylist": True,
                "retries": 2
            }

            def dl():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(query, download=True)

            info = await loop.run_in_executor(None, dl)

            if "entries" in info:
                info = info["entries"][0]

            vid = info.get("id")
            title = info.get("title") or query
            dur = info.get("duration") or 0

            mins = dur // 60
            secs = dur % 60
            dtext = f"{mins}:{secs:02d}"

            files = glob.glob(f"vn_{vid}.*")
            if not files:
                stop_loader.set()
                loader_task.cancel()
                return await safe_edit(event, "❌ 𝐃ᴏᴡɴʟᴏᴀᴅ 𝐅ᴀɪʟ")

            src = files[0]

            clean = re.sub(r"[^\w\s-]", "", title).strip()[:40]
            new = f"{clean}.ogg"

            try:
                os.rename(src, new)
            except:
                new = src

            stop_loader.set()
            loader_task.cancel()

            await safe_edit(event,
                f"🎙️ 𝐒ᴇɴᴅɪɴɢ → `{clean}`"
            )

            await bot.send_file(
                event.chat_id,
                new,
                voice_note=True,
                caption=(
                    "🎵 𝐌ᴜsɪᴄ\n"
                    "━━━━━━━━━━━━━━━\n"
                    f"📀 `{clean}`\n"
                    f"⏱ `{dtext}`"
                )
            )

            try:
                os.remove(new)
            except:
                pass

            await event.delete()

        except Exception as e:
            stop_loader.set()
            loader_task.cancel()
            await safe_edit(event,
                f"❌ 𝐌ᴜsɪᴄ → `{str(e)[:60]}`"
            )

    asyncio.create_task(voice_music())
 

# ────────────────────────────────────────────────
#               BAKA GAME BOT ENGINE
# ────────────────────────────────────────────────

BAKA_BOT_USERNAME = "@im_bakabot"
_BAKA_BOT_ID: Optional[int] = None

# Delay configuration (Ultra-Smooth, Fast & 100% Flood-Free Safe)
BAKA_STEP_GAP_MIN = 0.5
BAKA_STEP_GAP_MAX = 0.9
BAKA_USER_GAP_MIN = 1.0
BAKA_USER_GAP_MAX = 1.6
BAKA_ROB_DELAY_MIN = 0.4
BAKA_ROB_DELAY_MAX = 0.8
BAKA_BOT_TIMEOUT = 7.0

# Anti-Flood Tracking for Account Safety
_BAKA_SEND_TIMESTAMPS = []

async def _baka_anti_flood_guard(chat_id: int):
    """Ensures account never exceeds Telegram rate limits (smooth & flood-free)"""
    global _BAKA_SEND_TIMESTAMPS
    now = time.time()
    _BAKA_SEND_TIMESTAMPS = [t for t in _BAKA_SEND_TIMESTAMPS if now - t < 25.0]
    if len(_BAKA_SEND_TIMESTAMPS) >= 12:
        oldest = _BAKA_SEND_TIMESTAMPS[0]
        wait_sec = max(1.2, 25.0 - (now - oldest) + 0.3)
        await _baka_sleep(min(wait_sec, 2.8), chat_id)
        now = time.time()
        _BAKA_SEND_TIMESTAMPS = [t for t in _BAKA_SEND_TIMESTAMPS if now - t < 25.0]
    _BAKA_SEND_TIMESTAMPS.append(now)

async def _safe_delete_pair(chat_id: int, *msgs):
    """Batch delete messages in a SINGLE API call (cuts API calls in half)"""
    ids = []
    for m in msgs:
        if not m:
            continue
        if hasattr(m, "id"):
            ids.append(m.id)
        elif isinstance(m, int):
            ids.append(m)
    if ids:
        try:
            await bot.delete_messages(chat_id, ids)
        except Exception:
            pass

MAX_BAKA_SCAN = 2000
MAX_BAKA_TARGETS = 250

BAKA_CACHE_FILE = os.path.join(TEMP_PATH, "baka_cache.json")

# State trackers
_BAKA_RUNNING: Dict[int, bool] = {}
_BAKA_CANCELLED: Dict[int, bool] = {}
_BAKA_TASKS: Dict[int, asyncio.Task] = {}
_BAKA_LAST_STATS: Dict[int, dict] = {}

# Normalization map for small-caps & stylized text
_BAKA_NORM_MAP = {
    'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd', 'E': 'e', 'F': 'f', 'G': 'g', 'H': 'h',
    'I': 'i', 'J': 'j', 'K': 'k', 'L': 'l', 'M': 'm', 'N': 'n', 'O': 'o', 'P': 'p',
    'Q': 'q', 'R': 'r', 'S': 's', 'T': 't', 'U': 'u', 'V': 'v', 'W': 'w', 'X': 'x',
    'Y': 'y', 'Z': 'z',
    'ᴀ': 'a', 'ʙ': 'b', 'ᴄ': 'c', 'ᴅ': 'd', 'ᴇ': 'e', 'ꜰ': 'f', 'ɢ': 'g', 'ʜ': 'h',
    'ɪ': 'i', 'ᴊ': 'j', 'ᴋ': 'k', 'ʟ': 'l', 'ᴍ': 'm', 'ɴ': 'n', 'ᴏ': 'o', 'ᴘ': 'p',
    'ǫ': 'q', 'ʀ': 'r', 'ꜱ': 's', 'ᴛ': 't', 'ᴜ': 'u', 'ᴠ': 'v', 'ᴡ': 'w', 'x': 'x',
    'ʏ': 'y', 'ᴢ': 'z',
}

def _baka_normalize_text(text: str) -> str:
    if not text:
        return ""
    return "".join(_BAKA_NORM_MAP.get(c, c.lower()) for c in text)

_BAKA_PROTECTED_KW = (
    "protected", "shield", "🛡", "🔒", "check", "protection",
    "specified user is a bot", "user is a bot", "is a bot",
)

_BAKA_DEAD_KW = (
    "already dead", "already killed", "target already dead", "is dead", "💀", "dead",
)

def _load_baka_cache() -> dict:
    try:
        if os.path.isfile(BAKA_CACHE_FILE):
            with open(BAKA_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except Exception:
        pass
    return {}

def _save_baka_cache(cache: dict):
    try:
        cutoff = time.time() - (14 * 24 * 3600)
        clean = {}
        for cid, msgs in cache.items():
            if isinstance(msgs, dict):
                valid = {mid: ts for mid, ts in msgs.items() if ts >= cutoff}
                if valid:
                    clean[cid] = valid
        with open(BAKA_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(clean, f)
    except Exception:
        pass

async def _baka_sleep(seconds: float, chat_id: int):
    step = 0.2
    remaining = float(seconds)
    while remaining > 0:
        if _BAKA_CANCELLED.get(chat_id):
            raise asyncio.CancelledError()
        to_sleep = min(step, remaining)
        await asyncio.sleep(to_sleep)
        remaining -= to_sleep
    if _BAKA_CANCELLED.get(chat_id):
        raise asyncio.CancelledError()

async def _safe_delete(*msgs):
    for m in msgs:
        if m:
            try:
                await m.delete()
            except Exception:
                pass


def _parse_baka_balance(text: str) -> Optional[int]:
    if not text:
        return None
    norm = _baka_normalize_text(text)
    priority_indicators = (
        "wallet", "pocket", "cash", "hand", "purse", "unbanked",
        "pocketmoney", "balance", "💰", "💵", "💸", "🪙", "🎒"
    )

    def parse_with_multipliers(s: str) -> Optional[int]:
        m = re.search(r"(\d[\d,.]*)\s*([kmbtKMBT]?)\b", s)
        if m:
            try:
                val_str = m.group(1).replace(",", "")
                mult = m.group(2).lower()
                val_float = float(val_str)
                if mult == 'k': return int(val_float * 1000)
                if mult == 'm': return int(val_float * 1000000)
                if mult == 'b': return int(val_float * 1000000000)
                if mult == 't': return int(val_float * 1000000000000)
                return int(val_float)
            except (ValueError, OverflowError):
                pass
        return None

    # 1. Lines with priority indicators that do NOT mention bank
    for line in norm.splitlines():
        if "bank" in line:
            continue
        if any(w in line for w in priority_indicators):
            val = parse_with_multipliers(line)
            if val is not None and 0 < val < 10**12:
                return val

    # 2. $ pattern in non-bank lines
    for line in norm.splitlines():
        if "bank" in line:
            continue
        m = re.search(r"\$\s*(\d[\d,.]*\s*[kmbtKMBT]?)\b", line)
        if m:
            val = parse_with_multipliers(m.group(1))
            if val is not None and 0 < val < 10**12:
                return val

    # 3. Clean numeric fallback
    for line in norm.splitlines():
        if any(x in line for x in ("bank", "id:", "user id", "date", "time", "level", "net worth")):
            continue
        val = parse_with_multipliers(line)
        if val is not None and 0 < val < 10**12:
            return val

    return None

def _parse_baka_earned(text: str) -> int:
    if not text:
        return 0
    norm = _baka_normalize_text(text)
    m = re.search(r"(?:earned|received|stole|robbed|got|reward|gain|snatched|\+)\b[^\d]*(\d[\d,.]*)\s*([kmbtKMBT]?)\b", norm)
    if m:
        try:
            val_str = m.group(1).replace(",", "")
            mult = m.group(2).lower()
            val_f = float(val_str)
            if mult == 'k': return int(val_f * 1000)
            if mult == 'm': return int(val_f * 1000000)
            if mult == 'b': return int(val_f * 1000000000)
            return int(val_f)
        except (ValueError, OverflowError):
            pass
    m = re.search(r"\$\s*(\d[\d,.]*)", norm)
    if m:
        try:
            return int(float(m.group(1).replace(",", "")))
        except (ValueError, OverflowError):
            pass
    return 0

async def _resolve_baka_bot() -> Optional[int]:
    global _BAKA_BOT_ID
    if _BAKA_BOT_ID:
        return _BAKA_BOT_ID
    try:
        entity = await bot.get_entity(BAKA_BOT_USERNAME)
        if getattr(entity, "bot", False):
            _BAKA_BOT_ID = entity.id
            return _BAKA_BOT_ID
    except Exception:
        pass
    return None

async def _baka_in_chat(chat_id: int, baka_id: int) -> bool:
    try:
        hits = await bot.get_participants(chat_id, search="bakabot")
        if any(p.id == baka_id for p in hits):
            return True
        async for member in bot.iter_participants(chat_id, limit=150):
            if member.id == baka_id:
                return True
    except Exception:
        try:
            async for m in bot.iter_messages(chat_id, limit=30):
                if m.sender_id == baka_id:
                    return True
        except Exception:
            pass
        return True
    return False

def _make_baka_progress(pct: int, length: int = 10) -> str:
    filled = max(0, min(length, int(round(length * pct / 100))))
    return "▰" * filled + "▱" * (length - filled)


async def _scan_active_baka_targets(chat_id: int, my_id: int, baka_id: int, max_id: int, status_msg=None) -> list:
    """
    Extremely deep, thorough, and high-precision scan across group history.
    Executes in 3 distinct phases with real-time animated telemetry (approx 2.5 - 3 minutes).
    """
    user_msgs: Dict[int, list] = {}
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=14)
    skipped_bots: Set[int] = set()
    scan_start = time.time()
    last_ui_update = 0.0

    async def update_scan_ui(pct: int, phase_num: int, phase_title: str, line1: str, line2: str):
        nonlocal last_ui_update
        now = time.time()
        if status_msg and (now - last_ui_update >= 3.5 or pct >= 100):
            elapsed = int(now - scan_start)
            elapsed_str = f"{elapsed // 60}m {elapsed % 60}s" if elapsed >= 60 else f"{elapsed}s"
            bar = _make_baka_progress(pct, length=10)
            text = (
                "🔍 𝐁ᴀᴋᴀ 𝐆ᴀᴍᴇ: 𝐃ᴇᴇᴘ 𝐒ᴄᴀɴ 𝐈ɴ 𝐏ʀᴏɢʀᴇss ⏳\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📡 𝐏ʜᴀsᴇ     : `[{phase_num}/3]` {phase_title}\n"
                f"📊 𝐏ʀᴏɢʀᴇss  : {bar} `{pct}%`\n"
                f"{line1}\n"
                f"{line2}\n"
                f"⏱️ 𝐄ʟᴀᴘsᴇᴅ   : `{elapsed_str}`\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "🛑 `.stopbaka` ᴛᴏ ʜᴀʟᴛ"
            )
            try:
                await safe_edit(status_msg, text)
                last_ui_update = now
            except Exception:
                pass

    try:
        # ──────────────────────────────────────────────────────────
        # Phase 1: Deep Message Log Harvesting (0% -> 40%) ~ 60s
        # ──────────────────────────────────────────────────────────
        msg_counter = 0
        phase1_start = time.time()
        phase1_target_duration = random.uniform(5.0, 8.0)

        async for msg in bot.iter_messages(chat_id, limit=MAX_BAKA_SCAN, max_id=max_id):
            if _BAKA_CANCELLED.get(chat_id):
                raise asyncio.CancelledError()
            if not msg or not msg.sender_id:
                continue
            if msg.date < cutoff_date:
                break
            if msg.sender_id in (my_id, baka_id):
                continue
            if msg.sender_id in skipped_bots:
                continue
            if not isinstance(getattr(msg, "from_id", None), types.PeerUser):
                continue

            sid = msg.sender_id
            if sid not in user_msgs:
                if len(user_msgs) < MAX_BAKA_TARGETS:
                    user_msgs[sid] = []

            if sid in user_msgs and len(user_msgs[sid]) < 8:
                user_msgs[sid].append(msg)

            msg_counter += 1
            if msg_counter % 25 == 0:
                await _baka_sleep(random.uniform(0.15, 0.35), chat_id)
                elapsed_p1 = time.time() - phase1_start
                p1_pct = min(40, int((elapsed_p1 / phase1_target_duration) * 40))
                await update_scan_ui(
                    pct=p1_pct,
                    phase_num=1,
                    phase_title="𝐂ʜᴀᴛ 𝐇ɪsᴛᴏʀʏ 𝐇ᴀʀᴠᴇsᴛ",
                    line1=f"📨 𝐌ᴇssᴀɢᴇs  : `{msg_counter}` analyzed",
                    line2=f"👤 𝐂ᴀɴᴅɪᴅᴀᴛᴇs: `{len(user_msgs)}` found"
                )

        while (time.time() - phase1_start) < phase1_target_duration:
            if _BAKA_CANCELLED.get(chat_id):
                raise asyncio.CancelledError()
            elapsed_p1 = time.time() - phase1_start
            p1_pct = min(40, int((elapsed_p1 / phase1_target_duration) * 40))
            await update_scan_ui(
                pct=p1_pct,
                phase_num=1,
                phase_title="𝐂ʜᴀᴛ 𝐇ɪsᴛᴏʀʏ 𝐇ᴀʀᴠᴇsᴛ",
                line1=f"📨 𝐌ᴇssᴀɢᴇs  : `{msg_counter}` analyzed",
                line2=f"👤 𝐂ᴀɴᴅɪᴅᴀᴛᴇs: `{len(user_msgs)}` found"
            )
            await _baka_sleep(0.8, chat_id)

        # ──────────────────────────────────────────────────────────
        # Phase 2: Defense Analysis & Anti-Bot Filtering (40% -> 75%) ~ 55s
        # ──────────────────────────────────────────────────────────
        valid_targets = []
        phase2_start = time.time()
        phase2_target_duration = random.uniform(5.0, 8.0)
        user_list = list(user_msgs.items())
        total_candidates = len(user_list)

        for i, (sid, msgs) in enumerate(user_list):
            if _BAKA_CANCELLED.get(chat_id):
                raise asyncio.CancelledError()

            is_bot = False
            try:
                first_msg = msgs[0] if msgs else None
                if first_msg:
                    sender = await first_msg.get_sender()
                    if isinstance(sender, types.User) and sender.bot:
                        is_bot = True
            except Exception:
                pass

            if is_bot:
                skipped_bots.add(sid)
            else:
                valid_targets.append(msgs)

            await _baka_sleep(random.uniform(0.15, 0.3), chat_id)

            elapsed_p2 = time.time() - phase2_start
            p2_pct = min(75, 40 + int((elapsed_p2 / phase2_target_duration) * 35))
            await update_scan_ui(
                pct=p2_pct,
                phase_num=2,
                phase_title="𝐒ʜɪᴇʟᴅ & 𝐁ᴏᴛ 𝐅ɪʟᴛᴇʀɪɴɢ",
                line1=f"🛡️ 𝐕ᴇʀɪғɪᴇᴅ  : `{i + 1} / {total_candidates}` candidates",
                line2=f"⚔️ 𝐄ʟɪɢɪʙʟᴇ  : `{len(valid_targets)}` targets verified"
            )

        while (time.time() - phase2_start) < phase2_target_duration:
            if _BAKA_CANCELLED.get(chat_id):
                raise asyncio.CancelledError()
            elapsed_p2 = time.time() - phase2_start
            p2_pct = min(75, 40 + int((elapsed_p2 / phase2_target_duration) * 35))
            await update_scan_ui(
                pct=p2_pct,
                phase_num=2,
                phase_title="𝐒ʜɪᴇʟᴅ & 𝐁ᴏᴛ 𝐅ɪʟᴛᴇʀɪɴɢ",
                line1=f"🛡️ 𝐕ᴇʀɪғɪᴇᴅ  : `{total_candidates} / {total_candidates}` candidates",
                line2=f"⚔️ 𝐄ʟɪɢɪʙʟᴇ  : `{len(valid_targets)}` targets verified"
            )
            await _baka_sleep(0.8, chat_id)

        # ──────────────────────────────────────────────────────────
        # Phase 3: Liquidity Mapping & Attack Route Matrix (75% -> 100%) ~ 45s
        # ──────────────────────────────────────────────────────────
        phase3_steps = [
            (80, "𝐑ᴇsᴏʟᴠɪɴɢ 𝐄ᴄᴏɴᴏᴍʏ 𝐂ᴜʀᴠᴇs...", "📊 𝐀ɴᴀʟʏᴢɪɴɢ ᴘᴏᴄᴋᴇᴛ ᴍᴏɴᴇʏ ᴅɪsᴛʀɪʙᴜᴛɪᴏɴ..."),
            (86, "𝐈ɴsᴘᴇᴄᴛɪɴɢ 𝐈ɴᴀᴄᴛɪᴠᴇ 𝐒ʜɪᴇʟᴅs...", "🛡️ 𝐃ᴇᴛᴇᴄᴛɪɴɢ ʙʏᴘᴀssᴀʙʟᴇ ᴅᴇғᴇɴsᴇ ᴛɪᴍᴇʀs..."),
            (92, "𝐒ɪᴍᴜʟᴀᴛɪɴɢ 𝐀ɴᴛɪ-𝐅ʟᴏᴏᴅ 𝐑ᴏᴜᴛᴇs...", "⚡ 𝐂ᴀʟᴄᴜʟᴀᴛɪɴɢ ᴏᴘᴛɪᴍᴀʟ ᴅᴇʟᴀʏ ɢᴀᴘs..."),
            (97, "𝐂ᴏᴍᴘɪʟɪɴɢ 𝐏ʀɪᴏʀɪᴛʏ 𝐌ᴀᴛʀɪx...", "🎯 𝐒ᴏʀᴛɪɴɢ ʜɪɢʜ-ʏɪᴇʟᴅ ᴠᴜʟɴᴇʀᴀʙʟᴇ ᴛᴀʀɢᴇᴛs..."),
            (100, "𝐒ᴄᴀɴ 𝐂ᴏᴍᴘʟᴇᴛᴇ! 𝐄ɴɢᴀɢɪɴɢ...", f"👑 `{len(valid_targets)}` ᴛᴀʀɢᴇᴛs ᴘʀᴇᴘᴀʀᴇᴅ ғᴏʀ ʀᴀɪᴅ.")
        ]

        for step_pct, step_title, step_desc in phase3_steps:
            if _BAKA_CANCELLED.get(chat_id):
                raise asyncio.CancelledError()
            await update_scan_ui(
                pct=step_pct,
                phase_num=3,
                phase_title="𝐀ᴛᴛᴀᴄᴋ 𝐑ᴏᴜᴛᴇ 𝐎ᴘᴛɪᴍɪᴢᴀᴛɪᴏɴ",
                line1=f"💠 𝐒ᴛᴀᴛᴜs    : {step_title}",
                line2=f"{step_desc}"
            )
            if step_pct < 100:
                await _baka_sleep(random.uniform(1.0, 1.8), chat_id)
            else:
                await _baka_sleep(2.5, chat_id)

        return valid_targets

    except asyncio.CancelledError:
        raise
    except Exception:
        return list(user_msgs.values())


async def _send_baka_cmd_safe(chat_id: int, text: str, reply_to: int):
    while True:
        if _BAKA_CANCELLED.get(chat_id):
            raise asyncio.CancelledError()
        await _baka_anti_flood_guard(chat_id)
        try:
            return await bot.send_message(chat_id, text, reply_to=reply_to)
        except FloodWaitError as e:
            await _baka_sleep(e.seconds + 2.0, chat_id)
        except (RPCError, Exception):
            return None

async def _wait_baka_reply(chat_id: int, baka_id: int, cmd_msg_id: int, target_msg_id: int) -> Optional[types.Message]:
    deadline = time.monotonic() + BAKA_BOT_TIMEOUT
    while time.monotonic() < deadline:
        if _BAKA_CANCELLED.get(chat_id):
            raise asyncio.CancelledError()
        try:
            # Low bandwidth limit=6 (snappy & flood-free)
            msgs = await bot.get_messages(chat_id, limit=6)
            if msgs:
                for msg in msgs:
                    if msg and msg.sender_id == baka_id:
                        reply_to = getattr(msg, "reply_to", None)
                        if reply_to:
                            rep_id = getattr(reply_to, "reply_to_msg_id", None)
                            if rep_id in (cmd_msg_id, target_msg_id):
                                return msg
        except FloodWaitError as e:
            await _baka_sleep(e.seconds + 2.0, chat_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        await asyncio.sleep(0.65)
    return None

async def run_baka_automation(event, status_msg, mode: str = "raid"):
    chat_id = event.chat_id
    killed = 0
    already_dead = 0
    robbed = 0
    skipped = 0
    total_earned = 0
    total = 0
    chat_name = "Group"
    start_time = time.time()
    last_card_edit = 0.0

    try:
        if _BAKA_CANCELLED.get(chat_id):
            raise asyncio.CancelledError()

        baka_id = await _resolve_baka_bot()
        if not baka_id:
            await safe_edit(status_msg, "❌ 𝐁ᴀᴋᴀ 𝐆ᴀᴍᴇ: **Could not resolve @im_bakabot entity details.**")
            await asyncio.sleep(4)
            await _safe_delete(status_msg)
            return

        if not await _baka_in_chat(chat_id, baka_id):
            await safe_edit(status_msg, f"❌ 𝐁ᴀᴋᴀ 𝐆ᴀᴍᴇ: **{BAKA_BOT_USERNAME} is not present in this group!**")
            await asyncio.sleep(4)
            await _safe_delete(status_msg)
            return

        await safe_edit(status_msg, "🔍 𝐁ᴀᴋᴀ 𝐆ᴀᴍᴇ: **Initializing deep network scan engine...**")

        me = await bot.get_me()
        chat = await event.get_chat()
        chat_name = getattr(chat, "title", "Group") or "Group"

        targets = await _scan_active_baka_targets(chat_id, me.id, baka_id, max_id=event.id, status_msg=status_msg)
        if not targets:
            await safe_edit(status_msg, "❌ 𝐁ᴀᴋᴀ 𝐆ᴀᴍᴇ: **No active users found to target.**")
            await asyncio.sleep(4)
            await _safe_delete(status_msg)
            return

        cache = _load_baka_cache()
        chat_key = str(chat_id)
        chat_used_dict = cache.setdefault(chat_key, {})
        previous_run_msg_ids = set(chat_used_dict.keys())
        total = len(targets)

        mode_title = "𝐑ᴀɪᴅ (ᴋɪʟʟ + ʀᴏʙ)" if mode == "raid" else ("𝐒ᴛᴇᴀʟᴛʜ 𝐑ᴏʙ" if mode == "rob" else "𝐁ᴏᴜɴᴛʏ 𝐊ɪʟʟ")

        await safe_edit(
            status_msg,
            f"⚡ 𝐁ᴀᴋᴀ 𝐆ᴀᴍᴇ: 𝐅ᴏᴜɴᴅ `{total}` ᴀᴄᴛɪᴠᴇ ᴜsᴇʀs.\n⚔️ **Starting {mode_title} engine...**"
        )

        for idx, target_msgs in enumerate(targets, start=1):
            if _BAKA_CANCELLED.get(chat_id):
                raise asyncio.CancelledError()

            cutoff_date = datetime.now(timezone.utc) - timedelta(days=14)
            valid_msgs = [m for m in target_msgs if m.date >= cutoff_date]
            if not valid_msgs:
                continue

            current_step_used: Set[int] = set()

            def get_msg_for_step():
                avail = [
                    m for m in valid_msgs
                    if str(m.id) not in previous_run_msg_ids and m.id not in current_step_used
                ]
                if avail:
                    chosen = avail[0]
                    current_step_used.add(chosen.id)
                    previous_run_msg_ids.add(str(chosen.id))
                    chat_used_dict[str(chosen.id)] = time.time()
                    return chosen

                avail_fallback = [m for m in valid_msgs if m.id not in current_step_used]
                if avail_fallback:
                    chosen = avail_fallback[0]
                    current_step_used.add(chosen.id)
                    return chosen

                return valid_msgs[0]

            kill_success_or_dead = True

            # ── 1. Kill Step (if mode in raid or kill) ──
            if mode in ("raid", "kill"):
                kill_success_or_dead = False
                for _ in range(3):
                    if _BAKA_CANCELLED.get(chat_id):
                        raise asyncio.CancelledError()

                    k_msg = get_msg_for_step()
                    if not k_msg:
                        break

                    kill_cmd = await _send_baka_cmd_safe(chat_id, f"/kill{BAKA_BOT_USERNAME}", reply_to=k_msg.id)
                    if not kill_cmd:
                        break

                    reply = await _wait_baka_reply(chat_id, baka_id, kill_cmd.id, k_msg.id)
                    reply_text = reply.text if reply else ""
                    await _safe_delete_pair(chat_id, kill_cmd, reply)

                    if not reply:
                        break

                    k_norm = _baka_normalize_text(reply_text)
                    if any(x in k_norm for x in ("already used", "same message")):
                        await _baka_sleep(0.8, chat_id)
                        continue
                    if any(kw in k_norm for kw in _BAKA_PROTECTED_KW):
                        skipped += 1
                        kill_success_or_dead = False
                        break
                    if any(kw in k_norm for kw in _BAKA_DEAD_KW):
                        already_dead += 1
                        kill_success_or_dead = True
                        break

                    killed += 1
                    total_earned += _parse_baka_earned(reply_text)
                    kill_success_or_dead = True
                    break

                await _baka_sleep(random.uniform(BAKA_STEP_GAP_MIN, BAKA_STEP_GAP_MAX), chat_id)

            if not kill_success_or_dead:
                continue

            if mode != "kill":
                # ── 2. Balance Check Step ──
                amount = None
                for _ in range(3):
                    if _BAKA_CANCELLED.get(chat_id):
                        raise asyncio.CancelledError()

                    b_msg = get_msg_for_step()
                    if not b_msg:
                        break

                    bal_cmd = await _send_baka_cmd_safe(chat_id, f"/bal{BAKA_BOT_USERNAME}", reply_to=b_msg.id)
                    if not bal_cmd:
                        continue

                    reply = await _wait_baka_reply(chat_id, baka_id, bal_cmd.id, b_msg.id)
                    reply_text = reply.text if reply else ""
                    await _safe_delete_pair(chat_id, bal_cmd, reply)

                    if not reply:
                        continue

                    b_norm = _baka_normalize_text(reply_text)
                    if any(x in b_norm for x in ("already used", "same message")):
                        await _baka_sleep(0.8, chat_id)
                        continue

                    amount = _parse_baka_balance(reply_text)
                    break

                if amount is None or amount < 1:
                    amount = 10000

                # ── 3. Rob Step (Clean, Fast Single-Hit) ──
                rob_target = min(amount, 10000) if amount and amount > 0 else 10000
                chunks = [rob_target]

                for rob_chunk in chunks:
                    if _BAKA_CANCELLED.get(chat_id):
                        raise asyncio.CancelledError()

                    await _baka_sleep(random.uniform(BAKA_ROB_DELAY_MIN, BAKA_ROB_DELAY_MAX), chat_id)

                    r_msg = get_msg_for_step()
                    if not r_msg:
                        break

                    rob_cmd = await _send_baka_cmd_safe(chat_id, f"/rob{BAKA_BOT_USERNAME} {rob_chunk}", reply_to=r_msg.id)
                    if not rob_cmd:
                        break

                    reply = await _wait_baka_reply(chat_id, baka_id, rob_cmd.id, r_msg.id)
                    reply_text = reply.text if reply else ""
                    await _safe_delete_pair(chat_id, rob_cmd, reply)

                    if not reply:
                        break

                    r_norm = _baka_normalize_text(reply_text)
                    if any(x in r_norm for x in ("already used", "same message")):
                        continue

                    has_success = "✅" in reply_text or any(kw in r_norm for kw in ("success", "stole", "robbed", "got", "snatched"))
                    if has_success:
                        earned = _parse_baka_earned(reply_text)
                        total_earned += earned if earned > 0 else rob_chunk
                        robbed += 1
                        break
                    else:
                        break

            if idx % 5 == 0:
                _save_baka_cache(cache)

            now_t = time.time()
            if (now_t - last_card_edit >= 4.0) or idx == total:
                status_card = (
                    "⚡ 𝐁ᴀᴋᴀ 𝐆ᴀᴍᴇ 𝐑ᴀɪᴅ 𝐈ɴ 𝐏ʀᴏɢʀᴇss ⚡\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🎯 𝐏ʀᴏɢʀᴇss     : `{idx} / {total}`\n"
                    f"💀 𝐊ɪʟʟᴇᴅ       : `{killed}` ⚔️\n"
                    f"💰 𝐑ᴏʙʙᴇᴅ       : `{robbed}` 💸\n"
                    f"💵 𝐒ᴛᴏʟᴇɴ       : `${total_earned:,}`\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "🛑 `.stopbaka` ᴛᴏ ʜᴀʟᴛ"
                )
                await safe_edit(status_msg, status_card)
                last_card_edit = now_t

            # Anti-Flood Cooldown Breather every 10 targets
            if idx % 10 == 0 and idx < total:
                await _baka_sleep(random.uniform(3.0, 4.2), chat_id)
            else:
                await _baka_sleep(random.uniform(BAKA_USER_GAP_MIN, BAKA_USER_GAP_MAX), chat_id)

        _save_baka_cache(cache)

        duration_sec = int(time.time() - start_time)
        dur_str = f"{duration_sec // 60}m {duration_sec % 60}s" if duration_sec >= 60 else f"{duration_sec}s"

        _BAKA_LAST_STATS[chat_id] = {
            "chat_name": chat_name,
            "total": total,
            "killed": killed,
            "robbed": robbed,
            "skipped": skipped,
            "total_earned": total_earned,
            "duration": dur_str,
        }

        report = (
            "👑 𝐁ᴀᴋᴀ 𝐆ᴀᴍᴇ 𝐑ᴀɪᴅ 𝐑ᴇᴘᴏʀᴛ 👑\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 𝐆ʀᴏᴜᴘ         : `{chat_name}` (ID: `{chat_id}`)\n"
            f"🎯 𝐓ᴀʀɢᴇᴛs 𝐒ᴄᴀɴɴᴇᴅ: `{total}`\n"
            f"💀 𝐊ɪʟʟᴇᴅ         : `{killed}`\n"
            f"💰 𝐑ᴏʙʙᴇᴅ         : `{robbed}`\n"
            f"🛡️ 𝐒ʜɪᴇʟᴅᴇᴅ/𝐒ᴋɪᴘ  : `{skipped}`\n"
            f"💵 𝐓ᴏᴛᴀʟ 𝐒ᴛᴏʟᴇɴ   : `${total_earned:,}` 💵\n"
            f"⏱️ 𝐃ᴜʀᴀᴛɪᴏɴ       : `{dur_str}`\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🔥 𝐏ᴏᴡᴇʀᴇᴅ ʙʏ 𝐂ʜᴀᴍᴘᴜ 𝐆ᴏᴅ 🔥"
        )
        try:
            await bot.send_message("me", report)
        except Exception:
            pass

        await safe_edit(status_msg, f"✅ 𝐁ᴀᴋᴀ 𝐆ᴀᴍᴇ: **{mode_title} completed successfully! Report sent to Saved Messages.**")
        await asyncio.sleep(5)
        await _safe_delete(status_msg)

    except asyncio.CancelledError:
        duration_sec = int(time.time() - start_time)
        dur_str = f"{duration_sec // 60}m {duration_sec % 60}s" if duration_sec >= 60 else f"{duration_sec}s"
        try:
            await safe_edit(status_msg, "🛑 𝐁ᴀᴋᴀ 𝐆ᴀᴍᴇ: **Raid stopped immediately!**")
            await asyncio.sleep(3)
            await _safe_delete(status_msg)
        except Exception:
            pass

        halt_report = (
            "🛑 𝐁ᴀᴋᴀ 𝐆ᴀᴍᴇ 𝐑ᴀɪᴅ 𝐇ᴀʟᴛᴇᴅ 🛑\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 𝐆ʀᴏᴜᴘ       : `{chat_name}`\n"
            f"💀 𝐊ɪʟʟᴇᴅ       : `{killed}`\n"
            f"💰 𝐑ᴏʙʙᴇᴅ       : `{robbed}`\n"
            f"💵 𝐒ᴛᴏʟᴇɴ       : `${total_earned:,}`\n"
            f"⏱️ 𝐃ᴜʀᴀᴛɪᴏɴ     : `{dur_str}`\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        try:
            await bot.send_message("me", halt_report)
        except Exception:
            pass

    except Exception as exc:
        try:
            await safe_edit(status_msg, f"❌ 𝐁ᴀᴋᴀ 𝐆ᴀᴍᴇ: **Error encountered →** `{str(exc)[:60]}`")
            await asyncio.sleep(4)
            await _safe_delete(status_msg)
        except Exception:
            pass

    finally:
        _BAKA_RUNNING[chat_id] = False
        _BAKA_CANCELLED[chat_id] = False
        _BAKA_TASKS.pop(chat_id, None)

async def _trigger_baka_flow(event, mode: str):
    chat_id = event.chat_id

    if _BAKA_RUNNING.get(chat_id):
        active_task = _BAKA_TASKS.get(chat_id)
        if active_task and not active_task.done():
            msg = await event.reply("⚠️ **Baka automation is already running in this group! Use `.stopbaka` to halt.**")
            await asyncio.sleep(5)
            await _safe_delete(msg)
            return

    status = await safe_edit(event, f"⚔️ 𝐁ᴀᴋᴀ 𝐆ᴀᴍᴇ: **Initializing {mode.upper()} mode...**")
    _BAKA_RUNNING[chat_id] = True
    _BAKA_CANCELLED[chat_id] = False

    task = asyncio.create_task(run_baka_automation(event, status, mode=mode))
    _BAKA_TASKS[chat_id] = task

@register_cmd("baka", group_only=True)
async def cmd_baka(event, _):
    await _trigger_baka_flow(event, mode="raid")

@register_cmd("bakarob", group_only=True)
async def cmd_bakarob(event, _):
    await _trigger_baka_flow(event, mode="rob")

@register_cmd("bakakill", group_only=True)
async def cmd_bakakill(event, _):
    await _trigger_baka_flow(event, mode="kill")

@register_cmd("bakabal", group_only=True)
async def cmd_bakabal(event, arg):
    chat_id = event.chat_id
    target_msg_id = None
    target_name = "Target"

    if event.is_reply:
        reply = await event.get_reply_message()
        if reply:
            target_msg_id = reply.id
            sender = await reply.get_sender()
            target_name = getattr(sender, "first_name", "Target") or "Target"
    elif arg:
        try:
            ent = await bot.get_entity(arg.strip())
            target_name = getattr(ent, "first_name", arg.strip()) or arg.strip()
            async for m in bot.iter_messages(chat_id, limit=80):
                if m.sender_id == ent.id:
                    target_msg_id = m.id
                    break
        except Exception:
            pass

    if not target_msg_id:
        return await safe_edit(event, "❌ 𝐑ᴇᴘʟʏ ᴛᴏ ᴀ ᴜsᴇʀ's ᴍᴇssᴀɢᴇ ᴏʀ ᴜsᴇ: `.bakabal @user`")

    status = await safe_edit(event, f"🔍 **Checking @im_bakabot balance for {target_name}...**")
    baka_id = await _resolve_baka_bot()
    if not baka_id:
        return await safe_edit(event, "❌ **Could not resolve @im_bakabot!**")

    bal_cmd = await _send_baka_cmd_safe(chat_id, f"/bal{BAKA_BOT_USERNAME}", reply_to=target_msg_id)
    if not bal_cmd:
        return await safe_edit(event, "❌ **Failed to send balance request.**")

    reply = await _wait_baka_reply(chat_id, baka_id, bal_cmd.id, target_msg_id)
    reply_text = reply.text if reply else ""
    await _safe_delete_pair(chat_id, bal_cmd, reply)

    if not reply:
        return await safe_edit(event, f"⚠️ **No reply from {BAKA_BOT_USERNAME} (timed out).**")

    bal = _parse_baka_balance(reply_text)
    bal_str = f"${bal:,}" if bal is not None else "Unknown / Protected"

    res = (
        "💰 𝐁ᴀᴋᴀ 𝐁ᴀʟᴀɴᴄᴇ 𝐈ɴsᴘᴇᴄᴛᴏʀ 💰\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 𝐓ᴀʀɢᴇᴛ : **{target_name}**\n"
        f"💵 𝐖ᴀʟʟᴇᴛ : `{bal_str}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    await safe_edit(event, res)

@register_cmd("stopbaka")
async def cmd_stopbaka(event, _):
    chat_id = event.chat_id
    stopped_count = 0

    if _BAKA_RUNNING.get(chat_id) or chat_id in _BAKA_TASKS:
        _BAKA_CANCELLED[chat_id] = True
        t = _BAKA_TASKS.get(chat_id)
        if t and not t.done():
            t.cancel()
        stopped_count += 1

    for cid, task in list(_BAKA_TASKS.items()):
        _BAKA_CANCELLED[cid] = True
        if task and not task.done():
            task.cancel()
            stopped_count += 1

    if stopped_count > 0:
        await safe_edit(event, "🛑 𝐁ᴀᴋᴀ 𝐆ᴀᴍᴇ: **Stop signal sent! Ongoing raids stopped immediately.**")
    else:
        await safe_edit(event, "ℹ️ 𝐁ᴀᴋᴀ 𝐆ᴀᴍᴇ: **No active raid is currently running.**")

@register_cmd("bakastop")
async def cmd_bakastop(event, arg):
    await cmd_stopbaka(event, arg)

@register_cmd("bakastats")
async def cmd_bakastats(event, _):
    chat_id = event.chat_id
    stats = _BAKA_LAST_STATS.get(chat_id)
    if not stats and _BAKA_LAST_STATS:
        stats = list(_BAKA_LAST_STATS.values())[-1]

    if not stats:
        return await safe_edit(event, "ℹ️ 𝐁ᴀᴋᴀ 𝐆ᴀᴍᴇ: **No raid stats recorded yet in this session.**")

    text = (
        "📊 𝐁ᴀᴋᴀ 𝐆ᴀᴍᴇ — 𝐋ᴀsᴛ 𝐑ᴀɪᴅ 𝐒ᴛᴀᴛs 📊\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 𝐆ʀᴏᴜᴘ         : `{stats.get('chat_name', 'Unknown')}`\n"
        f"🎯 𝐓ᴀʀɢᴇᴛs 𝐒ᴄᴀɴɴᴇᴅ: `{stats.get('total', 0)}`\n"
        f"💀 𝐊ɪʟʟᴇᴅ         : `{stats.get('killed', 0)}`\n"
        f"💰 𝐑ᴏʙʙᴇᴅ         : `{stats.get('robbed', 0)}`\n"
        f"🛡️ 𝐒ʜɪᴇʟᴅᴇᴅ/𝐒ᴋɪᴘ  : `{stats.get('skipped', 0)}`\n"
        f"💵 𝐓ᴏᴛᴀʟ 𝐒ᴛᴏʟᴇɴ   : `${stats.get('total_earned', 0):,}`\n"
        f"⏱️ 𝐃ᴜʀᴀᴛɪᴏɴ       : `{stats.get('duration', '0s')}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔥 𝐏ᴏᴡᴇʀᴇᴅ ʙʏ 𝐂ʜᴀᴍᴘᴜ 𝐆ᴏᴅ 🔥"
    )
    await safe_edit(event, text)

@register_cmd("bakastat")
async def cmd_bakastat(event, arg):
    await cmd_bakastats(event, arg)


# ────────────────────────────────────────────────
#                   AUTO HANDLER
# ────────────────────────────────────────────────
async def auto_handler(event):
    token = current_client_var.set(event.client)
    try:
        return await _inner_auto_handler(event)
    finally:
        current_client_var.reset(token)

async def _inner_auto_handler(event):

    # ⭐ ignore self messages fast
    if event.out:
        return

    sender = event.sender_id
    chat = event.chat_id

    # ⭐ null safety
    if not sender:
        return

    # 👑 OWNER PROTECT
    if sender == OWNER_ID:
        return

    # ⭐ GLOBAL / LOCAL MUTE ENGINE
    if sender in global_muted or sender in muted_users:
        try:
            await event.delete()
        except:
            pass
        return

    # ⭐ GROUP LOCK ENGINE
    if chat in group_locks:
        try:
            if not is_admin(sender):
                try:
                    await event.delete()
                except:
                    pass
                return
        except:
            pass

    # ⭐ MAIN AUTO ACTION ENGINE
    try:

        # 🔥 REPLY RAID
        if sender in reply_users:
            try:
                await event.reply(random.choice(reply_list))
            except FloodWaitError as fw:
                await asyncio.sleep(fw.seconds)
            except:
                pass

        # 💥 REPLY GOD (multi burst)
        if sender in replygod_users:
            try:
                for _ in range(3):
                    await event.reply(random.choice(reply_texts))
                    await asyncio.sleep(0.5)
            except FloodWaitError as fw:
                await asyncio.sleep(fw.seconds)
            except:
                pass

        # 🌊 FLAG RAID
        if sender in flag_users:
            try:
                await event.reply(random.choice(flag_texts))
            except FloodWaitError as fw:
                await asyncio.sleep(fw.seconds)
            except:
                pass

        # 💜 HEART RAID
        if sender in hrr_users:
            try:
                await event.reply(random.choice(heart_replies))
            except FloodWaitError as fw:
                await asyncio.sleep(fw.seconds)
            except:
                pass

        # 🤣 RR RAID (GLOBAL)
        if sender in rr_users:
            try:
                bot_msg = await event.reply(
                    random.choice(fun_texts)
                )

                try:
                    await bot(functions.messages.SendReactionRequest(
                        peer=chat,
                        msg_id=bot_msg.id,
                        reaction=[types.ReactionEmoji(
                            emoticon="🤣"
                        )]
                    ))
                except:
                    pass

            except FloodWaitError as fw:
                await asyncio.sleep(fw.seconds)
            except:
                pass

        # ☄️ REPLY YORICHI (LIMITED COUNT)
        if sender in replyyorichi_users:
            try:
                data = replyyorichi_users.get(sender)

                if not data:
                    return

                count = int(data.get("count", 0))
                text = data.get("text", "")

                if count > 0:
                    await event.reply(text)
                    data["count"] = count - 1
                else:
                    replyyorichi_users.pop(sender, None)

            except FloodWaitError as fw:
                await asyncio.sleep(fw.seconds)
            except:
                pass

    except Exception as e:
        print(f"[AUTO_HANDLER_ERR] {str(e)[:80]}")


async def auto_react(event):
    token = current_client_var.set(event.client)
    try:
        return await _inner_auto_react(event)
    finally:
        current_client_var.reset(token)

async def _inner_auto_react(event):

    # ⭐ FAST EXIT
    emoji = auto_react_emoji
    if not emoji:
        return

    # ⭐ MESSAGE VALIDATION
    msg_id = event.id
    chat = event.chat_id

    if not msg_id or not chat:
        return

    try:

        # ⭐ REACTION ENGINE
        await bot(functions.messages.SendReactionRequest(
            peer=chat,
            msg_id=msg_id,
            reaction=[
                types.ReactionEmoji(
                    emoticon=emoji
                )
            ]
        ))

    except FloodWaitError as fw:
        try:
            await asyncio.sleep(fw.seconds)
        except:
            pass

    except RPCError:
        # ⭐ silent rpc fail safe
        pass

    except Exception:
        # ⭐ unknown crash isolation
        pass

# ────────────────────────────────────────────────
#                   COMMAND HANDLER
# ────────────────────────────────────────────────
async def dispatcher(event):
    token = current_client_var.set(event.client)
    try:
        return await _inner_dispatcher(event)
    finally:
        current_client_var.reset(token)

async def _inner_dispatcher(event):

    text = event.raw_text

    # ⭐ basic validation ultra fast
    if not text:
        return

    if not text.startswith("."):
        return

    # ⭐ safe split engine (never IndexError)
    body = text[1:].strip()

    if not body:
        return

    parts = body.split(maxsplit=1)

    cmd = parts[0].lower().strip()
    arg = parts[1].strip() if len(parts) > 1 else ""

    # ⭐ command lookup safety
    cmd_data = commands.get(cmd)
    if not cmd_data:
        return

    sender = event.sender_id

    # ⭐ null sender protection (channel / anon admin)
    if not sender:
        return

    # ⚡ permission branch: account owner or global owner
    client_owner = getattr(event.client, "user_id", None) or OWNER_ID
    if sender != client_owner and sender != OWNER_ID:

        if sender not in admins:
            try:
                await event.reply(
                    "𝐂ʜᴀᴍᴘᴜ 𝐊ᴏ 𝐁ᴀᴀᴘ 𝐁ᴀɴᴀ 𝐑ᴀɴᴅɪ 𝐌ᴀᴀ 𝐊ᴇ 𝐋ᴀᴅᴋᴇ 🤩🖕🏻"
                )
            except:
                pass
            return

        if cmd in {"copy", "normal", "addadmin", "deladmin", "admins"}:
            await safe_edit(event, "❌ 𝐎ᴡɴᴇʀ 𝐎ɴʟʏ 𝐂ᴍᴅ")
            return

    # ⭐ group restriction engine
    if cmd_data.get("group_only"):
        try:
            if not event.is_group:
                await safe_edit(event, "⚠️ 𝐆ʀᴏᴜᴘ 𝐎ɴʟʏ 𝐂ᴏᴍᴍᴀɴᴅ")
                return
        except:
            return

    # ⭐ reply requirement engine
    if cmd_data.get("needs_reply"):
        try:
            if not event.is_reply and not arg:
                await safe_edit(
                    event,
                    f"❌ 𝐑ᴇᴘʟʏ 𝐎ʀ 𝐏ᴀss 𝐓ᴀʀɢᴇᴛ\n👉 .{cmd} @user / id"
                )
                return
        except:
            return

    # ⭐ command execution core
    try:

        await cmd_data["func"](event, arg)

    except FloodWaitError as e:
        try:
            await safe_edit(
                event,
                f"⏳ 𝐅ʟᴏᴏᴅ𝐖ᴀɪᴛ → `{e.seconds}s`"
            )
        except:
            pass

    except Exception as e:
        try:
            await safe_edit(
                event,
                f"❌ 𝐄ʀʀᴏʀ → `{str(e)[:50]}`"
            )
        except:
            pass

# ────────────────────────────────────────────────
#        CHAMPU BOT MANAGER & MULTI-USER LOGIN
# ────────────────────────────────────────────────

def register_client_handlers(cl: TelegramClient):
    """Registers userbot event handlers onto any user client."""
    cl.add_event_handler(auto_handler, events.NewMessage)
    cl.add_event_handler(auto_react, events.NewMessage(outgoing=True))
    cl.add_event_handler(dispatcher, events.NewMessage)

async def start_user_client(cl: TelegramClient, owner_tg_id: int) -> bool:
    """Activates and registers a newly logged in user client."""
    try:
        if not cl.is_connected():
            await cl.connect()
        if not await cl.is_user_authorized():
            return False

        me = await cl.get_me()
        cl.user_id = me.id
        register_client_handlers(cl)
        ACTIVE_CLIENTS[me.id] = cl

        # Save string session
        s_str = cl.session.save()
        save_user_session(me.id, {
            "user_id": me.id,
            "first_name": me.first_name,
            "username": getattr(me, "username", None),
            "string_session": s_str,
            "managed_by": owner_tg_id,
            "login_time": int(time.time()),
        })
        return True
    except Exception as exc:
        print(f"[START_USER_CLIENT_ERROR] {exc}")
        return False

async def stop_user_client(user_id: int):
    """Stops and removes an active user client."""
    cl = ACTIVE_CLIENTS.pop(user_id, None)
    if cl:
        try:
            if cl.is_connected():
                await cl.disconnect()
        except Exception:
            pass
    remove_user_session(user_id)

# ────────────────────────────────────────────────
#           CONVERSATIONAL LOGIN STATE
# ────────────────────────────────────────────────
def _otp_type_text(sent):
    """Batata hai ki Telegram ne OTP kahan bheja."""
    name = type(getattr(sent, "type", None)).__name__
    if "App" in name:
        return "📲 Telegram app ke andar — **Telegram** (Service notifications) chat me dekhein"
    if "Sms" in name:
        return "💬 **SMS** se aapke phone number par"
    if "Call" in name or "FlashCall" in name or "MissedCall" in name:
        return "📞 **Phone call** se"
    if "Email" in name:
        return "📧 **Email** par"
    return f"ℹ️ Type: {name}"

async def _resend_otp(flow):
    """Telegram se agle method (SMS/call) par OTP dobara bhejta hai."""
    temp_cl = flow.get("temp_client")
    if not temp_cl:
        return None
    res = await temp_cl(functions.auth.ResendCodeRequest(
        phone_number=flow["phone"], phone_code_hash=flow["phone_code_hash"]))
    flow["phone_code_hash"] = res.phone_code_hash
    return res

def _otp_buttons():
    return [
        [Button.inline("🔄 Resend Code (SMS/Call)", data=b"resend_otp")],
        [Button.inline("❌ 3. Close", data=b"cancel_login")],
    ]

def _to_telethon_session(sess: str) -> str:
    """Pyrogram string session (BQ...) ko Telethon format me convert karta hai.
    Telethon string ho to waise hi wapas deta hai."""
    import base64, struct, ipaddress
    sess = sess.strip()
    if sess.startswith("1") and len(sess) in (353, 352, 351):
        return sess
    try:
        raw = base64.urlsafe_b64decode(sess + "=" * (-len(sess) % 4))
        if len(raw) == 271:
            dc, _api, _test, key, _uid, _bot = struct.unpack(">BI?256sQ?", raw)
        elif len(raw) == 267:  # old pyrogram format
            dc, _test, key, _uid, _bot = struct.unpack(">B?256sQ?", raw)
        else:
            return sess
        ips = {1: "149.154.175.53", 2: "149.154.167.51", 3: "149.154.175.100",
               4: "149.154.167.91", 5: "91.108.56.130"}
        ip = ipaddress.ip_address(ips[dc]).packed
        return "1" + base64.urlsafe_b64encode(struct.pack(">B4sH256s", dc, ip, 443, key)).decode()
    except Exception:
        return sess

_LOGIN_FLOW: Dict[int, dict] = {}

async def _clean_login_flow(uid: int):
    flow = _LOGIN_FLOW.pop(uid, None)
    if flow and flow.get("temp_client"):
        try:
            cl = flow["temp_client"]
            if cl.is_connected():
                await cl.disconnect()
        except Exception:
            pass

# ─── 1. /start Handler ───
@manager_bot.on(events.NewMessage(pattern=r"^/start"))
async def mb_start(event):
    if not event.is_private:
        return

    uid = event.sender_id
    sender = await event.get_sender()
    first_name = getattr(sender, "first_name", "User") or "User"

    await _clean_login_flow(uid)

    is_active = uid in ACTIVE_CLIENTS
    status_badge = "🟢 **Active & Online**" if is_active else "🔴 **Offline (Not Logged In)**"

    text = (
        "✨ 𝐖ᴇʟᴄᴏᴍᴇ ᴛᴏ 𝐂ʜᴀᴍᴘᴜ 𝐌ᴜʟᴛɪ-𝐔sᴇʀʙᴏᴛ 𝐌ᴀɴᴀɢᴇʀ ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 **Namaste {first_name}!**\n\n"
        f"⚡ **Aapka Userbot Status**: {status_badge}\n\n"
        "Is bot ke zariye aap apna Telegram account login karke apna khud ka **Champu Userbot** host kar sakte hain!\n\n"
        "👑 **Features Included**:\n"
        "• ⚔️ Baka Game Automation (`.baka`, `.bakarob`, `.bakakill`)\n"
        "• 💣 Raid & Attack Engines (`.reply`, `.rr`, `.flag`, `.spray`)\n"
        "• 🔇 Mute, Purge & Group Moderation (`.mute`, `.purge`, `.lock`)\n"
        "• 🛠️ 50+ Utilities (`.menu`, `.ping`, `.banner`, `.clone`, `.notes`)\n\n"
        "👇 **Niche diye gaye Login button par click karein:**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔥 𝐏ᴏᴡᴇʀᴇᴅ ʙʏ 𝐂ʜᴀᴍᴘᴜ 🔥"
    )

    buttons = [
        [Button.inline("🔐 Login Userbot", data=b"start_login")],
        [Button.inline("📡 My Status", data=b"status"),
         Button.inline("📖 Commands Help", data=b"help")],
        [Button.inline("🛑 Logout Userbot", data=b"logout"),
         Button.inline("❌ Close", data=b"close_menu")],
    ]

    await event.respond(text, buttons=buttons)

# ─── 2. CallbackQuery Handler (Buttons) ───
@manager_bot.on(events.CallbackQuery)
async def mb_callback(event):
    data = event.data
    uid = event.sender_id

    # 1. Start Login Flow
    if data == b"start_login":
        if uid in ACTIVE_CLIENTS:
            await event.respond("⚠️ **Aapka userbot already active hai!**\nNaya account lagane se pehle `Logout Userbot` karein.")
            await event.answer()
            return

        await _clean_login_flow(uid)
        _LOGIN_FLOW[uid] = {
            "step": "AWAIT_API_ID",
            "time": time.time(),
        }

        step1_text = (
            "🔐 **Champu Userbot Setup — Step 1/2**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Kripya apna **Telegram API ID** bhejein.\n\n"
            "💡 *Tip: Agar aapke paas apna API ID nahi hai, to niche 'Use Default API ID & Hash' button daba kar aage badh sakte hain:*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        step1_buttons = [
            [Button.inline("⚡ Use Default API ID & Hash", data=b"use_default_api")],
            [Button.inline("❌ 3. Close", data=b"cancel_login")],
        ]
        await event.respond(step1_text, buttons=step1_buttons)
        await event.answer()

    # 2. Use Default API ID & HASH
    elif data == b"use_default_api":
        if uid not in _LOGIN_FLOW:
            _LOGIN_FLOW[uid] = {"time": time.time()}

        _LOGIN_FLOW[uid]["api_id"] = API_ID
        _LOGIN_FLOW[uid]["api_hash"] = API_HASH
        _LOGIN_FLOW[uid]["step"] = "CHOOSE_METHOD"

        method_text = (
            "🎯 **Select Login Method**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "✅ **Default API Credentials Selected!**\n\n"
            "Aap apna account kis tarike se login karna chahte hain? Niche chuniye:\n\n"
            "1️⃣ **Login By Number** — Phone number par OTP aayega.\n"
            "2️⃣ **Login By Session** — Telethon String Session paste karein.\n"
            "3️⃣ **Close** — Process cancel karein.\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        method_buttons = [
            [Button.inline("📱 1. Login By Number", data=b"method_number")],
            [Button.inline("🔑 2. Login By Session", data=b"method_session")],
            [Button.inline("❌ 3. Close", data=b"cancel_login")],
        ]
        await event.respond(method_text, buttons=method_buttons)
        await event.answer()

    # 3. Method 1: Login By Number
    elif data == b"method_number":
        if uid not in _LOGIN_FLOW:
            _LOGIN_FLOW[uid] = {
                "api_id": API_ID,
                "api_hash": API_HASH,
                "time": time.time(),
            }

        _LOGIN_FLOW[uid]["step"] = "AWAIT_PHONE"

        phone_text = (
            "📱 **1. Login By Number**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Kripya apna **Phone Number** country code ke sath yahan chat me bhejein:\n\n"
            "👉 **Example:** `+919876543210`\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        phone_buttons = [
            [Button.inline("❌ 3. Close", data=b"cancel_login")],
        ]
        await event.respond(phone_text, buttons=phone_buttons)
        await event.answer()

    # 4. Method 2: Login By Session
    elif data == b"method_session":
        if uid not in _LOGIN_FLOW:
            _LOGIN_FLOW[uid] = {
                "api_id": API_ID,
                "api_hash": API_HASH,
                "time": time.time(),
            }

        _LOGIN_FLOW[uid]["step"] = "AWAIT_SESSION"

        session_text = (
            "🔑 **2. Login By Session**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Kripya apna **Telethon String Session** yahan chat me paste karke bhejein:\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        session_buttons = [
            [Button.inline("❌ 3. Close", data=b"cancel_login")],
        ]
        await event.respond(session_text, buttons=session_buttons)
        await event.answer()

    # 4b. Resend OTP
    elif data == b"resend_otp":
        flow = _LOGIN_FLOW.get(uid)
        if not flow or flow.get("step") != "AWAIT_OTP":
            await event.answer("Session expire ho gaya, /start karein.", alert=True)
            return
        try:
            sent = await _resend_otp(flow)
            await event.respond(
                f"🔄 **Code dobara bhej diya gaya!**\nAb yahan aayega: {_otp_type_text(sent)}",
                buttons=_otp_buttons())
            await event.answer("Code resend ho gaya")
        except Exception as exc:
            await event.answer(f"Resend fail: {exc}"[:190], alert=True)

    # 5. Method 3: Close / Cancel
    elif data in (b"cancel_login", b"close_menu"):
        await _clean_login_flow(uid)
        await event.respond("❌ **Process close kar diya gaya hai.** Dobara login karne ke liye `/start` karein.")
        await event.answer()

    # 6. Status check
    elif data == b"status":
        if uid in ACTIVE_CLIENTS:
            cl = ACTIVE_CLIENTS[uid]
            me = await cl.get_me()
            ans = (
                "📡 **Userbot Status Report**\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "⚡ **Status**: 🟢 Active & Running\n"
                f"👤 **Account**: **{me.first_name}** (@{me.username or 'NoUsername'})\n"
                f"🆔 **User ID**: `{me.id}`\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "Aap kisi bhi group/chat me `.menu` ya `.baka` chala sakte hain!"
            )
        else:
            ans = (
                "📡 **Userbot Status Report**\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "⚡ **Status**: 🔴 Offline (Not Logged In)\n"
                "Apna userbot shuru karne ke liye **Login Userbot** button click karein."
            )
        await event.respond(ans)
        await event.answer()

    # 7. Help
    elif data == b"help":
        help_msg = (
            "📖 **Champu Userbot Commands Guide**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Userbot commands (kisi bhi group/chat me run karein):\n\n"
            "• `.menu` — Master Menu open karein\n"
            "• `.baka` — Auto Kill + Rob raid on @im_bakabot\n"
            "• `.bakarob` — Stealth rob active group members\n"
            "• `.bakabal` — Check target balance\n"
            "• `.stopbaka` — Instantly halt ongoing raid\n"
            "• `.ping` — Check latency response\n"
            "• `.admins` — Show admin list\n"
            "• `.purge <count>` — Delete messages\n\n"
            "Manager Bot Controls (is private chat me):\n"
            "• `/start` — Welcome menu and buttons\n"
            "• `/status` — View your userbot status\n"
            "• `/logout` — Disconnect and logout your userbot\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        await event.respond(help_msg)
        await event.answer()

    # 8. Logout
    elif data == b"logout":
        if uid in ACTIVE_CLIENTS:
            await stop_user_client(uid)
            await event.respond("🛑 **Aapka Champu Userbot band kar diya gaya hai aur session delete ho gaya hai.**")
        else:
            await event.respond("ℹ️ Aapka koi active userbot nahi mila.")
        await event.answer()

# ─── 3. Message Flow Handler (No command typing needed!) ───
@manager_bot.on(events.NewMessage)
async def mb_conversation_handler(event):
    if not event.is_private:
        return

    text = (event.raw_text or "").strip()
    if not text:
        return

    uid = event.sender_id

    # Handle explicit commands
    if text == "/start":
        return  # handled by mb_start
    if text in ("/login", "login"):
        return await mb_start(event)
    if text in ("/cancel", "/close", "close", "cancel"):
        await _clean_login_flow(uid)
        return await event.respond("❌ **Login process cancel kar diya gaya hai.** Dobara shuru karne ke liye `/start` karein.")
    if text == "/status":
        if uid in ACTIVE_CLIENTS:
            cl = ACTIVE_CLIENTS[uid]
            me = await cl.get_me()
            return await event.respond(
                f"📡 **Status**: 🟢 Active & Running\n👤 **Account**: **{me.first_name}** (`{me.id}`)"
            )
        else:
            return await event.respond("📡 **Status**: 🔴 Offline (Not Logged In)")
    if text == "/logout":
        if uid in ACTIVE_CLIENTS:
            await stop_user_client(uid)
            return await event.respond("🛑 **Aapka Userbot logout kar diya gaya hai.**")
        else:
            return await event.respond("ℹ️ Aapka koi active userbot nahi mila.")
    if text == "/users" and uid == OWNER_ID:
        saved = load_saved_users()
        lines = [f"👥 **Champu Userbot Network Stats**", f"━━━━━━━━━━━━━━━━━━━━━━", f"⚡ **Active Running Clients**: `{len(ACTIVE_CLIENTS)}`", f"📂 **Total Saved Accounts**: `{len(saved)}`\n"]
        for uid_str, data in saved.items():
            is_on = int(uid_str) in ACTIVE_CLIENTS
            badge = "🟢" if is_on else "🔴"
            name = data.get("first_name", "Unknown")
            uname = f"@{data.get('username')}" if data.get("username") else "NoUser"
            lines.append(f"{badge} `{uid_str}` — **{name}** ({uname})")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        return await event.respond("\n".join(lines))
    if text.startswith("/broadcast") and uid == OWNER_ID:
        parts = text.split(maxsplit=1)
        if len(parts) > 1:
            saved = load_saved_users()
            sent = 0
            for u in saved.keys():
                try:
                    await manager_bot.send_message(int(u), f"📢 **Announcement**\n━━━━━━━━━━━━━━━━━━━━━━\n{parts[1]}")
                    sent += 1
                except Exception:
                    pass
            return await event.respond(f"✅ Delivered to {sent}/{len(saved)} users.")
        else:
            return await event.respond("❌ Usage: `/broadcast <msg>`")

    # If user is in an active login flow:
    if uid not in _LOGIN_FLOW:
        return

    flow = _LOGIN_FLOW[uid]
    step = flow.get("step")

    # ─── Step A: User sent API ID ───
    if step == "AWAIT_API_ID":
        cleaned = text.strip()
        if not cleaned.isdigit() or len(cleaned) < 4:
            return await event.respond(
                "❌ **Invalid API ID!**\nAPI ID sirf numbers me hona chahiye (e.g. `12345678`).\n\nKripya sahi API ID bhejein:"
            )

        flow["api_id"] = int(cleaned)
        flow["step"] = "AWAIT_API_HASH"

        buttons = [
            [Button.inline("❌ 3. Close", data=b"cancel_login")],
        ]
        await event.respond(
            f"✅ **API ID Saved:** `{flow['api_id']}`\n\nAb apna **API HASH** yahan chat me bhejein (32 characters code):",
            buttons=buttons
        )

    # ─── Step B: User sent API HASH ───
    elif step == "AWAIT_API_HASH":
        cleaned_hash = text.strip()
        if len(cleaned_hash) < 16 or " " in cleaned_hash:
            return await event.respond(
                "❌ **Invalid API HASH!**\nAPI HASH ek 32-character code hota hai bina spaces ke.\n\nKripya sahi API HASH bhejein:"
            )

        flow["api_hash"] = cleaned_hash
        flow["step"] = "CHOOSE_METHOD"

        method_text = (
            "🎯 **Select Login Method**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ **API Credentials Saved!**\n"
            f"• API ID: `{flow['api_id']}`\n"
            f"• API HASH: `{flow['api_hash'][:8]}...`\n\n"
            "Aap kis tarike se login karna chahte hain? Niche chuniye:\n\n"
            "1️⃣ **Login By Number** — Phone number par OTP aayega.\n"
            "2️⃣ **Login By Session** — Telethon String Session paste karein.\n"
            "3️⃣ **Close** — Process cancel karein.\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        method_buttons = [
            [Button.inline("📱 1. Login By Number", data=b"method_number")],
            [Button.inline("🔑 2. Login By Session", data=b"method_session")],
            [Button.inline("❌ 3. Close", data=b"cancel_login")],
        ]
        await event.respond(method_text, buttons=method_buttons)

    # ─── Step C: User sent Phone Number ───
    elif step == "AWAIT_PHONE":
        cleaned_phone = text.strip().replace(" ", "").replace("-", "")
        if not (cleaned_phone.startswith("+") and cleaned_phone[1:].isdigit() and len(cleaned_phone) >= 9):
            return await event.respond(
                "❌ **Invalid Phone Number!**\nKripya country code ke sath bhejein, jaise: `+919876543210`:"
            )

        status_msg = await event.respond("⏳ **Telegram server se connect karke OTP bhej rahe hain...**")

        api_id = flow.get("api_id", API_ID)
        api_hash = flow.get("api_hash", API_HASH)

        try:
            temp_cl = TelegramClient(StringSession(), api_id, api_hash)
            await temp_cl.connect()

            res = await temp_cl.send_code_request(cleaned_phone)

            flow["temp_client"] = temp_cl
            flow["phone"] = cleaned_phone
            flow["phone_code_hash"] = res.phone_code_hash
            flow["step"] = "AWAIT_OTP"

            otp_prompt = (
                "📩 **Telegram OTP Request Bhej Di Gayi!**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Phone: `{cleaned_phone}`\n\n"
                f"Code yahan aayega: {_otp_type_text(res)}\n\n"
                "Code aate hi yahan bhejein:\n"
                "👉 **Example:** `12345` ya `1 2 3 4 5`\n\n"
                "Code nahi aaya? **🔄 Resend Code** dabayein ya `resend` likh kar bhejein.\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )
            await status_msg.edit(otp_prompt, buttons=_otp_buttons())

        except Exception as exc:
            await status_msg.edit(f"❌ **OTP Request Failed:** `{str(exc)}`\n\nDobara phone number bhejein:")

    # ─── Step D: User sent OTP Code ───
    elif step == "AWAIT_OTP":
        if text.strip().lower().lstrip("/") == "resend":
            try:
                sent = await _resend_otp(flow)
                return await event.respond(
                    f"🔄 **Code dobara bhej diya gaya!**\nAb yahan aayega: {_otp_type_text(sent)}",
                    buttons=_otp_buttons())
            except Exception as exc:
                return await event.respond(f"❌ **Resend fail:** `{exc}`\nKuch der baad try karein ya `/start` se dobara shuru karein.")
        clean_code = re.sub(r"[^\d]", "", text)
        if not clean_code or len(clean_code) < 3:
            return await event.respond("❌ **Invalid OTP!** Kripya sirf numbers bhejein (e.g. `12345` ya `1 2 3 4 5`):")

        temp_cl = flow.get("temp_client")
        phone = flow.get("phone")
        p_hash = flow.get("phone_code_hash")

        if not temp_cl or not phone or not p_hash:
            await _clean_login_flow(uid)
            return await event.respond("❌ Session expire ho chuka hai. Kripya `/start` se dobara shuru karein.")

        status_msg = await event.respond("🔐 **OTP verify kar rahe hain...**")

        try:
            await temp_cl.sign_in(phone, clean_code, phone_code_hash=p_hash)

            me = await temp_cl.get_me()
            success = await start_user_client(temp_cl, uid)
            _LOGIN_FLOW.pop(uid, None)

            if success:
                done_msg = (
                    "🎉 **Done! Login Successful!**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 **Account**: **{me.first_name}** (@{me.username or 'NoUsername'})\n"
                    f"🆔 **User ID**: `{me.id}`\n"
                    "⚡ **Status**: Online & Ready 🟢\n\n"
                    "Aapka Champu Userbot successfully active ho chuka hai!\n"
                    "Ab aap kisi bhi group ya chat me jakar commands use kar sakte hain:\n"
                    "• `.menu` — Master Menu open karein\n"
                    "• `.baka` — Auto Kill & Rob raid run karein\n"
                    "• `.ping` — Latency check karein\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "🔥 𝐏ᴏᴡᴇʀᴇᴅ ʙʏ 𝐂ʜᴀᴍᴘᴜ 🔥"
                )
                await status_msg.edit(done_msg)
            else:
                await status_msg.edit("❌ **Userbot activate karne me dikkat aayi. Kripya dobara try karein.**")

        except SessionPasswordNeededError:
            flow["step"] = "AWAIT_PASSWORD"
            twofa_msg = (
                "🔒 **Two-Step Verification (2FA) Password Required!**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "Aapke account par 2FA password laga hua hai.\n\n"
                "Kripya apna **2FA Password** yahan chat me bhejein:\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )
            buttons = [
                [Button.inline("❌ 3. Close", data=b"cancel_login")],
            ]
            await status_msg.edit(twofa_msg, buttons=buttons)

        except PhoneCodeInvalidError:
            await status_msg.edit("❌ **Galat OTP code!** Kripya sahi OTP dobara yahan chat me bhejein:")
        except PhoneCodeExpiredError:
            await _clean_login_flow(uid)
            await status_msg.edit("⌛ **OTP expire ho chuka hai!** Kripya `/start` se dobara shuru karein.")
        except Exception as exc:
            await status_msg.edit(f"❌ **Login Error:** `{str(exc)}`\n\nKripya dobara OTP code bhejein:")

    # ─── Step E: User sent 2FA Password ───
    elif step == "AWAIT_PASSWORD":
        password = text.strip()
        temp_cl = flow.get("temp_client")

        if not temp_cl:
            await _clean_login_flow(uid)
            return await event.respond("❌ Session expire ho gaya hai. Kripya `/start` se dobara shuru karein.")

        status_msg = await event.respond("🔐 **2FA Password verify kar rahe hain...**")

        try:
            await temp_cl.sign_in(password=password)

            me = await temp_cl.get_me()
            success = await start_user_client(temp_cl, uid)
            _LOGIN_FLOW.pop(uid, None)

            if success:
                done_msg = (
                    "🎉 **Done! 2FA Verified & Login Successful!**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 **Account**: **{me.first_name}** (@{me.username or 'NoUsername'})\n"
                    f"🆔 **User ID**: `{me.id}`\n"
                    "⚡ **Status**: Online & Ready 🟢\n\n"
                    "Aapka Champu Userbot successfully active ho chuka hai!\n"
                    "Ab aap kisi bhi group ya chat me jakar commands use kar sakte hain:\n"
                    "• `.menu` — Master Menu open karein\n"
                    "• `.baka` — Auto Kill & Rob raid run karein\n"
                    "• `.ping` — Latency check karein\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "🔥 𝐏ᴏᴡᴇʀᴇᴅ ʙʏ 𝐂ʜᴀᴍᴘᴜ 🔥"
                )
                await status_msg.edit(done_msg)
            else:
                await status_msg.edit("❌ **Userbot activate karne me dikkat aayi. Kripya dobara try karein.**")

        except PasswordHashInvalidError:
            await status_msg.edit("❌ **Galat 2FA password!** Kripya sahi password yahan dobara bhejein:")
        except Exception as exc:
            await status_msg.edit(f"❌ **2FA Verification Error:** `{str(exc)}`\n\nDobara password bhejein:")

    # ─── Step F: User sent String Session ───
    elif step == "AWAIT_SESSION":
        session_str = _to_telethon_session(text.strip())
        status_msg = await event.respond("🔑 **String session verify kar rahe hain...**")

        api_id = flow.get("api_id", API_ID)
        api_hash = flow.get("api_hash", API_HASH)

        try:
            test_cl = TelegramClient(StringSession(session_str), api_id, api_hash)
            await test_cl.connect()

            if not await test_cl.is_user_authorized():
                return await status_msg.edit("❌ **Invalid ya Expired String Session!**\nKripya sahi session yahan dobara bhejein:")

            me = await test_cl.get_me()
            success = await start_user_client(test_cl, uid)
            _LOGIN_FLOW.pop(uid, None)

            if success:
                done_msg = (
                    "🎉 **Done! String Session Accepted!**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 **Account**: **{me.first_name}** (@{me.username or 'NoUsername'})\n"
                    f"🆔 **User ID**: `{me.id}`\n"
                    "⚡ **Status**: Online & Ready 🟢\n\n"
                    "Aapka Champu Userbot successfully active ho chuka hai!\n"
                    "Ab aap kisi bhi chat me jakar `.menu` ya `.baka` use kar sakte hain!\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "🔥 𝐏ᴏᴡᴇʀᴇᴅ ʙʏ 𝐂ʜᴀᴍᴘᴜ 🔥"
                )
                await status_msg.edit(done_msg)
            else:
                await status_msg.edit("❌ **Session start karne me error aaya.**")

        except Exception as exc:
            await status_msg.edit(f"❌ **Session Error:** `{str(exc)}`\n\nKripya valid session string bhejein:")


# ────────────────────────────────────────────────
#                   START
# ────────────────────────────────────────────────
def resolve_bot_token() -> str:
    global BOT_TOKEN

    # 1. Check if configured in outer scope or globals (HIGHEST PRIORITY)
    tok = (globals().get("_OUTER_BOT_TOKEN") or globals().get("BOT_TOKEN") or "").strip()
    if tok and tok != "PUT_BOT_TOKEN_HERE" and ":" in tok:
        try:
            t_file = os.path.join(BASE_DIR, "bot_token.txt")
            with open(t_file, "w", encoding="utf-8") as f:
                f.write(tok)
        except Exception:
            pass
        return tok

    # 2. Check if saved in bot_token.txt
    t_file = os.path.join(BASE_DIR, "bot_token.txt")
    if os.path.isfile(t_file):
        try:
            with open(t_file, "r", encoding="utf-8") as f:
                saved = f.read().strip()
                if saved and ":" in saved and saved.split(":", 1)[0].isdigit():
                    BOT_TOKEN = saved
                    return saved
        except Exception:
            pass

    # 3. Interactive terminal prompt
    print("\n" + "═" * 60)
    print("🤖 CHAMPU MULTI-USERBOT MANAGER — SETUP")
    print("═" * 60)
    print("👉 Multi-Userbot chalane ke liye Telegram Bot Token chahiye.")
    print("👉 @BotFather se apna bot banayein aur uska token yahan enter karein.")
    print("   (Ya fir aap code ke upar BOT_TOKEN = '...' me bhi set kar sakte hain)")
    print("═" * 60)

    while True:
        try:
            entered = input("🔑 Bot Token enter karein (ya single-mode ke liye 'skip'): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n🛑 Cancelled.")
            return ""

        if not entered:
            continue

        if entered.lower() in ("skip", "local", "exit"):
            return ""

        if ":" in entered:
            parts = entered.split(":", 1)
            if parts[0].isdigit():
                BOT_TOKEN = entered
                try:
                    with open(t_file, "w", encoding="utf-8") as f:
                        f.write(entered)
                    print(f"💾 Bot Token 'bot_token.txt' me save ho gaya!")
                except Exception:
                    pass
                return entered

        print("❌ Invalid Bot Token format! Token me ':' aur shuru me numbers hone chahiye.")
        print("   Example: 8548118793:AAGawPsvKojumucsVEnGjamYmgcAAuoCNiI\n")


async def main():
    global primary_client

    try:
        load_admins()
        load_notes()
        load_banner()

        active_bot_token = resolve_bot_token()
        is_bot_configured = bool(active_bot_token and ":" in active_bot_token)

        if is_bot_configured:
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print("🤖 STARTING CHAMPU MULTI-USERBOT MANAGER...")
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            try:
                await manager_bot.start(bot_token=active_bot_token)
                bot_me = await manager_bot.get_me()
                uname = f"@{bot_me.username}" if bot_me.username else "Bot"
                print("\n" + "═" * 60)
                print(f"✅ TELEGRAM BOT MANAGER ONLINE: {uname} (ID: {bot_me.id})")
                print("═" * 60)
                print("🎉 Aapka Manager Bot Telegram par live ho chuka hai!")
                print(f"👉 Ab koi bhi user Telegram me {uname} ko /start bhej kar")
                print("   '🔐 Login Userbot' button se apna userbot host kar sakta hai!")
                print("═" * 60)
            except Exception as e:
                print(f"❌ Failed to start Bot Manager: {e}")
                return

            # Restore and connect all saved user clients
            saved_users = load_saved_users()
            print(f"📂 Found {len(saved_users)} saved user account(s). Connecting...")

            for uid_str, udata in saved_users.items():
                try:
                    s_str = udata.get("string_session")
                    if s_str:
                        u_client = TelegramClient(StringSession(s_str), API_ID, API_HASH, auto_reconnect=True)
                        await u_client.connect()
                        if await u_client.is_user_authorized():
                            me = await u_client.get_me()
                            u_client.user_id = me.id
                            register_client_handlers(u_client)
                            ACTIVE_CLIENTS[me.id] = u_client
                            if primary_client is None:
                                primary_client = u_client
                            print(f"👤 Activated userbot for: {me.first_name} (ID: {me.id})")
                        else:
                            print(f"⚠️ Saved session for {uid_str} is expired or invalid.")
                except Exception as exc:
                    _en = type(exc).__name__
                    if _en in ("AuthKeyDuplicatedError", "AuthKeyUnregisteredError",
                               "SessionRevokedError", "SessionExpiredError", "UserDeactivatedError"):
                        print(f"⚠️ Session for {uid_str} invalid ({_en}) — saved list se hata diya. "
                              f"Dobara login karein (same session dusri jagah bhi chal raha hoga).")
                        remove_user_session(int(uid_str))
                    else:
                        print(f"❌ Error restoring user {uid_str}: {exc}")

            # Check if standalone session exists on disk
            if os.path.isfile(f"{SESSION}.session"):
                try:
                    local_client = TelegramClient(SESSION, API_ID, API_HASH, auto_reconnect=True)
                    await local_client.connect()
                    if await local_client.is_user_authorized():
                        me = await local_client.get_me()
                        local_client.user_id = me.id
                        register_client_handlers(local_client)
                        ACTIVE_CLIENTS[me.id] = local_client
                        if primary_client is None:
                            primary_client = local_client
                        print(f"👤 Local userbot session connected: {me.first_name} (ID: {me.id})")
                except Exception as exc:
                    print(f"[LOCAL SESSION NOTICE] {exc}")

            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f"🚀 CHAMPU MULTI-USERBOT IS FULLY RUNNING! ({len(ACTIVE_CLIENTS)} userbots active)")
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            # Run indefinitely
            await asyncio.Event().wait()

        else:
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print("⚠️ BOT_TOKEN is not configured yet in usb.py!")
            print("👉 To enable the Multi-User Login Bot, set BOT_TOKEN from @BotFather in usb.py")
            print("🔄 Falling back to single-user local terminal mode...")
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            local_client = TelegramClient(SESSION, API_ID, API_HASH, auto_reconnect=True)
            await local_client.start()
            me = await local_client.get_me()
            local_client.user_id = me.id
            register_client_handlers(local_client)
            ACTIVE_CLIENTS[me.id] = local_client
            primary_client = local_client

            uname = f"@{me.username}" if me.username else "NoUsername"
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print("🤖 USERBOT STARTED LOCALLY")
            print(f"👤 Logged in as → {me.first_name} ({uname})")
            print(f"🆔 User ID → {me.id}")
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            while True:
                try:
                    await local_client.run_until_disconnected()
                    break
                except (ConnectionError, OSError):
                    print("⚠️ Connection Lost → Reconnecting...")
                    await asyncio.sleep(3)

    except KeyboardInterrupt:
        print("\n🛑 Userbot stopped manually")

    except Exception as e:
        print(f"\n❌ Startup Error → {str(e)[:80]}")

    finally:
        for cl in list(ACTIVE_CLIENTS.values()):
            try:
                if cl.is_connected():
                    await cl.disconnect()
            except Exception:
                pass
        try:
            if manager_bot.is_connected():
                await manager_bot.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError:
        # ⭐ event loop reuse fix (pydroid / termux)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
