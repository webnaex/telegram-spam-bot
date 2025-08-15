# Railway Telegram Anti-Spam Bot mit vollständigen Statistiken
# Version 3.3 - Speziell für User ID 539342443

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import uuid
from datetime import datetime, timedelta
import re
import logging
import asyncio
import httpx
import emoji
from motor.motor_asyncio import AsyncIOMotorClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Telegram Anti-Spam Bot Railway", version="3.3.0")

# Global variables
mongodb = None

# SPAM DETECTION CONFIGURATION
SPAM_KEYWORDS = [
    'pump', 'pumpfun', 'airdrop', 'claim', 'bonus', 'solana', 'usdt', 'sol',
    'prove', 'tokens', 'allocated', 'eligible', 'wallets', 'distributed',
    'listings', 'upbit', 'bithumb', 'binance', 'tge', 'axiom',
    'casino', 'bet', 'jackpot', 'slot', 'poker', 'gambling', 'jetluxe', 'vexway',
    'payout', 'withdraw', 'deposit', 'play now', 'player', 'promo code',
    'gift', 'free', 'money', 'cash', 'earn', 'income', 'profit', '$600', '$800',
    'investment', 'trading', 'forex', 'crypto', 'bitcoin',
    'limited', 'expire', 'urgent', 'immediate', 'instant', 'quick', 'fast', 'now',
    'hurry', 'act now', 'register', 'sign up', 'join', 'activate', 'redeem',
    'visit', 'website', 'click here', 'official', 'welcome', 'honor', 'launch',
    'telegram bot', 'trading bot', 'bot for trading', 'get from', 'can get'
]

SUSPICIOUS_DOMAINS = [
    'clck.ru', 'bit.ly', 'tinyurl.com', 'short.link', 'cutt.ly', 'clk.li',
    't.co', '0.ma', '1.gs', '2.gp', '3.ly', '4.gp', '5.gp', 'is.gd',
    'ow.ly', 'buff.ly', 'su.pr', 'tiny.cc', 'tinyurl.co', 'shorturl.at'
]

# ADMIN USER IDs
def get_admin_user_ids():
    admin_id = os.getenv("ADMIN_USER_ID") 
    if admin_id:
        try:
            return [int(admin_id)]
        except ValueError:
            pass
    return [539342443]  # Fallback zu Ihrer User ID

class TestSpamRequest(BaseModel):
    message: str
    has_media: bool = False

def is_admin_user(user_id: int) -> bool:
    admin_ids = get_admin_user_ids()
    return user_id in admin_ids

def detect_language(text: str) -> str:
    if not text or len(text.strip()) < 3:
        return "unknown"
    
    text_lower = text.lower()
    german_words = ['der', 'die', 'das', 'und', 'ist', 'für', 'mit', 'auf', 'ich', 'du']
    english_words = ['the', 'and', 'is', 'for', 'with', 'on', 'you', 'that', 'this']
    
    german_count = sum(1 for word in german_words if f' {word} ' in f' {text_lower} ')
    english_count = sum(1 for word in english_words if f' {word} ' in f' {text_lower} ')
    
    if german_count > english_count and german_count > 0:
        return "de"
    elif english_count > german_count and english_count > 0:
        return "en"
    return "unknown"

def has_links(text: str) -> bool:
    if not text:
        return False
    url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+])+|(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}')
    return bool(url_pattern.search(text))

def has_suspicious_links(text: str) -> bool:
    if not text:
        return False
    return any(domain in text.lower() for domain in SUSPICIOUS_DOMAINS)

def count_emojis(text: str) -> int:
    if not text:
        return 0
    try:
        return len([c for c in text if c in emoji.EMOJI_DATA])
    except:
        return 0

def contains_spam_keywords(text: str) -> List[str]:
    if not text:
        return []
    text_lower = text.lower()
    return [keyword for keyword in SPAM_KEYWORDS if keyword in text_lower]

def word_count(text: str) -> int:
    return len(text.split()) if text else 0

async def get_today_stats():
    try:
        if mongodb is None:
            return {"error": "Database wird eingerichtet..."}
        
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        spam_today = await mongodb.spam_reports.count_documents({"timestamp": {"$gte": today}})
        messages_today = await mongodb.messages.count_documents({"timestamp": {"$gte": today}})
        
        spam_rate = round((spam_today / max(messages_today, 1)) * 100, 1) if messages_today > 0 else 0
        
        return {
            "spam_blocked": spam_today,
            "messages_total": messages_today,
            "spam_rate": spam_rate
        }
    except Exception as e:
        return {"error": f"DB Fehler: {str(e)}"}

async def send_telegram_message(chat_id: int, text: str):
    try:
        telegram_token = os.getenv("TELEGRAM_TOKEN")
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"https://api.telegram.org/bot{telegram_token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
            )
    except Exception as e:
        logger.error(f"Message error: {e}")

