# Railway Telegram Anti-Spam Bot mit vollständigen Statistiken
# Version 3.0 - Mit allen Statistik-Commands und optimiert für Railway.app

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

app = FastAPI(title="Telegram Anti-Spam Bot Railway", version="3.0.0")

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

# ADMIN USER IDs
def get_admin_user_ids():
    """Get admin user IDs from environment or allow all for testing"""
    admin_id = os.getenv("ADMIN_USER_ID")
    if admin_id:
        try:
            return [int(admin_id)]
        except ValueError:
            logger.error(f"Invalid ADMIN_USER_ID: {admin_id}")
            pass
    return []  # Empty = all users can use commands (for testing)

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

def has_mentions(text: str) -> List[str]:
    if not text:
        return []
    return re.findall(r'@\w+', text)

def has_money_symbols(text: str) -> bool:
    if not text:
        return False
    money_pattern = re.compile(r'[\$€£¥₹₽¢₩₪₦₨₱₡₫₴₵₸₲₺]|\b\d+\s*(dollar|euro|pound|usd|eur|gbp|sol|solana)\b', re.IGNORECASE)
    return bool(money_pattern.search(text))

def contains_spam_keywords(text: str) -> List[str]:
    if not text:
        return []
    text_lower = text.lower()
    return [keyword for keyword in SPAM_KEYWORDS if keyword in text_lower]

def word_count(text: str) -> int:
    return len(text.split()) if text else 0

def is_admin_user(user_id: int) -> bool:
    """Check if user is admin (can use statistics commands)"""
    admin_ids = get_admin_user_ids()
    return not admin_ids or user_id in admin_ids

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

