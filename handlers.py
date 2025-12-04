"""
Telegram Bot Command Handlers
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
    return user_id in config.ADMIN_USER_IDS


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

Bot-Admins: {', '.join(map(str, config.ADMIN_USER_IDS))}
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

🧠 **Feedback/Learning:**
/spam - Als Reply: Nachricht als Spam markieren & Keywords lernen
/notspam - Als Reply: False Positive markieren
/keywords - Gelernte Keywords verwalten
/keywords list - Alle gelernten Keywords anzeigen
/keywords remove <keyword> - Keyword entfernen

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
    
    captcha_kicks = stats.get('captcha_kicks', 0)
    media_blocks = stats.get('media_blocks', 0)
    
    message = f"""📊 **STATISTIKEN (Heute)**
━━━━━━━━━━━━━━━━━━━━

🚫 **Spam blockiert:** {stats['spam_blocked']}
👢 **CAPTCHA-Kicks:** {captcha_kicks}
📹 **Media blockiert (neue User):** {media_blocks}

📈 **Gesamt Nachrichten:** {stats['messages_total']}
🛡️ **Spam-Rate:** {stats['spam_rate']}%

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
• Admin IDs: {', '.join(map(str, config.ADMIN_USER_IDS))}
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
`/whitelist add <user_id|@username>` - User zur Whitelist hinzufügen
`/whitelist remove <user_id|@username>` - User von Whitelist entfernen