async def handle_stats_command(chat_id: int, user_id: int, command: str):
    try:
        if not is_admin_user(user_id):
            await send_telegram_message(chat_id, 
                f"❌ Nur Admin kann Statistiken abrufen.\n" +
                f"Ihre User ID: `{user_id}`")
            return
        
        if command == "/stats":
            stats = await get_today_stats()
            if "error" in stats:
                message = f"""📊 **SPAM STATISTIKEN (Heute)**
━━━━━━━━━━━━━━━━━━━━
⚠️ Status: {stats['error']}

✅ **Bot läuft und blockiert Spam!**
🔧 Statistik-DB wird eingerichtet..."""
            else:
                message = f"""📊 **SPAM STATISTIKEN (Heute)**
━━━━━━━━━━━━━━━━━━━━
🚫 Blockiert: **{stats['spam_blocked']}** Nachrichten
📈 Spam-Rate: **{stats['spam_rate']}%**
💬 Nachrichten gesamt: **{stats['messages_total']}**

✅ **Bot läuft perfekt!**"""
            
            await send_telegram_message(chat_id, message)
        
        elif command == "/help":
            help_message = f"""🤖 **SPAM-BOT BEFEHLE**
━━━━━━━━━━━━━━━━━━━━
📊 `/stats` - Heutige Statistiken
❓ `/help` - Diese Hilfe

👤 **Admin:** ✅ (User ID: {user_id})

🛡️ **Bot schützt aktiv vor Spam!**
📊 Database: {"✅ Aktiv" if mongodb else "🔧 Setup"}"""
            await send_telegram_message(chat_id, help_message)
    
    except Exception as e:
        logger.error(f"Command error: {e}")

@app.on_event("startup")
async def startup_db_client():
    global mongodb
    try:
        mongo_url = os.getenv("MONGODB_URL") or os.getenv("MONGO_URL")
        if mongo_url:
            client = AsyncIOMotorClient(mongo_url)
            mongodb = client.telegram_spam_bot
            await client.admin.command('ping')
            logger.info("✅ MongoDB connected")
        else:
            logger.warning("⚠️ No MongoDB URL")
        
        asyncio.create_task(polling_loop())
        logger.info("🚀 Bot started for admin 539342443")
        
    except Exception as e:
        logger.error(f"Startup error: {e}")

@app.get("/")
async def root():
    return {
        "message": "🤖 @manuschatbot läuft!",
        "version": "3.3.0",
        "admin_user": "539342443",
        "status": "healthy"
    }

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "admin_user": "539342443",
        "telegram_bot": "@manuschatbot",
        "timestamp": datetime.utcnow()
    }

async def polling_loop():
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    if not telegram_token:
        return
    
    offset = 0
    logger.info("🔄 Polling started...")
    
    while True:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"https://api.telegram.org/bot{telegram_token}/getUpdates",
                    params={"offset": offset, "limit": 10, "timeout": 25}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data["ok"]:
                        for update in data["result"]:
                            offset = max(offset, update["update_id"] + 1)
                            if "message" in update:
                                await process_message(update["message"])
                
        except Exception as e:
            logger.error(f"Polling: {e}")
            await asyncio.sleep(5)
        await asyncio.sleep(1)

async def process_message(message_data: Dict[str, Any]):
    try:
        chat_id = message_data['chat']['id']
        user_id = message_data['from']['id']
        username = message_data['from'].get('username', f"user_{user_id}")
        message_text = message_data.get('text') or message_data.get('caption', '')
        message_id = message_data['message_id']
        
        if message_data['from'].get('is_bot'):
            return
        
        # Handle commands
        if message_text and message_text.startswith('/'):
            command = message_text.split()[0].lower()
            if command in ['/stats', '/help']:
                logger.info(f"📊 {command} from @{username} (ID: {user_id})")
                await handle_stats_command(chat_id, user_id, command)
                return
        
        # Basic spam detection
        if message_text:
            spam_words = contains_spam_keywords(message_text)
            has_suspicious = has_suspicious_links(message_text)
            emoji_count = count_emojis(message_text)
            words = word_count(message_text)
            
            is_spam = False
            reason = ""
            
            if has_suspicious:
                is_spam = True
                reason = "Verdächtige URL erkannt"
            elif len(spam_words) >= 3:
                is_spam = True
                reason = f"Spam Keywords: {', '.join(spam_words[:3])}"
            elif emoji_count > 10 and has_links(message_text):
                is_spam = True
                reason = f"Zu viele Emojis ({emoji_count}) mit Links"
            
            if is_spam:
                logger.warning(f"🚫 SPAM: @{username} - {reason}")
                await handle_spam(chat_id, message_id, user_id, username, reason)
            
            # Log to database if available
            if mongodb is not None:
                try:
                    await mongodb.messages.insert_one({
                        "id": str(uuid.uuid4()),
                        "message_id": message_id,
                        "chat_id": chat_id,
                        "user_id": user_id,
                        "username": username,
                        "message": message_text[:500],
                        "timestamp": datetime.utcnow(),
                        "is_spam": is_spam,
                        "spam_reason": reason if is_spam else None
                    })
                except Exception as e:
                    logger.error(f"DB log error: {e}")
        
    except Exception as e:
        logger.error(f"Processing: {e}")

async def handle_spam(chat_id: int, message_id: int, user_id: int, username: str, reason: str):
    try:
        telegram_token = os.getenv("TELEGRAM_TOKEN")
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Delete message
            await client.post(
                f"https://api.telegram.org/bot{telegram_token}/deleteMessage",
                json={"chat_id": chat_id, "message_id": message_id}
            )
            # Send notification  
            await client.post(
                f"https://api.telegram.org/bot{telegram_token}/sendMessage",
                json={"chat_id": chat_id, "text": f"🚫 Spam blockiert!\n👤 @{username}\n📋 {reason}"}
            )
            
        # Log spam report
        if mongodb is not None:
            try:
                await mongodb.spam_reports.insert_one({
                    "id": str(uuid.uuid4()),
                    "message_id": message_id,
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "username": username,
                    "reason": reason,
                    "timestamp": datetime.utcnow()
                })
            except Exception as e:
                logger.error(f"Spam log error: {e}")
                
        logger.info(f"✅ Spam handled: @{username}")
        
    except Exception as e:
        logger.error(f"Spam handling: {e}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
