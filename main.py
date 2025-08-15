# Railway-optimierte Version des Telegram Spam Bots
from fastapi import FastAPI, HTTPException, Request
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
from langdetect import detect, LangDetectException
from motor.motor_asyncio import AsyncIOMotorClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Telegram Anti-Spam Bot Railway", version="1.0.0")

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
    'ow.ly', 'buff.ly', 'su.pr', 'tiny.cc', 'tinyurl.co', 'shorturl.at',
    'rb.gy', 'v.gd', 'short.gy', 'tiny.one', 'link.ly', 'go.link', 'u.to'
]

class TestSpamRequest(BaseModel):
    message: str
    has_media: bool = False

# Utility functions
def detect_language(text: str) -> str:
    if not text or len(text.strip()) < 3:
        return "unknown"
    try:
        return detect(text)
    except:
        return "unknown"

def has_links(text: str) -> bool:
    if not text:
        return False
    url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+])+|(?:www\\.)?[a-zA-Z0-9-]+\\.[a-zA-Z]{2,}')
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

def has_mentions(text: str) -> List[str]:
    if not text:
        return []
    return re.findall(r'@\\w+', text)

def has_money_symbols(text: str) -> bool:
    if not text:
        return False
    money_pattern = re.compile(r'[\\$€£¥₹₽¢₩₪₦₨₱₡₫₴₵₸₲₺]|\\b\\d+\\s*(dollar|euro|pound|usd|eur|gbp|sol|solana)\\b', re.IGNORECASE)
    return bool(money_pattern.search(text))

def contains_spam_keywords(text: str) -> List[str]:
    if not text:
        return []
    text_lower = text.lower()
    return [keyword for keyword in SPAM_KEYWORDS if keyword in text_lower]

def word_count(text: str) -> int:
    return len(text.split()) if text else 0

async def user_days_since_join(user_id: int, chat_id: int) -> int:
    try:
        if not mongodb:
            return 0
        user_record = await mongodb.users.find_one({"user_id": user_id, "chat_id": chat_id})
        if not user_record:
            return 0
        join_time = user_record.get("join_time")
        if join_time:
            time_diff = datetime.utcnow() - join_time
            return int(time_diff.total_seconds() / 86400)
        return 0
    except:
        return 0

async def is_user_new(user_id: int, chat_id: int) -> bool:
    try:
        if not mongodb:
            return True
        user_record = await mongodb.users.find_one({"user_id": user_id, "chat_id": chat_id})
        if not user_record:
            return True
        join_time = user_record.get("join_time")
        if join_time:
            time_diff = datetime.utcnow() - join_time
            return time_diff.total_seconds() < 3600
        return True
    except:
        return True

async def is_spam_message(message_text: str, user_id: int, chat_id: int, has_media: bool = False) -> tuple[bool, str]:
    if not message_text and not has_media:
        return False, ""
    
    try:
        days_since_join = await user_days_since_join(user_id, chat_id)
        is_new_user = await is_user_new(user_id, chat_id)
        
        # Media check for new users
        if has_media and days_since_join < 10:
            return True, f"Medien-Beschränkung: Neue Benutzer können erst nach 10 Tagen Bilder senden"
        
        if not message_text:
            return False, ""
        
        # Analyze message content
        language = detect_language(message_text)
        is_english = language == 'en'
        is_german = language == 'de'
        has_url = has_links(message_text)
        has_suspicious_url = has_suspicious_links(message_text)
        spam_words = contains_spam_keywords(message_text)
        emoji_count = count_emojis(message_text)
        has_money = has_money_symbols(message_text)
        words = word_count(message_text)
        mentions = has_mentions(message_text)
        
        # NEW USER RESTRICTIONS
        if is_new_user:
            if emoji_count > 3:
                return True, f"Emoji-Limit: Neue Benutzer max. 3 Emojis ({emoji_count} erkannt)"
            if words > 20:
                return True, f"Wort-Limit: Neue Benutzer max. 20 Wörter ({words} Wörter)"
            if is_english and mentions and not is_german:
                return True, f"@Mention-Beschränkung: Keine @mentions in englischen Nachrichten"
        
        # ALL USER RESTRICTIONS
        if has_suspicious_url:
            return True, "Verdächtige Short-URL erkannt"
        
        # Casino/Token scam patterns
        casino_keywords = ['jetluxe', 'vexway', 'axiom', 'casino', 'bonus', '$600', '$800']
        found_casino = [word for word in casino_keywords if word.lower() in message_text.lower()]
        if found_casino and (has_money or emoji_count > 2):
            return True, f"Casino-Scam erkannt: {', '.join(found_casino)}"
        
        # Token/Crypto scam detection
        crypto_keywords = ['axiom', 'airdrop', 'claim', 'tokens', 'sol', 'prove']
        found_crypto = [word for word in crypto_keywords if word.lower() in message_text.lower()]
        if len(found_crypto) >= 2 and (has_money or emoji_count > 1 or mentions):
            return True, f"Token-Scam erkannt: {', '.join(found_crypto)}"
        
        # Multiple spam indicators
        spam_score = 0
        if emoji_count > 5: spam_score += 1
        if has_money: spam_score += 1
        if len(spam_words) >= 4: spam_score += 1
        if has_url: spam_score += 1
        if words > 50: spam_score += 1
        if is_english and mentions: spam_score += 1
        
        if spam_score >= 3:
            return True, f"Multiple Spam-Indikatoren erkannt"
        
        return False, ""
        
    except Exception as e:
        logger.error(f"Spam detection error: {e}")
        return False, ""

