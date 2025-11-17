"""
Telegram Anti-Spam Bot
Hauptdatei mit Bot-Logik und Message Handler
"""
import logging
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional

from telegram import Update, ChatMemberUpdated
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ChatMemberHandler,
    filters,
    ContextTypes
)
from telegram.constants import ParseMode
from fastapi import FastAPI
from contextlib import asynccontextmanager
import uvicorn

import config
from database import db
from spam_detector import spam_detector
from handlers import (
    start_command,
    help_command,
    stats_command,
    config_command,
    whitelist_command
)

# Logging Setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Globale Variable für Bot Application
bot_app: Optional[Application] = None

# Dictionary um neue User zu tracken (chat_id -> {user_id -> join_time})
new_users = {}


async def track_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Trackt neue Mitglieder in der Gruppe"""
    try:
        result = update.chat_member
        if result is None:
            return
        
        chat_id = result.chat.id
        new_member = result.new_chat_member
        
        if new_member.status in ["member", "restricted"]:
            user = new_member.user
            
            # Initialisiere Chat-Dictionary falls nicht vorhanden
            if chat_id not in new_users:
                new_users[chat_id] = {}
            
            # Speichere Beitrittszeit
            new_users[chat_id][user.id] = datetime.utcnow()
            
            logger.info(f"👤 Neues Mitglied: @{user.username} ({user.id}) in Chat {chat_id}")
    
    except Exception as e:
        logger.error(f"❌ Fehler beim Tracken neuer Mitglieder: {e}")


def is_new_user(chat_id: int, user_id: int) -> bool:
    """Prüft ob User neu in der Gruppe ist"""
    if chat_id not in new_users:
        return False
    
    if user_id not in new_users[chat_id]:
        return False
    
    join_time = new_users[chat_id][user_id]
    time_since_join = (datetime.utcnow() - join_time).total_seconds()
    
    return time_since_join < config.NEW_USER_WINDOW


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler für alle Nachrichten (Spam-Check)"""
    try:
        message = update.message
        if not message:
            return
        
        # Ignoriere Bot-Nachrichten
        if message.from_user.is_bot:
            return
        
        chat_id = message.chat_id
        user_id = message.from_user.id
        username = message.from_user.username or f"user_{user_id}"
        message_id = message.message_id
        
        # Text aus Nachricht oder Caption extrahieren
        text = message.text or message.caption or ""
        
        # Hat die Nachricht Media?
        has_media = bool(
            message.photo or 
            message.video or 
            message.document or 
            message.animation
        )
        
        # Prüfe ob User auf Whitelist ist
        is_whitelisted = await db.is_whitelisted(user_id)
        
        # Prüfe ob User neu ist
        is_new = is_new_user(chat_id, user_id)
        
        # NEUE REGEL: Neue User dürfen keine Media posten (nur Text)
        if is_new and has_media and not is_whitelisted:
            try:
                # Lösche Media-Nachricht
                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=message_id
                )
                
                # Sende Warnung (verschwindet nach 10 Sekunden)
                warning_msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ **Neue User dürfen keine Videos/Fotos posten!**\n"
                         f"👤 User: @{username}\n"
                         f"⏰ Bitte warte 7 Tage nach Beitritt.",
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Lösche Warnung nach 10 Sekunden
                await asyncio.sleep(10)
                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=warning_msg.message_id
                )
                
                logger.info(f"🚫 Media von neuem User blockiert: @{username} (ID: {user_id})")
                
                # Log als Spam
                await db.log_spam({
                    "id": str(uuid.uuid4()),
                    "message_id": message_id,
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "username": username,
                    "message": "[MEDIA - Neuer User]",
                    "reason": "Neue User dürfen keine Media posten",
                    "score": 100,
                    "timestamp": datetime.utcnow()
                })
                
                return  # Beende Handler, keine weitere Verarbeitung
                
            except Exception as e:
                logger.error(f"❌ Fehler beim Löschen von Media: {e}")
        
        # Log message to database
        await db.log_message({
            "id": str(uuid.uuid4()),
            "message_id": message_id,
            "chat_id": chat_id,
            "user_id": user_id,
            "username": username,
            "message": text[:500],  # Limitiere Text-Länge
            "has_media": has_media,
            "is_new_user": is_new,
            "is_whitelisted": is_whitelisted,
            "timestamp": datetime.utcnow()
        })
        
        # Spam-Erkennung
        is_spam, reason, score = spam_detector.detect_spam(
            text=text,
            has_media=has_media,
            is_new_user=is_new,
            is_whitelisted=is_whitelisted
        )
        
        if is_spam:
            # Log spam to database
            await db.log_spam({
                "id": str(uuid.uuid4()),
                "message_id": message_id,
                "chat_id": chat_id,
                "user_id": user_id,
                "username": username,
                "reason": reason,
                "score": score,
                "message_preview": text[:200],
                "timestamp": datetime.utcnow()
            })
            
            # Lösche Spam-Nachricht
            try:
                await message.delete()
                logger.warning(f"🚫 SPAM gelöscht von @{username} (Score: {score}): {reason}")
                
                # Sende Benachrichtigung
                notification = (
                    f"🚫 **Spam blockiert!**\n\n"
                    f"👤 User: @{username} (ID: `{user_id}`)\n"
                    f"📋 Grund: {reason}\n"
                    f"📊 Score: {score}/100"
                )
                
                # Sende Nachricht und lösche sie nach 10 Sekunden
                sent_msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text=notification,
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Lösche Benachrichtigung nach 10 Sekunden
                await asyncio.sleep(10)
                try:
                    await sent_msg.delete()
                except:
                    pass
                
            except Exception as e:
                logger.error(f"❌ Fehler beim Löschen der Spam-Nachricht: {e}")
    
    except Exception as e:
        logger.error(f"❌ Fehler beim Verarbeiten der Nachricht: {e}")


