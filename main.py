"""
Telegram Anti-Spam Bot
Hauptdatei mit Bot-Logik, CAPTCHA-System und Message Handler
"""
import logging
import asyncio
import uuid
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple

from telegram import Update, ChatMemberUpdated, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ChatMemberHandler,
    CallbackQueryHandler,
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
    whitelist_command,
    spam_command,
    notspam_command,
    keywords_command
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

# Dictionary für CAPTCHA Verifications (user_id -> {challenge, answer, message_id, task})
pending_verifications: Dict[int, Dict] = {}

# Dictionary für verifizierte User (user_id -> verification_time)
verified_users: Dict[int, datetime] = {}


# CAPTCHA Challenges
CAPTCHA_CHALLENGES = [
    # Mathe - Einfach
    ("Was ist 2 + 3?", "5", ["4", "5", "6", "7"]),
    ("Was ist 7 - 4?", "3", ["2", "3", "4", "5"]),
    ("Was ist 5 + 2?", "7", ["6", "7", "8", "9"]),
    ("Was ist 10 - 3?", "7", ["6", "7", "8", "9"]),
    ("Was ist 4 + 4?", "8", ["7", "8", "9", "10"]),
    
    # Mathe - Mittel
    ("Was ist 6 × 2?", "12", ["10", "11", "12", "14"]),
    ("Was ist 15 - 8?", "7", ["6", "7", "8", "9"]),
    ("Was ist 9 + 6?", "15", ["14", "15", "16", "17"]),
    ("Was ist 20 - 12?", "8", ["7", "8", "9", "10"]),
    
    # Einfache Fragen
    ("Wie viele Finger hat eine Hand?", "5", ["4", "5", "6", "10"]),
    ("Wie viele Tage hat eine Woche?", "7", ["5", "6", "7", "8"]),
    ("Wie viele Stunden hat ein Tag?", "24", ["12", "20", "24", "30"]),
    ("Bist du ein Mensch?", "Ja", ["Ja", "Nein", "Vielleicht", "Weiß nicht"]),
    ("Bist du ein Bot?", "Nein", ["Ja", "Nein", "Vielleicht", "Weiß nicht"]),
]


def generate_captcha() -> Tuple[str, str, list]:
    """Generiert eine zufällige CAPTCHA-Challenge"""
    question, correct_answer, options = random.choice(CAPTCHA_CHALLENGES)
    
    # Mische die Optionen
    shuffled_options = options.copy()
    random.shuffle(shuffled_options)
    
    return question, correct_answer, shuffled_options


