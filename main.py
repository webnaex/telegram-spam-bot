# TELEGRAM ANTI-SPAM BOT - COMPLETE CODE
# Version 2.0 - Überarbeitete und optimierte Version
# Funktioniert mit FastAPI + MongoDB + Telegram Bot API

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import uuid
from datetime import datetime, timedelta
import re
import logging
from dotenv import load_dotenv
import httpx
import emoji
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException
from motor.motor_asyncio import AsyncIOMotorClient

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Telegram Anti-Spam Bot", version="2.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
bot = None
mongodb = None

# ENHANCED SPAM DETECTION CONFIGURATION
SPAM_KEYWORDS = [
    # Crypto/Token scams
    'pump', 'pumpfun', 'airdrop', 'claim', 'bonus', 'solana', 'usdt', 'sol',
    'prove', 'tokens', 'allocated', 'eligible', 'wallets', 'distributed',
    'listings', 'upbit', 'bithumb', 'binance', 'tge', 'axiom',
    
    # Casino/Gambling
    'casino', 'bet', 'jackpot', 'slot', 'poker', 'gambling', 'jetluxe', 'vexway',
    'payout', 'withdraw', 'deposit', 'play now', 'player', 'bonus', 'promo code',
    
    # Money/Financial scams
    'gift', 'free', 'money', 'cash', 'earn', 'income', 'profit', '$600', '$800',
    'investment', 'trading', 'forex', 'crypto', 'bitcoin',
    
    # Urgency tactics
    'limited', 'expire', 'urgent', 'immediate', 'instant', 'quick', 'fast', 'now',
    'hurry', 'act now', 'don\\'t miss', 'last chance', 'today only',
    
    # Promotional terms
    'register', 'sign up', 'join', 'activate', 'redeem', 'visit', 'website',
    'click here', 'official', 'welcome', 'honor', 'launch', 'special',
    
    # Trading bot patterns
    'telegram bot', 'trading bot', 'bot for trading', 'get from', 'can get'
]

SUSPICIOUS_DOMAINS = [
    'clck.ru', 'bit.ly', 'tinyurl.com', 'short.link', 'cutt.ly', 'clk.li',
    't.co', '0.ma', '1.gs', '2.gp', '3.ly', '4.gp', '5.gp', 'is.gd',
    'ow.ly', 'buff.ly', 'su.pr', 'tiny.cc', 'tinyurl.co', 'shorturl.at',
    'rb.gy', 'v.gd', 'short.gy', 'tiny.one', 'link.ly', 'go.link', 'u.to'
]

# Pydantic models
class TestSpamRequest(BaseModel):
    message: str
    has_media: bool = False

class SpamReport(BaseModel):
    message_id: int
    chat_id: int
    user_id: int
    username: str
    message: str
    reason: str
    timestamp: datetime
    action_taken: str

# Utility functions
def detect_language(text: str) -> str:
    """Detect language of text with error handling"""
    if not text or len(text.strip()) < 3:
        return "unknown"
    try:
        return detect(text)
    except LangDetectException:
        return "unknown"
    except Exception as e:
        logger.error(f"Language detection error: {e}")
        return "unknown"

def has_links(text: str) -> bool:
    """Check if text contains URLs"""
    if not text:
        return False
    url_pattern = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\\\(\\\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        r'|(?:www\\.)?[a-zA-Z0-9-]+\\.[a-zA-Z]{2,}'
        r'|[a-zA-Z0-9-]+\\.(com|org|net|edu|gov|mil|biz|info|mobi|name|aero|jobs|museum)'
    )
    return bool(url_pattern.search(text))

def has_suspicious_links(text: str) -> bool:
    """Check if text contains suspicious URL domains"""
    if not text:
        return False
    text_lower = text.lower()
    return any(domain in text_lower for domain in SUSPICIOUS_DOMAINS)

def count_emojis(text: str) -> int:
    """Count emoji characters in text"""
    if not text:
        return 0
    try:
        return len([c for c in text if c in emoji.EMOJI_DATA])
    except Exception as e:
        logger.error(f"Emoji counting error: {e}")
        return 0

def has_mentions(text: str) -> List[str]:
    """Extract @mentions from text"""
    if not text:
        return []
    mention_pattern = re.compile(r'@\\w+')
    return mention_pattern.findall(text)