async def post_init(application: Application):
    """Wird nach Bot-Initialisierung aufgerufen"""
    logger.info("🤖 Bot initialisiert")
    
    # Verbinde mit MongoDB
    await db.connect()


async def post_shutdown(application: Application):
    """Wird beim Herunterfahren aufgerufen"""
    logger.info("👋 Bot wird heruntergefahren...")
    
    # Schließe MongoDB-Verbindung
    await db.close()


def create_bot_application() -> Application:
    """Erstellt und konfiguriert die Bot Application"""
    
    # Erstelle Application
    application = (
        Application.builder()
        .token(config.TELEGRAM_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    
    # Command Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("config", config_command))
    application.add_handler(CommandHandler("whitelist", whitelist_command))
    
    # Chat Member Handler (für neue Mitglieder)
    application.add_handler(ChatMemberHandler(track_new_member, ChatMemberHandler.CHAT_MEMBER))
    
    # Message Handler (für Spam-Erkennung)
    # Filtere nur Gruppen-Nachrichten
    application.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND,
            handle_message
        )
    )
    
    logger.info("✅ Bot Application erstellt")
    
    return application


# FastAPI für Health Check (Railway braucht HTTP endpoint)
@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI Lifespan Manager"""
    global bot_app
    
    # Startup
    logger.info("🚀 Starte Bot...")
    
    if not config.TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN nicht gesetzt!")
        raise ValueError("TELEGRAM_TOKEN fehlt in Umgebungsvariablen")
    
    # Erstelle Bot Application
    bot_app = create_bot_application()
    
    # Starte Bot
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling(drop_pending_updates=True)
    
    logger.info("✅ Bot läuft!")
    
    yield
    
    # Shutdown
    logger.info("🛑 Stoppe Bot...")
    if bot_app:
        await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()
    
    logger.info("👋 Bot gestoppt")


# FastAPI App
fastapi_app = FastAPI(
    title="Telegram Anti-Spam Bot",
    version="4.0.0",
    lifespan=lifespan
)


@fastapi_app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "🤖 Telegram Anti-Spam Bot läuft!",
        "version": "4.0.0",
        "status": "healthy",
        "mongodb": db.available,
        "admin_id": config.ADMIN_USER_ID
    }


@fastapi_app.get("/health")
async def health_check():
    """Health Check für Railway"""
    stats = await db.get_today_stats()
    
    return {
        "status": "healthy",
        "bot_running": bot_app is not None and bot_app.running,
        "mongodb_available": db.available,
        "stats": stats,
        "timestamp": datetime.utcnow().isoformat()
    }


@fastapi_app.get("/stats")
async def api_stats():
    """API Endpoint für Statistiken"""
    stats = await db.get_today_stats()
    return stats


if __name__ == "__main__":
    # Starte FastAPI Server (Railway startet automatisch)
    logger.info(f"🚀 Starte Server auf Port {config.PORT}...")
    
    uvicorn.run(
        fastapi_app,
        host="0.0.0.0",
        port=config.PORT,
        log_level="info"
    )
