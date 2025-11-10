# Railway Telegram Anti-Spam Bot mit CAPTCHA System
# Version 4.0 - CAPTCHA für neue User + MongoDB Integration

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import uuid
import logging
import asyncio
import httpx
import re
import random
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Telegram Anti-Spam Bot Railway", version="4.0.0")

# Global variables
mongodb = None
mongodb_available = False

# CAPTCHA & User Verification System
user_verification = {}  # In-memory storage für user verification status
captcha_questions = [
    {"question": "Schreiben Sie das Wort 'verifiziert' um zu bestätigen, dass Sie ein echter Mensch sind:", "answer": "verifiziert"},
    {"question": "Anti-Spam Verifikation: Schreiben Sie 'mensch' als Antwort:", "answer": "mensch"},
    {"question": "Bestätigen Sie, dass Sie kein Bot sind. Schreiben Sie 'echt':", "answer": "echt"},
    {"question": "Verifikation erforderlich: Tippen Sie 'bestätigt':", "answer": "bestätigt"},
    {"question": "Spam-Schutz aktiv: Schreiben Sie 'freischalten':", "answer": "freischalten"}
]

# Fallback Stats (wenn MongoDB nicht verfügbar)
fallback_stats = {
    "spam_blocked_today": 0,
    "messages_today": 0,
    "captcha_solved_today": 0,
    "captcha_failed_today": 0,
    "last_reset": datetime.utcnow().date()
}

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

class TestSpamRequest(BaseModel):
    message: str
    has_media: bool = False

def is_admin_user(user_id: int) -> bool:
    admin_id = os.getenv("ADMIN_USER_ID", "539342443")
    return str(user_id) == str(admin_id)

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
        import emoji
        return len([c for c in text if c in emoji.EMOJI_DATA])
    except:
        # Fallback emoji counting
        emoji_chars = ['😀', '😁', '😂', '🤣', '😃', '😄', '😅', '😆', '😉', '😊', '🔥', '💎', '🚀', '💰', '🎉', '❤️', '👍', '👎', '🙏', '💪']
        return sum(1 for char in text if char in emoji_chars)

def contains_spam_keywords(text: str) -> List[str]:
    if not text:
        return []
    text_lower = text.lower()
    return [keyword for keyword in SPAM_KEYWORDS if keyword in text_lower]

def word_count(text: str) -> int:
    return len(text.split()) if text else 0

# CAPTCHA & USER VERIFICATION FUNCTIONS
async def is_user_verified(user_id: int, chat_id: int) -> bool:
    """Check if user is verified"""
    user_key = f"{chat_id}_{user_id}"
    
    # Check memory first
    if user_key in user_verification:
        return user_verification[user_key].get("verified", False)
    
    # Check MongoDB if available
    if mongodb_available and mongodb is not None:
        try:
            user_record = await mongodb.verified_users.find_one({
                "user_id": user_id,
                "chat_id": chat_id
            })
            if user_record:
                # Cache in memory
                user_verification[user_key] = {
                    "verified": True,
                    "verification_time": user_record.get("verification_time", datetime.utcnow())
                }
                return True
        except Exception as e:
            logger.error(f"Error checking verification: {e}")
    
    return False

async def verify_user(user_id: int, chat_id: int, username: str):
    """Mark user as verified"""
    user_key = f"{chat_id}_{user_id}"
    verification_time = datetime.utcnow()
    
    # Store in memory
    user_verification[user_key] = {
        "verified": True,
        "verification_time": verification_time
    }
    
    # Store in MongoDB if available
    await log_to_db("verified_users", {
        "user_id": user_id,
        "chat_id": chat_id,
        "username": username,
        "verification_time": verification_time,
        "id": str(uuid.uuid4())
    })
    
    logger.info(f"✅ User verified: @{username} (ID: {user_id})")

def get_random_captcha():
    """Get random CAPTCHA question"""
    return random.choice(captcha_questions)

async def send_captcha(chat_id: int, user_id: int, username: str):
    """Send CAPTCHA challenge to user"""
    try:
        captcha = get_random_captcha()
        
        captcha_message = f"""🔒 **VERIFIKATION ERFORDERLICH**
━━━━━━━━━━━━━━━━━━━━

👋 Hallo @{username}!

🛡️ Zum Schutz vor Spam müssen neue Mitglieder verifiziert werden.

❓ **{captcha['question']}**

⏰ Sie haben 5 Minuten Zeit.
🚫 Andere Nachrichten werden bis zur Verifikation gelöscht."""

        telegram_token = os.getenv("TELEGRAM_TOKEN")
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"https://api.telegram.org/bot{telegram_token}/sendMessage",
                json={
                    "chat_id": chat_id, 
                    "text": captcha_message, 
                    "parse_mode": "Markdown",
                    "reply_to_message_id": None
                }
            )
        
        # Store expected answer in memory
        user_key = f"{chat_id}_{user_id}"
        user_verification[user_key] = {
            "verified": False,
            "expected_answer": captcha['answer'].lower(),
            "captcha_sent_time": datetime.utcnow(),
            "attempts": 0
        }
        
    except Exception as e:
        logger.error(f"Error sending CAPTCHA: {e}")