**Beispiele:**
`/whitelist add 123456789`
`/whitelist add @max`
`/whitelist remove @anna`

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
                "❌ Bitte User ID oder Username angeben: `/whitelist add <user_id|@username>`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        user_input = args[1]
        target_user_id = None
        username = None
        
        # Prüfe ob Username (startet mit @)
        if user_input.startswith('@'):
            username = user_input[1:]  # Entferne @
            
            # Versuche User ID über Chat Member zu bekommen
            try:
                chat_member = await context.bot.get_chat_member(
                    chat_id=update.effective_chat.id,
                    user_id=f"@{username}"
                )
                target_user_id = chat_member.user.id
                username = chat_member.user.username or username
            except Exception as e:
                await update.message.reply_text(
                    f"❌ User @{username} nicht gefunden in dieser Gruppe.\n"
                    f"Stelle sicher, dass der User in der Gruppe ist!",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
        else:
            # Es ist eine User ID
            try:
                target_user_id = int(user_input)
                username = f"user_{target_user_id}"
            except ValueError:
                await update.message.reply_text(
                    "❌ Ungültige Eingabe. Nutze User ID (123456789) oder Username (@max)",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
        
        # Füge zur Whitelist hinzu
        success = await db.add_to_whitelist(target_user_id, username, user.id)
        
        if success:
            await update.message.reply_text(
                f"✅ User @{username} (ID: `{target_user_id}`) zur Whitelist hinzugefügt!",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                "❌ Fehler beim Hinzufügen zur Whitelist.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    elif action == "remove":
        if len(args) < 2:
            await update.message.reply_text(
                "❌ Bitte User ID oder Username angeben: `/whitelist remove <user_id|@username>`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        user_input = args[1]
        target_user_id = None
        
        # Prüfe ob Username (startet mit @)
        if user_input.startswith('@'):
            username = user_input[1:]  # Entferne @
            
            # Versuche User ID über Chat Member zu bekommen
            try:
                chat_member = await context.bot.get_chat_member(
                    chat_id=update.effective_chat.id,
                    user_id=f"@{username}"
                )
                target_user_id = chat_member.user.id
            except Exception as e:
                await update.message.reply_text(
                    f"❌ User @{username} nicht gefunden in dieser Gruppe.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
        else:
            # Es ist eine User ID
            try:
                target_user_id = int(user_input)
            except ValueError:
                await update.message.reply_text(
                    "❌ Ungültige Eingabe. Nutze User ID (123456789) oder Username (@max)",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
        
        # Von Whitelist entfernen
        success = await db.remove_from_whitelist(target_user_id)
        
        if success:
            await update.message.reply_text(
                f"✅ User (ID: `{target_user_id}`) von Whitelist entfernt!",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                "❌ User nicht auf Whitelist oder Fehler beim Entfernen.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    else:
        await update.message.reply_text(
            "❌ Unbekannte Aktion. Nutze: `list`, `add` oder `remove`",
            parse_mode=ParseMode.MARKDOWN
        )


async def spam_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler für /spam Command - Nachricht als Spam markieren und Keywords lernen"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text(
            "❌ Nur Admins können Nachrichten als Spam markieren.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Prüfe ob Command als Reply verwendet wurde
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "❌ Bitte antworte auf eine Nachricht mit `/spam` um sie als Spam zu markieren.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    spam_message = update.message.reply_to_message
    spam_text = spam_message.text or spam_message.caption or ""
    
    if not spam_text:
        await update.message.reply_text(
            "❌ Die Nachricht enthält keinen Text zum Analysieren.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Extrahiere Keywords aus der Spam-Nachricht
    # Einfache Keyword-Extraktion: Wörter mit 4+ Buchstaben, lowercase
    import re
    words = re.findall(r'\b[a-zA-ZäöüÄÖÜß]{4,}\b', spam_text.lower())
    
    # Filtere häufige Wörter (Stopwords)
    stopwords = {'dass', 'eine', 'sein', 'haben', 'werden', 'können', 'müssen', 
                 'sollen', 'wollen', 'dürfen', 'mögen', 'auch', 'noch', 'mehr',
                 'sehr', 'aber', 'oder', 'wenn', 'dann', 'weil', 'damit',
                 'this', 'that', 'have', 'been', 'with', 'from', 'they', 'will',
                 'what', 'when', 'where', 'which', 'about', 'their', 'there'}
    
    keywords = [w for w in words if w not in stopwords and len(w) >= 4]
    
    # Entferne Duplikate
    keywords = list(set(keywords))
    
    if not keywords:
        await update.message.reply_text(
            "⚠️ Keine relevanten Keywords in der Nachricht gefunden.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Speichere Keywords in DB
    added_count = 0
    for keyword in keywords[:10]:  # Max 10 Keywords pro Nachricht
        success = await db.add_learned_keyword(
            keyword=keyword,
            category="learned_spam",
            added_by=user.id,
            source_message=spam_text[:500]
        )
        if success:
            added_count += 1
    
    # Lösche die Spam-Nachricht
    try:
        await spam_message.delete()
        deleted_msg = "✅ Spam-Nachricht gelöscht!"
    except Exception as e:
        logger.error(f"Fehler beim Löschen: {e}")
        deleted_msg = "⚠️ Konnte Nachricht nicht löschen."
    
    # Bestätigung
    keywords_preview = ", ".join(keywords[:5])
    if len(keywords) > 5:
        keywords_preview += f" (+{len(keywords)-5} mehr)"
    
    await update.message.reply_text(
        f"{deleted_msg}\n\n"
        f"🧠 **Keywords gelernt:** {added_count}/{len(keywords)}\n"
        f"📝 **Beispiele:** {keywords_preview}\n\n"
        f"Die neuen Keywords werden ab sofort zur Spam-Erkennung verwendet!",
        parse_mode=ParseMode.MARKDOWN
    )


async def notspam_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler für /notspam Command - False Positive markieren"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text(
            "❌ Nur Admins können False Positives markieren.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Prüfe ob Command als Reply verwendet wurde
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "❌ Bitte antworte auf eine Nachricht mit `/notspam` um sie als legitim zu markieren.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Hier könnte man in Zukunft Keywords aus der False-Positive-Nachricht
    # aus der learned_keywords Collection entfernen
    # Für jetzt: Einfach Bestätigung
    
    await update.message.reply_text(
        "✅ Nachricht als legitim markiert!\n\n"
        "ℹ️ **Hinweis:** Um gelernte Keywords zu entfernen, nutze `/keywords remove <keyword>`",
        parse_mode=ParseMode.MARKDOWN
    )


async def keywords_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler für /keywords Command - Gelernte Keywords verwalten"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text(
            "❌ Nur Admins können Keywords verwalten.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    args = context.args
    
    if not args or args[0].lower() == "list":
        # Liste alle gelernten Keywords
        keywords_list = await db.get_learned_keywords_list()
        
        if not keywords_list:
            await update.message.reply_text(
                "📝 Noch keine Keywords gelernt.\n\n"
                "Nutze `/spam` als Antwort auf eine Spam-Nachricht, um Keywords zu lernen!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        message = "🧠 **GELERNTE KEYWORDS**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for entry in keywords_list[:20]:  # Zeige max 20
            keyword = entry.get('keyword', '')
            added_at = entry.get('added_at', datetime.utcnow())
            source = entry.get('source_message', '')[:50]
            
            message += f"• `{keyword}`\n"
            message += f"  📅 {added_at.strftime('%Y-%m-%d %H:%M')}\n"
            if source:
                message += f"  💬 \"{source}...\"\n"
            message += "\n"
        
        if len(keywords_list) > 20:
            message += f"\n... und {len(keywords_list)-20} weitere Keywords"
        
        message += f"\n\n**Gesamt:** {len(keywords_list)} Keywords"
        message += f"\n\n**Verwaltung:**\n`/keywords remove <keyword>` - Keyword entfernen"
        
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    
    elif args[0].lower() == "remove":
        if len(args) < 2:
            await update.message.reply_text(
                "❌ Bitte Keyword angeben: `/keywords remove <keyword>`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        keyword = args[1].lower()
        success = await db.remove_learned_keyword(keyword)
        
        if success:
            await update.message.reply_text(
                f"✅ Keyword `{keyword}` entfernt!",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                f"❌ Keyword `{keyword}` nicht gefunden oder Fehler beim Entfernen.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    else:
        await update.message.reply_text(
            "❌ Unbekannte Aktion. Nutze:\n"
            "`/keywords list` - Alle Keywords anzeigen\n"
            "`/keywords remove <keyword>` - Keyword entfernen",
            parse_mode=ParseMode.MARKDOWN
        )
