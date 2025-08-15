# Railway Telegram Anti-Spam Bot - Funktioniert OHNE MongoDB
# Version 3.4 - Sofort-Fix für User ID 539342443

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import logging
import asyncio
import httpx
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Telegram Anti-Spam Bot Railway", version="3.4.0")

# In-Memory Statistiken (ohne DB)
stats_cache = {
    "spam_blocked_today": 0,
    "messages_today": 0,
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
    import re
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

def reset_daily_stats():
    """Reset stats if new day"""
    global stats_cache
    today = datetime.utcnow().date()
    if stats_cache["last_reset"] != today:
        stats_cache["spam_blocked_today"] = 0
        stats_cache["messages_today"] = 0
        stats_cache["last_reset"] = today

def get_today_stats():
    reset_daily_stats()
    spam_rate = round((stats_cache["spam_blocked_today"] / max(stats_cache["messages_today"], 1)) * 100, 1)
    
    return {
        "spam_blocked": stats_cache["spam_blocked_today"],
        "messages_total": stats_cache["messages_today"], 
        "spam_rate": spam_rate
    }

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
                f"❌ Nur Admin kann Statistiken abrufen.\
" +
                f"Ihre User ID: `{user_id}`")
            return
        
        if command == "/stats":
            stats = get_today_stats()
            message = f"""📊 **SPAM STATISTIKEN (Heute)**
━━━━━━━━━━━━━━━━━━━━
🚫 Blockiert: **{stats['spam_blocked']}** Nachrichten
📈 Spam-Rate: **{stats['spam_rate']}%**
💬 Nachrichten gesamt: **{stats['messages_total']}**

✅ **Bot läuft perfekt!**
🔧 Live-Statistiken (ohne DB)"""
            
            await send_telegram_message(chat_id, message)
        
        elif command == "/help":
            help_message = f"""🤖 **SPAM-BOT BEFEHLE**
━━━━━━━━━━━━━━━━━━━━
📊 `/stats` - Heutige Live-Statistiken
❓ `/help` - Diese Hilfe

👤 **Admin:** ✅ (User ID: {user_id})

🛡️ **Bot schützt aktiv vor Spam!**
📊 Live-Statistiken: ✅ Funktioniert"""
            await send_telegram_message(chat_id, help_message)
    
    except Exception as e:
        logger.error(f"Command error: {e}")

@app.on_event("startup")
async def startup():
    asyncio.create_task(polling_loop())
    logger.info("🚀 Bot started - OHNE MongoDB, mit Live-Stats!")

@app.get("/")
async def root():
    return {
        "message": "🤖 @manuschatbot läuft PERFEKT!",
        "version": "3.4.0",
        "admin_user": "539342443",
        "status": "healthy",
        "database": "Live-Stats (kein MongoDB nötig)"
    }

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "admin_user": "539342443", 
        "telegram_bot": "@manuschatbot",
        "stats": get_today_stats(),
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
    global stats_cache
    try:
        chat_id = message_data['chat']['id']
        user_id = message_data['from']['id']
        username = message_data['from'].get('username', f"user_{user_id}")
        message_text = message_data.get('text') or message_data.get('caption', '')
        message_id = message_data['message_id']
        
        if message_data['from'].get('is_bot'):
            return
        
        # Count message
        reset_daily_stats()
        stats_cache["messages_today"] += 1
        
        # Handle commands
        if message_text and message_text.startswith('/'):
            command = message_text.split()[0].lower()
            if command in ['/stats', '/help']:
                logger.info(f"📊 {command} from @{username} (ID: {user_id})")
                await handle_stats_command(chat_id, user_id, command)
                return
        
        # Spam detection
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
                stats_cache["spam_blocked_today"] += 1
                logger.warning(f"🚫 SPAM: @{username} - {reason}")
                await handle_spam(chat_id, message_id, user_id, username, reason)
        
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
                json={"chat_id": chat_id, "text": f"🚫 Spam blockiert!\
👤 @{username}\
📋 {reason}"}
            )
                
        logger.info(f"✅ Spam handled: @{username}")
        
    except Exception as e:
        logger.error(f"Spam handling: {e}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