async def check_captcha_answer(user_id: int, chat_id: int, username: str, message_text: str) -> bool:
    """Check if CAPTCHA answer is correct"""
    user_key = f"{chat_id}_{user_id}"
    
    if user_key not in user_verification:
        return False
    
    user_data = user_verification[user_key]
    expected_answer = user_data.get("expected_answer", "").lower()
    user_answer = message_text.strip().lower()
    
    # Increment attempts
    user_data["attempts"] = user_data.get("attempts", 0) + 1
    
    if user_answer == expected_answer:
        # Correct answer!
        await verify_user(user_id, chat_id, username)
        reset_daily_fallback()
        fallback_stats["captcha_solved_today"] += 1
        
        await send_telegram_message(chat_id, f"""✅ **VERIFIKATION ERFOLGREICH**

🎉 Willkommen @{username}!

Sie sind jetzt verifiziert und können normal chatten.
🛡️ Unser Bot schützt diese Gruppe vor Spam.""")
        
        return True
    else:
        # Wrong answer
        reset_daily_fallback()
        fallback_stats["captcha_failed_today"] += 1
        
        if user_data["attempts"] >= 3:
            # Too many attempts - kick user
            await kick_user(chat_id, user_id, username, "Zu viele CAPTCHA-Fehlversuche")
            del user_verification[user_key]
        else:
            # Send CAPTCHA again
            await send_captcha(chat_id, user_id, username)
        
        return False

async def kick_user(chat_id: int, user_id: int, username: str, reason: str):
    """Kick user from chat"""
    try:
        telegram_token = os.getenv("TELEGRAM_TOKEN")
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Ban user
            await client.post(
                f"https://api.telegram.org/bot{telegram_token}/banChatMember",
                json={"chat_id": chat_id, "user_id": user_id}
            )
            # Unban to allow rejoining
            await client.post(
                f"https://api.telegram.org/bot{telegram_token}/unbanChatMember",
                json={"chat_id": chat_id, "user_id": user_id}
            )
            # Send notification
            await client.post(
                f"https://api.telegram.org/bot{telegram_token}/sendMessage",
                json={"chat_id": chat_id, "text": f"🚫 @{username} wurde entfernt.\n📋 Grund: {reason}"}
            )
        logger.info(f"👤 User kicked: @{username} - {reason}")
    except Exception as e:
        logger.error(f"Error kicking user: {e}")

def reset_daily_fallback():
    """Reset fallback stats if new day"""
    global fallback_stats
    today = datetime.utcnow().date()
    if fallback_stats["last_reset"] != today:
        fallback_stats["spam_blocked_today"] = 0
        fallback_stats["messages_today"] = 0
        fallback_stats["captcha_solved_today"] = 0
        fallback_stats["captcha_failed_today"] = 0
        fallback_stats["last_reset"] = today

async def get_today_stats():
    """Get today's statistics - MongoDB first, fallback second"""
    try:
        if mongodb_available and mongodb is not None:
            # Try MongoDB first
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            spam_today = await mongodb.spam_reports.count_documents({"timestamp": {"$gte": today}})
            messages_today = await mongodb.messages.count_documents({"timestamp": {"$gte": today}})
            captcha_solved = await mongodb.verified_users.count_documents({"verification_time": {"$gte": today}})
            
            spam_rate = round((spam_today / max(messages_today, 1)) * 100, 1) if messages_today > 0 else 0
            
            return {
                "spam_blocked": spam_today,
                "messages_total": messages_today,
                "captcha_solved": captcha_solved,
                "captcha_failed": 0,  # Schwer aus DB zu berechnen
                "spam_rate": spam_rate,
                "source": "MongoDB"
            }
    except Exception as e:
        logger.error(f"MongoDB stats error: {e}")
    
    # Fallback to memory stats
    reset_daily_fallback()
    spam_rate = round((fallback_stats["spam_blocked_today"] / max(fallback_stats["messages_today"], 1)) * 100, 1)
    
    return {
        "spam_blocked": fallback_stats["spam_blocked_today"],
        "messages_total": fallback_stats["messages_today"],
        "captcha_solved": fallback_stats["captcha_solved_today"],
        "captcha_failed": fallback_stats["captcha_failed_today"],
        "spam_rate": spam_rate,
        "source": "Live-Memory"
    }