async def send_captcha(chat_id: int, user_id: int, username: str, context: ContextTypes.DEFAULT_TYPE):
    """Sendet CAPTCHA an neuen User"""
    try:
        # Generiere Challenge
        question, correct_answer, options = generate_captcha()
        
        # Erstelle Inline Keyboard
        keyboard = []
        row = []
        for i, option in enumerate(options):
            row.append(InlineKeyboardButton(
                option,
                callback_data=f"captcha_{user_id}_{option}"
            ))
            # 2 Buttons pro Zeile
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:  # Rest hinzufügen
            keyboard.append(row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Sende CAPTCHA-Nachricht
        message_text = (
            f"👋 **Willkommen @{username}!**\n\n"
            f"🔒 **Bitte verifiziere dich um fortzufahren:**\n\n"
            f"❓ {question}\n\n"
            f"⏰ Du hast **120 Sekunden** Zeit!"
        )
        
        sent_message = await context.bot.send_message(
            chat_id=chat_id,
            text=message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Erstelle Timeout-Task
        timeout_task = asyncio.create_task(
            captcha_timeout(chat_id, user_id, username, sent_message.message_id, context)
        )
        
        # Speichere Verification
        pending_verifications[user_id] = {
            "chat_id": chat_id,
            "username": username,
            "question": question,
            "correct_answer": correct_answer,
            "message_id": sent_message.message_id,
            "timeout_task": timeout_task,
            "timestamp": datetime.utcnow()
        }
        
        logger.info(f"🔒 CAPTCHA gesendet an @{username} (ID: {user_id})")
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Senden von CAPTCHA: {e}")


async def captcha_timeout(chat_id: int, user_id: int, username: str, message_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Timeout-Handler für CAPTCHA (120 Sekunden)"""
    try:
        await asyncio.sleep(120)  # 120 Sekunden warten
        
        # Prüfe ob User noch pending ist
        if user_id in pending_verifications:
            logger.warning(f"⏰ CAPTCHA Timeout für @{username} (ID: {user_id})")
            
            # Lösche CAPTCHA-Nachricht
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            except:
                pass
            
            # Kicke User
            try:
                await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
                await context.bot.unban_chat_member(chat_id=chat_id, user_id=user_id)  # Unban = Kick
                
                # Log CAPTCHA-Kick
                await db.log_captcha_kick({
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "username": username,
                    "chat_id": chat_id,
                    "reason": "CAPTCHA Timeout (120s)",
                    "timestamp": datetime.utcnow()
                })
                
                logger.info(f"👢 User @{username} wegen CAPTCHA-Timeout gekickt")
                
            except Exception as e:
                logger.error(f"❌ Fehler beim Kicken: {e}")
            
            # Entferne aus pending
            del pending_verifications[user_id]
            
    except asyncio.CancelledError:
        # Task wurde abgebrochen (User hat rechtzeitig geantwortet)
        pass
    except Exception as e:
        logger.error(f"❌ Fehler im CAPTCHA-Timeout: {e}")


async def handle_captcha_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler für CAPTCHA Button-Klicks"""
    try:
        query = update.callback_query
        await query.answer()
        
        # Parse callback data: "captcha_{user_id}_{answer}"
        parts = query.data.split("_")
        if len(parts) < 3 or parts[0] != "captcha":
            return
        
        captcha_user_id = int(parts[1])
        user_answer = "_".join(parts[2:])  # Falls Antwort "_" enthält
        
        # Prüfe ob User der Klicker ist
        if query.from_user.id != captcha_user_id:
            await query.answer("❌ Das ist nicht dein CAPTCHA!", show_alert=True)
            return
        
        # Prüfe ob Verification pending ist
        if captcha_user_id not in pending_verifications:
            await query.answer("⚠️ CAPTCHA abgelaufen!", show_alert=True)
            return
        
        verification = pending_verifications[captcha_user_id]
        correct_answer = verification["correct_answer"]
        chat_id = verification["chat_id"]
        username = verification["username"]
        message_id = verification["message_id"]
        timeout_task = verification["timeout_task"]
        
        # Stoppe Timeout-Task
        timeout_task.cancel()
        
        # Prüfe Antwort
        if user_answer == correct_answer:
            # ✅ RICHTIG!
            logger.info(f"✅ CAPTCHA bestanden: @{username} (ID: {captcha_user_id})")
            
            # Lösche CAPTCHA-Nachricht
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            except:
                pass
            
            # Sende Erfolgs-Nachricht (verschwindet nach 5 Sekunden)
            success_msg = await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ **@{username} erfolgreich verifiziert!**\n\n"
                     f"ℹ️ Hinweis: Videos/Fotos erst nach 7 Tagen erlaubt.",
                parse_mode=ParseMode.MARKDOWN
            )
            
            await asyncio.sleep(5)
            try:
                await success_msg.delete()
            except:
                pass
            
            # Markiere als verifiziert
            verified_users[captcha_user_id] = datetime.utcnow()
            
            # Entferne aus pending
            del pending_verifications[captcha_user_id]
            
        else:
            # ❌ FALSCH!
            logger.warning(f"❌ CAPTCHA falsch: @{username} (ID: {captcha_user_id})")
            
            # Lösche CAPTCHA-Nachricht
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            except:
                pass
            
            # Kicke User
            try:
                await context.bot.ban_chat_member(chat_id=chat_id, user_id=captcha_user_id)
                await context.bot.unban_chat_member(chat_id=chat_id, user_id=captcha_user_id)
                
                # Log CAPTCHA-Kick
                await db.log_captcha_kick({
                    "id": str(uuid.uuid4()),
                    "user_id": captcha_user_id,
                    "username": username,
                    "chat_id": chat_id,
                    "reason": "CAPTCHA falsche Antwort",
                    "timestamp": datetime.utcnow()
                })
                
                logger.info(f"👢 User @{username} wegen falscher CAPTCHA-Antwort gekickt")
                
            except Exception as e:
                logger.error(f"❌ Fehler beim Kicken: {e}")
            
            # Entferne aus pending
            del pending_verifications[captcha_user_id]
            
    except Exception as e:
        logger.error(f"❌ Fehler beim Verarbeiten von CAPTCHA-Callback: {e}")


def is_verified(user_id: int) -> bool:
    """Prüft ob User verifiziert ist"""
    return user_id in verified_users


async def track_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Trackt neue Mitglieder und sendet CAPTCHA"""
    try:
        result = update.chat_member
        if result is None:
            return
        
        chat_id = result.chat.id
        new_member = result.new_chat_member
        
        if new_member.status in ["member", "restricted"]:
            user = new_member.user
            
            # Ignoriere Bots
            if user.is_bot:
                return
            
            # Initialisiere Chat-Dictionary falls nicht vorhanden
            if chat_id not in new_users:
                new_users[chat_id] = {}
            
            # Speichere Beitrittszeit
            new_users[chat_id][user.id] = datetime.utcnow()
            
            logger.info(f"👤 Neues Mitglied: @{user.username} ({user.id}) in Chat {chat_id}")
            
            # Sende CAPTCHA
            await send_captcha(chat_id, user.id, user.username or f"user_{user.id}", context)
    
    except Exception as e:
        logger.error(f"❌ Fehler beim Tracken neuer Mitglieder: {e}")


def is_new_user(chat_id: int, user_id: int) -> bool:
    """Prüft ob User neu in der Gruppe ist (< 7 Tage)"""
    if chat_id not in new_users:
        return False
    
    if user_id not in new_users[chat_id]:
        return False
    
    join_time = new_users[chat_id][user_id]
    time_since_join = (datetime.utcnow() - join_time).total_seconds()
    
    return time_since_join < config.NEW_USER_WINDOW


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler für alle Nachrichten (CAPTCHA-Check + Spam-Check)"""
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
        
        # Prüfe ob User auf Whitelist ist
        is_whitelisted = await db.is_whitelisted(user_id)
        
        # Whitelist-User überspringen alle Checks
        if is_whitelisted:
            return
        
        # CAPTCHA-CHECK: Prüfe ob User noch nicht verifiziert ist
        if user_id in pending_verifications:
            # User muss erst CAPTCHA lösen!
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
                
                # Sende Warnung (verschwindet nach 5 Sekunden)
                warning = await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ @{username}, bitte löse erst das CAPTCHA!",
                    parse_mode=ParseMode.MARKDOWN
                )
                await asyncio.sleep(5)
                try:
                    await warning.delete()
                except:
                    pass
                
            except Exception as e:
                logger.error(f"❌ Fehler beim Löschen: {e}")
            
            return  # Keine weitere Verarbeitung
        
        # User ist verifiziert, normale Checks
        
        # Text aus Nachricht oder Caption extrahieren
        text = message.text or message.caption or ""
        
        # Hat die Nachricht Media?
        has_media = bool(
            message.photo or 
            message.video or 
            message.document or 
            message.animation
        )
        
        # Prüfe ob User neu ist
        is_new = is_new_user(chat_id, user_id)
        
        # NEUE REGEL: Media ohne Text = Spam (für ALLE User!)
        if has_media and not text.strip():
            try:
                # Lösche Media-Nachricht
                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=message_id
                )
                
                # Sende Warnung (verschwindet nach 10 Sekunden)
                warning_msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ **Media ohne Text ist nicht erlaubt!**\n"
                         f"👤 User: @{username}\n"
                         f"💬 Bitte füge eine Beschreibung hinzu.",
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Lösche Warnung nach 10 Sekunden
                await asyncio.sleep(10)
                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=warning_msg.message_id
                )
                
                logger.info(f"🚫 Media ohne Text blockiert: @{username} (ID: {user_id})")
                
                # Log als Media-Block
                await db.log_media_block({
                    "id": str(uuid.uuid4()),
                    "message_id": message_id,
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "username": username,
                    "reason": "Media ohne Text nicht erlaubt",
                    "timestamp": datetime.utcnow()
                })
                
                return  # Beende Handler
                
            except Exception as e:
                logger.error(f"❌ Fehler beim Löschen von Media: {e}")
        
        # Log message to database
        await db.log_message({
            "id": str(uuid.uuid4()),
            "message_id": message_id,
            "chat_id": chat_id,
            "user_id": user_id,
            "username": username,
            "message": text[:500],
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
    
    # Feedback/Learning Commands
    application.add_handler(CommandHandler("spam", spam_command))
    application.add_handler(CommandHandler("notspam", notspam_command))
    application.add_handler(CommandHandler("keywords", keywords_command))
    
    # CAPTCHA Callback Handler
    application.add_handler(CallbackQueryHandler(handle_captcha_callback, pattern="^captcha_"))
    
    # Chat Member Handler (für neue Mitglieder + CAPTCHA)
    application.add_handler(ChatMemberHandler(track_new_member, ChatMemberHandler.CHAT_MEMBER))
    
    # Message Handler (für Spam-Erkennung)
    application.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND,
            handle_message
        )
    )
    
    logger.info("✅ Bot Application erstellt")
    
    return application


