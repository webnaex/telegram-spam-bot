# Minimal Railway Bot - ohne MongoDB für ersten Test
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

app = FastAPI(title="Telegram Anti-Spam Bot Railway", version="3.2.0")

# SPAM DETECTION CONFIGURATION
SPAM_KEYWORDS = [
    'pump', 'pumpfun', 'airdrop', 'claim', 'bonus', 'solana', 'usdt', 'sol',
    'prove', 'tokens', 'allocated', 'eligible', 'wallets', 'distributed',
    'listings', 'upbit', 'bithumb', 'binance', 'tge', 'axiom',
    'casino', 'bet', 'jackpot', 'slot', 'poker', 'gambling', 'jetluxe', 'vexway',
    'payout', 'withdraw', 'deposit', 'play now', 'player', 'promo code',
    'gift', 'free', 'money', 'cash', 'earn', 'income', 'profit', '$600', '$800'
]

SUSPICIOUS_DOMAINS = [
    'clck.ru', 'bit.ly', 'tinyurl.com', 'short.link', 'cutt.ly'
]

class TestSpamRequest(BaseModel):
    message: str
    has_media: bool = False

def get_admin_user_ids():
    admin_id = os.getenv("ADMIN_USER_ID")
    if admin_id:
        try:
            return [int(admin_id)]
        except ValueError:
            pass
    return []

def is_admin_user(user_id: int) -> bool:
    admin_ids = get_admin_user_ids()
    return not admin_ids or user_id in admin_ids

async def send_telegram_message(chat_id: int, text: str):
    try:
        telegram_token = os.getenv("TELEGRAM_TOKEN")
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"https://api.telegram.org/bot{telegram_token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
            )
    except Exception as e:
        logger.error(f"Error sending message: {e}")

async def handle_stats_command(chat_id: int, user_id: int, command: str):
    try:
        if not is_admin_user(user_id):
            await send_telegram_message(chat_id, 
                f"❌ Nur Admins können Statistik-Befehle verwenden.\
\
" +
                f"💡 **Setup-Anleitung:**\
" +
                f"1. Ihre User ID: `{user_id}`\
" +
                f"2. Setzen Sie ADMIN_USER_ID={user_id} in Railway")
            return
        
        if command == "/stats":
            message = """📊 **SPAM STATISTIKEN**
━━━━━━━━━━━━━━━━━━━━
🚫 Bot läuft: ✅
💬 Spam-Erkennung: ✅  
📊 MongoDB: ⚠️ Wird eingerichtet...

🎯 **Bot ist aktiv und blockiert Spam!**"""
            await send_telegram_message(chat_id, message)
        
        elif command == "/help":
            admin_status = "✅ Admin" if is_admin_user(user_id) else "❌ Kein Admin"
            help_message = f"""🤖 **SPAM-BOT STATUS**
━━━━━━━━━━━━━━━━━━━━
📊 `/stats` - Bot Status
❓ `/help` - Diese Hilfe

👤 **Ihr Status:** {admin_status}
🆔 **Ihre User ID:** `{user_id}`

✅ **Bot läuft und blockiert Spam!**
⚠️ Statistik-DB wird eingerichtet..."""
            await send_telegram_message(chat_id, help_message)
    
    except Exception as e:
        logger.error(f"Command error: {e}")

@app.on_event("startup")
async def startup():
    asyncio.create_task(polling_loop())
    logger.info("🚀 Minimal bot started")

@app.get("/")
async def root():
    return {
        "message": "🤖 Minimal Telegram Bot läuft!",
        "version": "3.2.0", 
        "status": "healthy"
    }

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "telegram_bot": "Anti-Spam Bot Minimal",
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
                        updates = data["result"]
                        for update in updates:
                            offset = max(offset, update["update_id"] + 1)
                            if "message" in update:
                                await process_message(update["message"])
                
        except Exception as e:
            logger.error(f"Polling error: {e}")
            await asyncio.sleep(5)
        await asyncio.sleep(1)

async def process_message(message_data: Dict[str, Any]):
    try:
        chat_id = message_data['chat']['id']
        user_id = message_data['from']['id']
        username = message_data['from'].get('username', f"user_{user_id}")
        message_text = message_data.get('text') or message_data.get('caption', '')
        
        if message_data['from'].get('is_bot'):
            return
        
        # Handle commands
        if message_text and message_text.startswith('/'):
            command = message_text.split()[0].lower()
            if command in ['/stats', '/help']:
                logger.info(f"📊 Command {command} from @{username}")
                await handle_stats_command(chat_id, user_id, command)
                return
        
        # Simple spam detection (without MongoDB)
        if message_text:
            text_lower = message_text.lower()
            spam_words = [kw for kw in SPAM_KEYWORDS if kw in text_lower]
            suspicious_urls = [domain for domain in SUSPICIOUS_DOMAINS if domain in text_lower]
            
            if len(spam_words) >= 3 or suspicious_urls:
                logger.warning(f"🚫 SPAM from @{username}: {spam_words or suspicious_urls}")
                await handle_spam(chat_id, message_data['message_id'], user_id, username)
        
    except Exception as e:
        logger.error(f"Processing error: {e}")

async def handle_spam(chat_id: int, message_id: int, user_id: int, username: str):
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
                json={"chat_id": chat_id, "text": f"🚫 Spam blockiert von @{username}!"}
            )
        logger.info(f"✅ Spam handled: @{username}")
    except Exception as e:
        logger.error(f"Spam handling error: {e}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