async def setup_mongodb():
    """Robuste MongoDB Setup mit mehreren URLs"""
    global mongodb, mongodb_available
    
    # Alle möglichen MongoDB URLs probieren
    possible_urls = [
        os.getenv("MONGODB_URL"),
        os.getenv("DATABASE_URL"), 
        os.getenv("MONGO_URL"),
        "mongodb://mongo:pjLGFTJxaIuKJfIRnNhQLaEGRAMGudJt@mongodb.railway.internal:27017",
        "mongodb://mongo:pjLGFTJxaIuKJfIRnNhQLaEGRAMGudJt@mongodb.railway.internal:27017/telegram_spam_bot"
    ]
    
    for url in possible_urls:
        if not url:
            continue
        
        try:
            logger.info(f"🔄 Trying MongoDB: {url[:30]}...")
            
            from motor.motor_asyncio import AsyncIOMotorClient
            client = AsyncIOMotorClient(url, serverSelectionTimeoutMS=5000)
            mongodb = client.telegram_spam_bot
            
            # Test connection
            await client.admin.command('ping')
            mongodb_available = True
            logger.info(f"✅ MongoDB connected successfully!")
            return True
            
        except Exception as e:
            logger.warning(f"❌ MongoDB failed: {str(e)[:100]}")
            continue
    
    logger.warning("⚠️ MongoDB not available - using memory stats")
    mongodb_available = False
    return False

async def log_to_db(collection: str, data: dict):
    """Safely log to MongoDB with fallback"""
    try:
        if mongodb_available and mongodb is not None:
            await getattr(mongodb, collection).insert_one(data)
            return True
    except Exception as e:
        logger.error(f"DB log error: {e}")
    return False

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
            
            db_status = "✅ MongoDB" if stats["source"] == "MongoDB" else "🔧 Live-Memory"
            
            message = f"""📊 **SPAM STATISTIKEN (Heute)**
━━━━━━━━━━━━━━━━━━━━
🚫 Spam blockiert: **{stats['spam_blocked']}**
📈 Spam-Rate: **{stats['spam_rate']}%**
💬 Nachrichten gesamt: **{stats['messages_total']}**

🔒 **CAPTCHA STATISTIKEN**
✅ Erfolgreich verifiziert: **{stats['captcha_solved']}**
❌ Fehlgeschlagen: **{stats['captcha_failed']}**

✅ **Bot läuft perfekt!**
💾 Datenbank: {db_status}
🛡️ CAPTCHA-Schutz: Aktiv
📹 **NEU:** Videos ohne Text = Spam"""
            
            await send_telegram_message(chat_id, message)
        
        elif command == "/help":
            db_status = "✅ MongoDB" if mongodb_available else "🔧 Live"
            help_message = f"""🤖 **SPAM-BOT BEFEHLE**
━━━━━━━━━━━━━━━━━━━━
📊 `/stats` - Statistiken mit CAPTCHA
❓ `/help` - Diese Hilfe

👤 **Admin:** ✅ (User ID: {user_id})

🛡️ **Schutz-Features:**
• Spam-Erkennung (38 Keywords)
• CAPTCHA für neue User
• Verdächtige Link-Erkennung
• Emoji-Spam Filter
• **📹 Videos ohne Text blockieren**
• **🖼️ Bilder ohne Beschreibung blockieren**

💾 Datenbank: {db_status}"""
            await send_telegram_message(chat_id, help_message)
    
    except Exception as e:
        logger.error(f"Command error: {e}")

@app.on_event("startup")
async def startup_db_client():
    try:
        # Setup MongoDB (with fallback)
        await setup_mongodb()
        
        # Start Telegram polling
        asyncio.create_task(polling_loop())
        logger.info("🚀 Bot started with robust MongoDB handling!")
        
    except Exception as e:
        logger.error(f"Startup error: {e}")

@app.get("/")
async def root():
    return {
        "message": "🤖 @manuschatbot läuft PERFEKT mit CAPTCHA!",
        "version": "4.0.0",
        "admin_user": "539342443",
        "status": "healthy",
        "mongodb_available": mongodb_available,
        "features": ["Spam Detection", "CAPTCHA System", "Admin Commands"]
    }

@app.get("/api/health")
async def health_check():
    stats = await get_today_stats()
    return {
        "status": "healthy",
        "admin_user": "539342443",
        "telegram_bot": "@manuschatbot",
        "mongodb_available": mongodb_available,
        "captcha_enabled": True,
        "stats": stats,
        "timestamp": datetime.utcnow()
    }