def has_money_symbols(text: str) -> bool:
    """Check if text contains money symbols or amounts"""
    if not text:
        return False
    money_pattern = re.compile(
        r'[\\$€£¥₹₽¢₩₪₦₨₱₡₫₴₵₸₲₺]|\\b\\d+\\s*(dollar|euro|pound|usd|eur|gbp|sol|solana)\\b', 
        re.IGNORECASE
    )
    return bool(money_pattern.search(text))

def contains_spam_keywords(text: str) -> List[str]:
    """Check if text contains spam keywords"""
    if not text:
        return []
    text_lower = text.lower()
    return [keyword for keyword in SPAM_KEYWORDS if keyword in text_lower]

def word_count(text: str) -> int:
    """Count words in text"""
    if not text:
        return 0
    return len(text.split())

async def user_days_since_join(user_id: int, chat_id: int) -> int:
    """Get number of days since user joined"""
    try:
        if not mongodb:
            return 0
            
        user_record = await mongodb.users.find_one({
            "user_id": user_id,
            "chat_id": chat_id
        })
        
        if not user_record:
            return 0  # New user, 0 days
            
        join_time = user_record.get("join_time")
        if join_time:
            time_diff = datetime.utcnow() - join_time
            return int(time_diff.total_seconds() / 86400)  # Convert to days
            
        return 0
    except Exception as e:
        logger.error(f"Error calculating user days: {e}")
        return 0

async def is_user_new(user_id: int, chat_id: int) -> bool:
    """Check if user joined recently (within 1 hour)"""
    try:
        if not mongodb:
            return True
            
        user_record = await mongodb.users.find_one({
            "user_id": user_id,
            "chat_id": chat_id
        })
        
        if not user_record:
            return True  # User not in database, consider as new
            
        join_time = user_record.get("join_time")
        if join_time:
            time_diff = datetime.utcnow() - join_time
            return time_diff.total_seconds() < 3600  # 1 hour
            
        return True
    except Exception as e:
        logger.error(f"Error checking user status: {e}")
        return True

async def is_spam_message(message_text: str, user_id: int, chat_id: int, has_media: bool = False) -> tuple[bool, str]:
    """
    ENHANCED spam detection with comprehensive rules:
    - Media restrictions for new users
    - Emoji limits for new users
    - Word count limits for new users
    - Suspicious URLs (all users)
    - Casino/Token scam patterns (all users)
    - Multiple spam indicators
    """
    if not message_text and not has_media:
        return False, ""
    
    try:
        # Check user status
        days_since_join = await user_days_since_join(user_id, chat_id)
        is_new_user = await is_user_new(user_id, chat_id)
        
        # Media check for new users
        if has_media and days_since_join < 10:
            return True, f"Medien-Beschränkung: Neue Benutzer können erst nach 10 Tagen Bilder senden (Mitglied seit {days_since_join} Tagen)"
        
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
        
        # STRICT RULES FOR NEW USERS
        if is_new_user:
            if emoji_count > 3:
                return True, f"Emoji-Limit: Neue Benutzer dürfen max. 3 Emojis verwenden ({emoji_count} erkannt)"
            
            if words > 20:
                return True, f"Wort-Limit: Neue Benutzer dürfen max. 20 Wörter schreiben ({words} Wörter)"
            
            if is_english and mentions and not is_german:
                return True, f"@Mention-Beschränkung: Keine @mentions in englischen Nachrichten für neue Benutzer: {', '.join(mentions)}"
        
        # PRIORITY RULES FOR ALL USERS
        # 1. Suspicious URLs (highest priority)
        if has_suspicious_url:
            return True, "Verdächtige Short-URL erkannt - Sofortige Blockierung"
        
        # 2. Casino/Token scam patterns
        casino_keywords = ['jetluxe', 'vexway', 'axiom', 'casino', 'bonus', '$600', '$800', 'promo code']
        found_casino = [word for word in casino_keywords if word.lower() in message_text.lower()]
        if found_casino and (has_money or emoji_count > 2):
            return True, f"Casino-Scam erkannt: {', '.join(found_casino)}"
        
        # 3. Token/Crypto scam detection
        crypto_keywords = ['axiom', 'airdrop', 'claim', 'tokens', 'sol', 'prove', 'distributed', 'eligible']
        found_crypto = [word for word in crypto_keywords if word.lower() in message_text.lower()]
        if len(found_crypto) >= 2 and (has_money or emoji_count > 1 or mentions):
            return True, f"Token-Scam erkannt: {', '.join(found_crypto)}"
        
        # 4. Excessive emojis with links
        if emoji_count > 8 and has_url:
            return True, f"Spam-Pattern: Zu viele Emojis ({emoji_count}) mit Links"
        
        # 5. English spam with links and keywords
        if is_english and has_url and len(spam_words) >= 2:
            return True, f"Englischer Spam: Links + Keywords: {', '.join(spam_words[:5])}"
        
        # 6. Money symbols with links and spam words
        if has_money and has_url and len(spam_words) >= 2:
            return True, f"Finanz-Scam: Geld-Symbole + Links + Keywords: {', '.join(spam_words[:3])}"
        
        # 7. Multiple spam indicators
        spam_score = 0
        indicators = []
        
        if emoji_count > 5:
            spam_score += 1
            indicators.append(f"Viele Emojis ({emoji_count})")
        
        if has_money:
            spam_score += 1
            indicators.append("Geld-Symbole")
        
        if len(spam_words) >= 4:
            spam_score += 1
            indicators.append(f"Spam-Keywords ({len(spam_words)})")
        
        if has_url:
            spam_score += 1
            indicators.append("Links")
        
        if words > 50:
            spam_score += 1
            indicators.append(f"Sehr lang ({words} Wörter)")
        
        if is_english and mentions:
            spam_score += 1
            indicators.append(f"Englisch + @mentions ({len(mentions)})")
        
        if spam_score >= 3:
            return True, f"Multiple Spam-Indikatoren: {', '.join(indicators)}"
        
        return False, ""
        
    except Exception as e:
        logger.error(f"Spam detection error: {e}")
        return False, f"Fehler bei Spam-Erkennung: {str(e)}"

