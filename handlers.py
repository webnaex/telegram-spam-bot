"""
Telegram Bot Command Handlers2
"""
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
import config
from database import db

logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    """Prüft ob User Admin ist"""
    return user_id == config.ADMIN_USER_ID


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler für /start Command"""
    user = update.effective_user
    
    message = f"""👋 **Willkommen beim Anti-Spam Bot!**

Ich schütze diese Gruppe vor Spam-Nachrichten.

🛡️ **Features:**
• Automatische Spam-Erkennung
• Keyword-basierte Filterung
• URL-Überwachung
• Whitelist-System

📋 **Verfügbare Commands:**
/help - Hilfe anzeigen
/stats - Statistiken (nur Admin)
/config - Konfiguration (nur Admin)

Bot-Admin: {config.ADMIN_USER_ID}
Deine User ID: `{user.id}`
"""
    
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler für /help Command"""
    user = update.effective_user
    is_admin_user = is_admin(user.id)
    
    help_text = f"""❓ **HILFE - Anti-Spam Bot**

📋 **Allgemeine Commands:**
/start - Bot starten
/help - Diese Hilfe

"""
    
    if is_admin_user:
        help_text += """👑 **Admin Commands:**
/stats - Heutige Statistiken anzeigen
/config - Konfiguration verwalten
/whitelist - Whitelist verwalten
/whitelist add @username - User zur Whitelist hinzufügen
/whitelist remove @username - User von Whitelist entfernen
/whitelist list - Alle Whitelist-User anzeigen

"""
    
    help_text += f"""🛡️ **Spam-Schutz:**
Der Bot überwacht alle Nachrichten und löscht automatisch Spam basierend auf:
• Spam-Keywords (z.B. "pump", "casino", "airdrop")
• Verdächtige URLs
• Übermäßige Emojis mit Links
• Neue User mit verdächtigem Verhalten

💾 **Datenbank:** {"✅ MongoDB" if db.available else "🔧 Memory-Fallback"}
👤 **Deine User ID:** `{user.id}`
👑 **Admin:** {"✅ Ja" if is_admin_user else "❌ Nein"}
"""
    
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler für /stats Command"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text(
            f"❌ Nur der Admin kann Statistiken abrufen.\n"
            f"Deine User ID: `{user.id}`\n"
            f"Admin User ID: `{config.ADMIN_USER_ID}`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Stats abrufen
    stats = await db.get_today_stats()
    
    db_status = "✅ MongoDB" if stats["source"] == "MongoDB" else "🔧 Memory-Fallback"
    
    message = f"""📊 **SPAM STATISTIKEN (Heute)**
━━━━━━━━━━━━━━━━━━━━

🚫 **Blockiert:** {stats['spam_blocked']} Nachrichten
📈 **Spam-Rate:** {stats['spam_rate']}%
💬 **Nachrichten gesamt:** {stats['messages_total']}

✅ **Bot läuft aktiv!**
💾 **Datenbank:** {db_status}
🕐 **Zeitpunkt:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
"""
    
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)


async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler für /config Command"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text(
            "❌ Nur der Admin kann die Konfiguration verwalten.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Aktuelle Konfiguration anzeigen
    message = f"""⚙️ **BOT KONFIGURATION**
━━━━━━━━━━━━━━━━━━━━

🔍 **Spam-Erkennung:**
• Keyword-Schwelle: {config.SPAM_KEYWORD_THRESHOLD}
• Emoji-Schwelle: {config.EMOJI_THRESHOLD}
• Neue-User-Schwelle: {config.NEW_USER_KEYWORD_THRESHOLD}
• Neue-User-Fenster: {config.NEW_USER_WINDOW}s

🛡️ **Whitelist:**
• Status: {"✅ Aktiviert" if config.WHITELIST_ENABLED else "❌ Deaktiviert"}

💾 **Datenbank:**
• Status: {"✅ MongoDB verbunden" if db.available else "⚠️ Memory-Fallback"}
• URL: {"✅ Konfiguriert" if config.MONGODB_URL else "❌ Nicht gesetzt"}

🤖 **Bot:**
• Admin ID: {config.ADMIN_USER_ID}
• Token: {"✅ Gesetzt" if config.TELEGRAM_TOKEN else "❌ Nicht gesetzt"}

📝 **Hinweis:**
Konfigurationsänderungen müssen in der `config.py` vorgenommen werden.
"""
    
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)


async def whitelist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler für /whitelist Command"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text(
            "❌ Nur der Admin kann die Whitelist verwalten.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Parse arguments
    args = context.args
    
    if not args:
        # Zeige Whitelist-Hilfe
        message = """📝 **WHITELIST VERWALTUNG**
━━━━━━━━━━━━━━━━━━━━

**Commands:**
`/whitelist list` - Alle Whitelist-User anzeigen
`/whitelist add <user_id>` - User zur Whitelist hinzufügen
`/whitelist remove <user_id>` - User von Whitelist entfernen

**Beispiele:**
`/whitelist add 123456789`
`/whitelist remove 123456789`

**Hinweis:** User auf der Whitelist werden nie als Spam markiert.
"""
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        return
    
    action = args[0].lower()
    
    if action == "list":
        # Liste alle Whitelist-User
        whitelist = await db.get_whitelist()
        
        if not whitelist:
            await update.message.reply_text("📝 Whitelist ist leer.")
            return
        
        message = "📝 **WHITELIST**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for entry in whitelist:
            username = entry.get('username', 'Unknown')
            user_id = entry.get('user_id', 'N/A')
            added_at = entry.get('added_at', datetime.utcnow())
            
            message += f"👤 @{username} (ID: `{user_id}`)\n"
            message += f"   Hinzugefügt: {added_at.strftime('%Y-%m-%d %H:%M')}\n\n"
        
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    
    elif action == "add":
        if len(args) < 2:
            await update.message.reply_text(
                "❌ Bitte User ID angeben: `/whitelist add <user_id>`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        try:
            target_user_id = int(args[1])
            
            # Versuche Username zu bekommen (falls verfügbar)
            username = f"user_{target_user_id}"
            
            success = await db.add_to_whitelist(target_user_id, username, user.id)
            
            if success:
                await update.message.reply_text(
                    f"✅ User `{target_user_id}` zur Whitelist hinzugefügt!",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    "❌ Fehler beim Hinzufügen zur Whitelist.",
                    parse_mode=ParseMode.MARKDOWN
                )
        
        except ValueError:
            await update.message.reply_text(
                "❌ Ungültige User ID. Bitte Zahl eingeben.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    elif action == "remove":
        if len(args) < 2:
            await update.message.reply_text(
                "❌ Bitte User ID angeben: `/whitelist remove <user_id>`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        try:
            target_user_id = int(args[1])
            
            success = await db.remove_from_whitelist(target_user_id)
            
            if success:
                await update.message.reply_text(
                    f"✅ User `{target_user_id}` von Whitelist entfernt!",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    "❌ User nicht auf Whitelist oder Fehler beim Entfernen.",
                    parse_mode=ParseMode.MARKDOWN
                )
        
        except ValueError:
            await update.message.reply_text(
                "❌ Ungültige User ID. Bitte Zahl eingeben.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    else:
        await update.message.reply_text(
            "❌ Unbekannte Aktion. Nutze: `list`, `add` oder `remove`",
            parse_mode=ParseMode.MARKDOWN
        )