async def polling_loop():
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    if not telegram_token:
        logger.error("❌ No TELEGRAM_TOKEN!")
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
    global fallback_stats
    try:
        chat_id = message_data['chat']['id']
        user_id = message_data['from']['id']
        username = message_data['from'].get('username', f"user_{user_id}")
        message_text = message_data.get('text') or message_data.get('caption', '')
        message_id = message_data['message_id']
        
        if message_data['from'].get('is_bot'):
            return
        
        # Skip admin user from CAPTCHA
        if is_admin_user(user_id):
            return
        
        # Count message (fallback)
        reset_daily_fallback()
        fallback_stats["messages_today"] += 1
        
        # Handle commands first
        if message_text and message_text.startswith('/'):
            command = message_text.split()[0].lower()
            if command in ['/stats', '/help']:
                logger.info(f"📊 {command} from @{username} (ID: {user_id})")
                await handle_stats_command(chat_id, user_id, command)
                return
        
        # Check if user is verified
        is_verified = await is_user_verified(user_id, chat_id)
        
        if not is_verified:
            # User is not verified - handle CAPTCHA
            user_key = f"{chat_id}_{user_id}"
            
            if user_key in user_verification and not user_verification[user_key].get("verified", False):
                # User has pending CAPTCHA - check answer
                if message_text:
                    # Delete their message first
                    await delete_message(chat_id, message_id)
                    
                    # Check if it's correct CAPTCHA answer
                    is_correct = await check_captcha_answer(user_id, chat_id, username, message_text)
                    if is_correct:
                        # User is now verified, process normally
                        return
                    else:
                        # Wrong answer, CAPTCHA sent again or user kicked
                        return
                else:
                    # Non-text message from unverified user
                    await delete_message(chat_id, message_id)
                    await send_captcha(chat_id, user_id, username)
                    return
            else:
                # First message from new user - send CAPTCHA
                await delete_message(chat_id, message_id)
                await send_captcha(chat_id, user_id, username)
                logger.info(f"🔒 CAPTCHA sent to new user: @{username} (ID: {user_id})")
                return
        
        # User is verified - normal spam detection
        if message_text:
            spam_words = contains_spam_keywords(message_text)
            has_suspicious = has_suspicious_links(message_text)
            emoji_count = count_emojis(message_text)
            
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
                fallback_stats["spam_blocked_today"] += 1
                logger.warning(f"🚫 SPAM: @{username} - {reason}")
                await handle_spam(chat_id, message_id, user_id, username, reason)
                
                # Log spam to DB (if available)
                await log_to_db("spam_reports", {
                    "id": str(uuid.uuid4()),
                    "message_id": message_id,
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "username": username,
                    "reason": reason,
                    "timestamp": datetime.utcnow()
                })
        
        # Check for MEDIA SPAM (Videos/Images without text)
        has_video = bool(message_data.get('video') or message_data.get('video_note'))
        has_image = bool(message_data.get('photo'))
        has_document = bool(message_data.get('document'))
        has_animation = bool(message_data.get('animation'))
        has_sticker = bool(message_data.get('sticker'))
        
        # Media without text or caption = SPAM
        if (has_video or has_image or has_document or has_animation or has_sticker) and not message_text:
            is_spam = True
            media_type = ""
            if has_video: media_type = "Video"
            elif has_image: media_type = "Bild" 
            elif has_document: media_type = "Dokument"
            elif has_animation: media_type = "GIF/Animation"
            elif has_sticker: media_type = "Sticker"
            
            reason = f"{media_type} ohne Text/Beschreibung"
            
            fallback_stats["spam_blocked_today"] += 1
            logger.warning(f"🚫 MEDIA SPAM: @{username} - {reason}")
            await handle_spam(chat_id, message_id, user_id, username, reason)
            
            # Log media spam to DB
            await log_to_db("spam_reports", {
                "id": str(uuid.uuid4()),
                "message_id": message_id,
                "chat_id": chat_id,
                "user_id": user_id,
                "username": username,
                "reason": reason,
                "media_type": media_type,
                "timestamp": datetime.utcnow()
            })
            return
            
        # Log normal message to DB (if available)
        if message_text or has_video or has_image:  # Log all messages with content
            await log_to_db("messages", {
                "id": str(uuid.uuid4()),
                "message_id": message_id,
                "chat_id": chat_id,
                "user_id": user_id,
                "username": username,
                "message": message_text[:500] if message_text else "[MEDIA]",
                "has_media": has_video or has_image or has_document or has_animation,
                "media_type": media_type if (has_video or has_image or has_document or has_animation) else None,
                "timestamp": datetime.utcnow(),
                "is_spam": False,
                "spam_reason": None,
                "user_verified": True
            })
        
    except Exception as e:
        logger.error(f"Processing: {e}")

async def delete_message(chat_id: int, message_id: int):
    """Delete a message"""
    try:
        telegram_token = os.getenv("TELEGRAM_TOKEN")
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"https://api.telegram.org/bot{telegram_token}/deleteMessage",
                json={"chat_id": chat_id, "message_id": message_id}
            )
    except Exception as e:
        logger.error(f"Error deleting message: {e}")

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
                
        logger.info(f"✅ Spam handled: @{username}")
        
    except Exception as e:
        logger.error(f"Spam handling: {e}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