# STATISTICS FUNCTIONS
async def get_today_stats():
    """Get today's spam statistics"""
    try:
        if not mongodb:
            return {"error": "Database not available"}
        
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        spam_today = await mongodb.spam_reports.count_documents({"timestamp": {"$gte": today}})
        messages_today = await mongodb.messages.count_documents({"timestamp": {"$gte": today}})
        
        # Get spam by type today
        spam_pipeline = [
            {"$match": {"timestamp": {"$gte": today}}},
            {"$group": {"_id": "$reason", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]
        spam_by_type = await mongodb.spam_reports.aggregate(spam_pipeline).to_list(length=5)
        
        spam_rate = round((spam_today / max(messages_today, 1)) * 100, 1) if messages_today > 0 else 0
        
        return {
            "spam_blocked": spam_today,
            "messages_total": messages_today,
            "spam_rate": spam_rate,
            "spam_by_type": spam_by_type
        }
    except Exception as e:
        logger.error(f"Error getting today stats: {e}")
        return {"error": str(e)}

async def get_week_report():
    """Get weekly spam report"""
    try:
        if not mongodb:
            return {"error": "Database not available"}
        
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        spam_week = await mongodb.spam_reports.count_documents({"timestamp": {"$gte": week_ago}})
        messages_week = await mongodb.messages.count_documents({"timestamp": {"$gte": week_ago}})
        
        # Top spam keywords this week
        keyword_counts = {}
        spam_reports = await mongodb.spam_reports.find({"timestamp": {"$gte": week_ago}}).to_list(length=1000)
        
        for report in spam_reports:
            reason = report.get('reason', '')
            for keyword in SPAM_KEYWORDS:
                if keyword.lower() in reason.lower():
                    keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
        
        top_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        new_users = await mongodb.users.count_documents({"join_time": {"$gte": week_ago}})
        
        return {
            "spam_blocked": spam_week,
            "messages_total": messages_week,
            "spam_rate": round((spam_week / max(messages_week, 1)) * 100, 1),
            "top_keywords": top_keywords,
            "new_users": new_users
        }
    except Exception as e:
        logger.error(f"Error getting week report: {e}")
        return {"error": str(e)}

async def get_top_keywords_today():
    """Get top spam keywords today"""
    try:
        if not mongodb:
            return {"error": "Database not available"}
        
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        keyword_counts = {}
        spam_reports = await mongodb.spam_reports.find({"timestamp": {"$gte": today}}).to_list(length=1000)
        
        for report in spam_reports:
            reason = report.get('reason', '')
            for keyword in SPAM_KEYWORDS:
                if keyword.lower() in reason.lower():
                    keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
        
        top_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {"top_keywords": top_keywords}
    except Exception as e:
        logger.error(f"Error getting top keywords: {e}")
        return {"error": str(e)}

async def send_telegram_message(chat_id: int, text: str):
    """Send message to Telegram chat"""
    try:
        telegram_token = os.getenv("TELEGRAM_TOKEN")
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"https://api.telegram.org/bot{telegram_token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
            )
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")

async def handle_stats_command(chat_id: int, user_id: int, command: str):
    """Handle statistics commands"""
    try:
        if not is_admin_user(user_id):
            await send_telegram_message(chat_id, 
                f"❌ Nur Admins können Statistik-Befehle verwenden.\n\n" +
                f"💡 **Setup-Anleitung:**\n" +
                f"1. Ihre User ID: `{user_id}`\n" +
                f"2. Setzen Sie ADMIN_USER_ID={user_id} in Railway\n" +
                f"3. Dann können Sie alle Statistik-Commands nutzen!")
            return
        
        if command == "/stats":
            stats = await get_today_stats()
            if "error" in stats:
                await send_telegram_message(chat_id, f"❌ Fehler: {stats['error']}")
                return
            
            message = f"""📊 **SPAM STATISTIKEN (Heute)**
━━━━━━━━━━━━━━━━━━━━
🚫 Blockiert: **{stats['spam_blocked']}** Nachrichten
📈 Spam-Rate: **{stats['spam_rate']}%**
💬 Nachrichten gesamt: **{stats['messages_total']}**

🎯 **Top Spam-Typen:**"""
            
            for spam_type in stats.get('spam_by_type', [])[:3]:
                reason = spam_type['_id'][:50] + "..." if len(spam_type['_id']) > 50 else spam_type['_id']
                message += f"\n• {reason}: {spam_type['count']}x"
            
            await send_telegram_message(chat_id, message)
        
        elif command == "/report":
            report = await get_week_report()
            if "error" in report:
                await send_telegram_message(chat_id, f"❌ Fehler: {report['error']}")
                return
            
            message = f"""📋 **WOCHEN-REPORT (7 Tage)**
━━━━━━━━━━━━━━━━━━━━
🚫 Spam blockiert: **{report['spam_blocked']}**
📊 Spam-Rate: **{report['spam_rate']}%**
💬 Nachrichten gesamt: **{report['messages_total']}**
👥 Neue Benutzer: **{report['new_users']}**

🔥 **Top Spam-Keywords:**"""
            
            for keyword, count in report.get('top_keywords', [])[:5]:
                message += f"\n• {keyword}: {count}x"
            
            await send_telegram_message(chat_id, message)
        
        elif command == "/top":
            top_data = await get_top_keywords_today()
            if "error" in top_data:
                await send_telegram_message(chat_id, f"❌ Fehler: {top_data['error']}")
                return
            
            message = "🏆 **TOP SPAM-KEYWORDS (Heute)**\n━━━━━━━━━━━━━━━━━━━━"
            
            if not top_data.get('top_keywords'):
                message += "\n✅ Noch keine Spam-Keywords heute erkannt!"
            else:
                for i, (keyword, count) in enumerate(top_data['top_keywords'][:10], 1):
                    emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                    message += f"\n{emoji} **{keyword}**: {count}x"
            
            await send_telegram_message(chat_id, message)
        
        elif command == "/help":
            admin_status = "✅ Admin" if is_admin_user(user_id) else "❌ Kein Admin"
            help_message = f"""🤖 **SPAM-BOT BEFEHLE**
━━━━━━━━━━━━━━━━━━━━
📊 `/stats` - Heutige Statistiken
📋 `/report` - 7-Tage Report  
🏆 `/top` - Top Spam-Keywords heute
❓ `/help` - Diese Hilfe

👤 **Ihr Status:** {admin_status}
🆔 **Ihre User ID:** `{user_id}`

💡 **Admin werden:**
Setzen Sie ADMIN_USER_ID={user_id} in Railway"""
            await send_telegram_message(chat_id, help_message)
        
        else:
            await send_telegram_message(chat_id, "❓ Unbekannter Befehl. Nutze `/help` für alle Befehle.")
    
    except Exception as e:
        logger.error(f"Error handling stats command: {e}")
        await send_telegram_message(chat_id, "❌ Fehler beim Verarbeiten des Befehls.")

# Database setup
@app.on_event("startup")
async def startup_db_client():
    global mongodb
    try:
        # MongoDB Connection
        mongo_url = os.getenv("MONGODB_URL") or os.getenv("MONGO_URL")
        if mongo_url:
            client = AsyncIOMotorClient(mongo_url)
            mongodb = client.telegram_spam_bot
            await client.admin.command('ping')
            logger.info("✅ MongoDB connected")
        else:
            logger.warning("⚠️ No MongoDB URL found")
        
        # Start Telegram polling
        asyncio.create_task(polling_loop())
        logger.info("🚀 Bot polling started")
        
    except Exception as e:
        logger.error(f"❌ Startup error: {e}")

# API Routes
@app.get("/")
async def root():
    admin_count = len(get_admin_user_ids())
    return {
        "message": "🤖 Telegram Anti-Spam Bot mit Statistiken läuft!",
        "version": "3.0.0", 
        "status": "healthy",
        "features": [
            "Spam-Erkennung", 
            "Statistik-Commands", 
            "Web-Dashboard",
            "MongoDB-Integration"
        ],
        "admin_users_configured": admin_count,
        "telegram_commands": ["/stats", "/report", "/top", "/help"]
    }

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "telegram_bot": "Anti-Spam Bot",
        "timestamp": datetime.utcnow(),
        "version": "3.0.0"
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
        
        # Skip bot messages
        if message_data['from'].get('is_bot'):
            return
        
        # Handle statistics commands first
        if message_text and message_text.startswith('/'):
            command = message_text.split()[0].lower()
            if command in ['/stats', '/report', '/top', '/help', '/users', '/trends']:
                logger.info(f"📊 Command {command} from @{username} (ID: {user_id})")
                await handle_stats_command(chat_id, user_id, command)
                return
        
        has_media = bool(
            message_data.get('photo') or message_data.get('video') or 
            message_data.get('document') or message_data.get('sticker') or
            message_data.get('animation') or message_data.get('voice') or
            message_data.get('audio')
        )
        
        logger.info(f"📝 Processing message from @{username} (ID: {user_id})")
        
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
                notification = f"🚫 Spam blockiert!\n👤 @{username}\n📋 {reason}"
            
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