# FastAPI für Health Check
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
    
    # Lade gelernte Keywords aus DB
    try:
        learned_kw = await db.get_learned_keywords()
        spam_detector.set_learned_keywords(learned_kw)
        logger.info(f"🧠 {len(learned_kw)} gelernte Keywords geladen")
    except Exception as e:
        logger.error(f"❌ Fehler beim Laden von Keywords: {e}")
    
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
    title="Telegram Anti-Spam Bot with CAPTCHA",
    version="5.0.0",
    lifespan=lifespan
)


@fastapi_app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "🤖 Telegram Anti-Spam Bot mit CAPTCHA läuft!",
        "version": "5.0.0",
        "status": "healthy",
        "mongodb": db.available,
        "features": ["CAPTCHA", "7-Day Media Block", "Spam Detection"]
    }


@fastapi_app.get("/health")
async def health_check():
    """Health Check für Railway"""
    stats = await db.get_today_stats()
    
    return {
        "status": "healthy",
        "bot_running": bot_app is not None and bot_app.running,
        "mongodb_available": db.available,
        "pending_captchas": len(pending_verifications),
        "verified_users": len(verified_users),
        "stats": stats,
        "timestamp": datetime.utcnow().isoformat()
    }


@fastapi_app.get("/stats")
async def api_stats():
    """API Endpoint für Statistiken"""
    stats = await db.get_today_stats()
    return stats


if __name__ == "__main__":
    # Starte FastAPI Server
    logger.info(f"🚀 Starte Server auf Port {config.PORT}...")
    
    uvicorn.run(
        fastapi_app,
        host="0.0.0.0",
        port=config.PORT,
        log_level="info"
    )