async def log_spam_report(message_id: int, chat_id: int, user_id: int, username: str, 
                         message: str, reason: str, action: str):
    """Log spam detection to database"""
    try:
        if not mongodb:
            return
            
        report = {
            "id": str(uuid.uuid4()),
            "message_id": message_id,
            "chat_id": chat_id,
            "user_id": user_id,
            "username": username,
            "message": message[:500],  # Limit message length
            "reason": reason,
            "action_taken": action,
            "timestamp": datetime.utcnow()
        }
        await mongodb.spam_reports.insert_one(report)
        logger.info(f"Spam report logged: {username} - {reason}")
    except Exception as e:
        logger.error(f"Error logging spam report: {e}")

# Database setup
@app.on_event("startup")
async def startup_db_client():
    global bot, mongodb
    try:
        # Initialize MongoDB
        mongo_url = os.getenv("MONGO_URL")
        if not mongo_url:
            raise Exception("MONGO_URL not found in environment variables")
        
        client = AsyncIOMotorClient(mongo_url)
        mongodb = client.telegram_spam_bot
        
        # Test connection
        await client.admin.command('ping')
        logger.info("✅ MongoDB connected successfully")
        
        # Initialize Telegram Bot
        from telegram import Bot
        telegram_token = os.getenv("TELEGRAM_TOKEN")
        if not telegram_token:
            raise Exception("TELEGRAM_TOKEN not found in environment variables")
            
        bot = Bot(token=telegram_token)
        
        # Test bot connection
        bot_info = await bot.get_me()
        logger.info(f"✅ Telegram Bot connected: @{bot_info.username}")
        
    except Exception as e:
        logger.error(f"❌ Startup error: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_db_client():
    if mongodb:
        mongodb.client.close()

# API Routes
@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    try:
        if mongodb is None:
            raise Exception("Database not connected")
        await mongodb.client.admin.command('ping')
        
        if bot is None:
            raise Exception("Bot not initialized")
        bot_info = await bot.get_me()
        
        return {
            "status": "healthy",
            "database": "connected",
            "telegram_bot": f"@{bot_info.username}",
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@app.get("/api/stats")
async def get_bot_stats():
    """Get bot statistics"""
    try:
        if not mongodb:
            raise HTTPException(status_code=500, detail="Database not connected")
            
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday = datetime.utcnow() - timedelta(days=1)
        
        # Count statistics
        spam_today = await mongodb.spam_reports.count_documents({"timestamp": {"$gte": today}})
        total_spam = await mongodb.spam_reports.count_documents({})
        messages_today = await mongodb.messages.count_documents({"timestamp": {"$gte": today}})
        total_messages = await mongodb.messages.count_documents({})
        active_users = await mongodb.users.count_documents({"join_time": {"$gte": yesterday}})
        
        spam_rate = round((spam_today / max(messages_today, 1)) * 100, 2)
        
        return {
            "spam_today": spam_today,
            "total_spam": total_spam,
            "messages_today": messages_today,
            "total_messages": total_messages,
            "active_users": active_users,
            "spam_rate": spam_rate,
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")

@app.get("/api/spam-reports")
async def get_spam_reports(limit: int = 50):
    """Get recent spam reports"""
    try:
        if not mongodb:
            raise HTTPException(status_code=500, detail="Database not connected")
            
        reports = await mongodb.spam_reports.find().sort("timestamp", -1).limit(limit).to_list(length=limit)
        return {"reports": reports, "count": len(reports)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch reports: {str(e)}")

@app.post("/api/test-spam")
async def test_spam_detection(request: TestSpamRequest):
    """Test spam detection on a message"""
    try:
        # Test with dummy user (new user for testing)
        is_spam, reason = await is_spam_message(request.message, 12345, -1001234567890, request.has_media)
        
        # Additional analysis
        language = detect_language(request.message) if request.message else "none"
        has_url = has_links(request.message)
        has_suspicious_url = has_suspicious_links(request.message)
        spam_words = contains_spam_keywords(request.message)
        words = word_count(request.message)
        emoji_count = count_emojis(request.message)
        has_money = has_money_symbols(request.message)
        mentions = has_mentions(request.message)
        
        return {
            "message": request.message,
            "has_media": request.has_media,
            "is_spam": is_spam,
            "reason": reason,
            "analysis": {
                "language": language,
                "has_links": has_url,
                "has_suspicious_links": has_suspicious_url,
                "spam_keywords": spam_words,
                "mentions": mentions,
                "word_count": words,
                "emoji_count": emoji_count,
                "has_money_symbols": has_money
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")

# Telegram webhook handler
@app.post("/api/telegram-webhook")
async def telegram_webhook_handler(request: Request):
    """Handle incoming Telegram updates via webhook"""
    try:
        update_data = await request.json()
        logger.info(f"📨 Received webhook update")
        
        if 'message' in update_data:
            await process_message(update_data['message'])
        
        return {"status": "ok", "processed": True}
        
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return {"status": "error", "error": str(e)}

async def process_message(message_data: Dict[str, Any]):
    """Process incoming message for spam detection"""
    try:
        # Extract message information
        chat_id = message_data['chat']['id']
        user_id = message_data['from']['id']
        username = message_data['from'].get('username', f"user_{user_id}")
        message_text = message_data.get('text') or message_data.get('caption', '')
        message_id = message_data['message_id']
        
        # Check if message has media
        has_media = bool(
            message_data.get('photo') or message_data.get('video') or 
            message_data.get('document') or message_data.get('sticker') or
            message_data.get('animation') or message_data.get('voice') or
            message_data.get('audio')
        )
        
        # Skip bot messages
        if message_data['from'].get('is_bot'):
            return
        
        logger.info(f"📝 Processing message from @{username}: {message_text[:50]}...")
        
        # Check for spam
        is_spam, reason = await is_spam_message(message_text, user_id, chat_id, has_media)
        
        if is_spam:
            logger.warning(f"🚫 SPAM DETECTED from @{username}: {reason}")
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
    """Handle spam message - delete, kick, notify"""
    actions_taken = []
    
    try:
        telegram_token = os.getenv("TELEGRAM_TOKEN")
        base_url = f"https://api.telegram.org/bot{telegram_token}"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Delete message
            delete_response = await client.post(
                f"{base_url}/deleteMessage",
                json={"chat_id": chat_id, "message_id": message_id}
            )
            if delete_response.status_code == 200:
                actions_taken.append("message_deleted")
                logger.info(f"🗑️ Message {message_id} deleted")
            
            # Handle different types of spam differently
            if "Medien-Beschränkung" in reason:
                # Don't kick for media restrictions, just inform
                notification = f"📷 @{username}, Bilder können erst nach 10 Tagen Mitgliedschaft gesendet werden."
                actions_taken.append("media_warning")
            else:
                # Kick user for other spam
                ban_response = await client.post(
                    f"{base_url}/banChatMember",
                    json={"chat_id": chat_id, "user_id": user_id}
                )
                if ban_response.status_code == 200:
                    actions_taken.append("user_banned")
                    logger.info(f"👤 User {user_id} banned")
                
                # Unban to allow rejoining
                await client.post(
                    f"{base_url}/unbanChatMember",
                    json={"chat_id": chat_id, "user_id": user_id}
                )
                actions_taken.append("user_unbanned")
                
                notification = f"🚫 Spam blockiert!\
👤 @{username}\
📋 {reason}"
            
            # Send notification
            await client.post(
                f"{base_url}/sendMessage",
                json={"chat_id": chat_id, "text": notification}
            )
            actions_taken.append("notification_sent")
        
        # Log spam report
        await log_spam_report(
            message_id, chat_id, user_id, username,
            "", reason, ", ".join(actions_taken)
        )
        
        logger.info(f"✅ Spam handled successfully: {', '.join(actions_taken)}")
        
    except Exception as e:
        logger.error(f"❌ Spam handling error: {e}")
        actions_taken.append(f"error: {str(e)}")

# Webhook management
@app.post("/api/set-webhook")
async def set_webhook():
    """Set Telegram webhook"""
    try:
        webhook_url = "https://your-domain.com/api/telegram-webhook"  # CHANGE THIS TO YOUR DOMAIN
        telegram_token = os.getenv("TELEGRAM_TOKEN")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.telegram.org/bot{telegram_token}/setWebhook",
                json={"url": webhook_url}
            )
            result = response.json()
        
        return {
            "status": "success",
            "webhook_url": webhook_url,
            "telegram_response": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set webhook: {str(e)}")

@app.get("/api/webhook-status")
async def get_webhook_status():
    """Get current webhook status"""
    try:
        telegram_token = os.getenv("TELEGRAM_TOKEN")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.telegram.org/bot{telegram_token}/getWebhookInfo"
            )
            result = response.json()
        
        return {"status": "success", "webhook_info": result["result"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get webhook status: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)


# =============================================================================
# INSTALLATION UND SETUP ANLEITUNG
# =============================================================================

"""
1. REQUIREMENTS INSTALLATION:
pip install fastapi uvicorn python-multipart httpx motor pymongo python-telegram-bot emoji langdetect python-dotenv

2. ENVIRONMENT VARIABLEN (.env Datei erstellen):
MONGO_URL=mongodb://localhost:27017/
TELEGRAM_TOKEN=YOUR_BOT_TOKEN_FROM_BOTFATHER
WEBHOOK_SECRET=your_secure_random_string

3. BOT SETUP BEI BOTFATHER:
- Gehe zu @BotFather in Telegram
- /newbot → Bot erstellen
- Token kopieren und in .env einfügen
- /mybots → Dein Bot → Bot Settings → Group Privacy → Disable

4. WEBHOOK EINRICHTEN:
- Domain/Server mit HTTPS benötigt
- Webhook-URL in set_webhook() Funktion ändern
- API aufrufen: POST /api/set-webhook

5. BOT ZU CHAT HINZUFÜGEN:
- Bot zu gewünschtem Chat hinzufügen
- Admin-Rechte geben:
  * Nachrichten löschen
  * Benutzer verwalten
  * Alle Nachrichten lesen

6. MONGODB SETUP:
- MongoDB installieren und starten
- Datenbank wird automatisch erstellt

7. SERVER STARTEN:
python server.py

8. TESTEN:
- POST /api/test-spam → Spam-Erkennung testen
- GET /api/health → Bot-Status prüfen
- GET /api/stats → Statistiken abrufen

SPAM-ERKENNUNGS-REGELN:
✅ Neue Benutzer: Max 3 Emojis, max 20 Wörter
✅ Medien: Nur nach 10 Tagen Mitgliedschaft
✅ Verdächtige URLs: bit.ly, tinyurl.com, clk.li etc.
✅ Casino-Scams: JETLUXE, VEXWAY mit Geld-Symbolen
✅ Token-Scams: Axiom, Airdrop, Claim mit @mentions
✅ Multiple Indikatoren: >3 Spam-Signale = Blockierung

Der Bot löscht automatisch Spam-Nachrichten, kickt Benutzer und sendet Benachrichtigungen.
"""