async def log_spam_report(message_id: int, chat_id: int, user_id: int, username: str, message: str, reason: str, action: str):
    try:
        if not mongodb:
            return
        report = {
            "id": str(uuid.uuid4()),
            "message_id": message_id,
            "chat_id": chat_id,
            "user_id": user_id,
            "username": username,
            "message": message[:500],
            "reason": reason,
            "action_taken": action,
            "timestamp": datetime.utcnow()
        }
        await mongodb.spam_reports.insert_one(report)
    except Exception as e:
        logger.error(f"Error logging spam report: {e}")

# Database setup
@app.on_event("startup")
async def startup_db_client():
    global mongodb
    try:
        # Use Railway's internal MongoDB or external service
        mongo_url = os.getenv("MONGODB_URL") or os.getenv("MONGO_URL")
        if mongo_url:
            client = AsyncIOMotorClient(mongo_url)
            mongodb = client.telegram_spam_bot
            await client.admin.command('ping')
            logger.info("✅ MongoDB connected")
        else:
            logger.warning("⚠️ No MongoDB URL found - running without database")
        
        # Start polling
        asyncio.create_task(polling_loop())
        logger.info("🚀 Bot polling started")
        
    except Exception as e:
        logger.error(f"❌ Startup error: {e}")

# API Routes
@app.get("/")
async def root():
    return {"message": "Telegram Anti-Spam Bot is running!", "status": "healthy"}

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "telegram_bot": "@manuschatbot",
        "timestamp": datetime.utcnow()
    }

@app.post("/api/test-spam")
async def test_spam_detection(request: TestSpamRequest):
    try:
        is_spam, reason = await is_spam_message(request.message, 12345, -1001234567890, request.has_media)
        
        return {
            "message": request.message,
            "has_media": request.has_media,
            "is_spam": is_spam,
            "reason": reason,
            "analysis": {
                "language": detect_language(request.message),
                "has_links": has_links(request.message),
                "has_suspicious_links": has_suspicious_links(request.message),
                "spam_keywords": contains_spam_keywords(request.message),
                "mentions": has_mentions(request.message),
                "word_count": word_count(request.message),
                "emoji_count": count_emojis(request.message),
                "has_money_symbols": has_money_symbols(request.message)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Telegram Polling
async def polling_loop():
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    if not telegram_token:
        logger.error("❌ No TELEGRAM_TOKEN found!")
        return
    
    offset = 0
    logger.info("🔄 Starting Telegram polling...")
    
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
                        updates = data["result"]
                        
                        for update in updates:
                            offset = max(offset, update["update_id"] + 1)
                            
                            if "message" in update:
                                await process_message(update["message"])
                
        except Exception as e:
            logger.error(f"❌ Polling error: {e}")
            await asyncio.sleep(5)
        
        await asyncio.sleep(1)

async def process_message(message_data: Dict[str, Any]):
    try:
        chat_id = message_data['chat']['id']
        user_id = message_data['from']['id']
        username = message_data['from'].get('username', f"user_{user_id}")
        message_text = message_data.get('text') or message_data.get('caption', '')
        message_id = message_data['message_id']
        
        has_media = bool(
            message_data.get('photo') or message_data.get('video') or 
            message_data.get('document') or message_data.get('sticker') or
            message_data.get('animation') or message_data.get('voice') or
            message_data.get('audio')
        )
        
        if message_data['from'].get('is_bot'):
            return
        
        logger.info(f"📝 Processing message from @{username}")
        
        is_spam, reason = await is_spam_message(message_text, user_id, chat_id, has_media)
        
        if is_spam:
            logger.warning(f"🚫 SPAM DETECTED: {reason}")
            await handle_spam(chat_id, message_id, user_id, username, reason)
        
        # Log message
        if mongodb:
            await mongodb.messages.insert_one({
                "id": str(uuid.uuid4()),
                "message_id": message_id,
                "chat_id": chat_id,
                "user_id": user_id,
                "username": username,
                "message": message_text[:500],
                "has_media": has_media,
                "timestamp": datetime.utcnow(),
                "is_spam": is_spam,
                "spam_reason": reason if is_spam else None
            })
        
    except Exception as e:
        logger.error(f"❌ Message processing error: {e}")

async def handle_spam(chat_id: int, message_id: int, user_id: int, username: str, reason: str):
    try:
        telegram_token = os.getenv("TELEGRAM_TOKEN")
        base_url = f"https://api.telegram.org/bot{telegram_token}"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Delete message
            await client.post(f"{base_url}/deleteMessage", 
                            json={"chat_id": chat_id, "message_id": message_id})
            
            if "Medien-Beschränkung" in reason:
                notification = f"📷 @{username}, Bilder erst nach 10 Tagen Mitgliedschaft erlaubt."
            else:
                # Ban and unban user
                await client.post(f"{base_url}/banChatMember", 
                                json={"chat_id": chat_id, "user_id": user_id})
                await client.post(f"{base_url}/unbanChatMember", 
                                json={"chat_id": chat_id, "user_id": user_id})
                notification = f"🚫 Spam blockiert!\
👤 @{username}\
📋 {reason}"
            
            # Send notification
            await client.post(f"{base_url}/sendMessage", 
                            json={"chat_id": chat_id, "text": notification})
        
        await log_spam_report(message_id, chat_id, user_id, username, "", reason, "handled")
        logger.info(f"✅ Spam handled successfully")
        
    except Exception as e:
        logger.error(f"❌ Spam handling error: {e}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
