# 🤖 Telegram Anti-Spam Bot

Ein moderner, leistungsstarker Telegram-Bot zum Schutz von Gruppen vor Spam-Nachrichten.

## ✨ Features Test

### 🛡️ Spam-Erkennung
- **Keyword-basierte Filterung**: Erkennt über 60 Spam-Keywords (Crypto, Casino, Scams)
- **URL-Überwachung**: Blockiert verdächtige und gekürzte URLs
- **Emoji-Analyse**: Erkennt übermäßige Emoji-Nutzung mit Links
- **Neue-User-Überwachung**: Strengere Regeln für neue Gruppenmitglieder
- **CAPS-Lock-Erkennung**: Blockiert übermäßige Großbuchstaben
- **Wiederholte Zeichen**: Erkennt Spam-Muster wie "aaaaa" oder "!!!!!"

### 📊 Statistiken & Monitoring
- Tägliche Spam-Statistiken
- Message-Tracking
- Spam-Rate-Berechnung
- MongoDB-Integration mit Memory-Fallback

### 👥 Whitelist-System
- Vertrauenswürdige User werden nie blockiert
- Einfache Verwaltung über Commands
- Persistente Speicherung in MongoDB

### ⚙️ Konfiguration
- Flexible Schwellenwerte
- Anpassbare Spam-Keywords
- Admin-basierte Konfiguration

## 🚀 Installation & Deployment

### Voraussetzungen

1. **Telegram Bot Token**
   - Erstelle einen Bot über [@BotFather](https://t.me/BotFather)
   - Verwende `/newbot` und folge den Anweisungen
   - Speichere den erhaltenen Token

2. **MongoDB Datenbank**
   - Erstelle eine MongoDB-Instanz auf [Railway](https://railway.app)
   - Kopiere die Connection String

3. **Deine User ID**
   - Sende eine Nachricht an [@userinfobot](https://t.me/userinfobot)
   - Notiere deine User ID

### Railway Deployment

#### 1. GitHub Repository erstellen

```bash
# Initialisiere Git Repository
git init
git add .
git commit -m "Initial commit: Telegram Anti-Spam Bot"

# Erstelle GitHub Repository und pushe
git remote add origin https://github.com/DEIN_USERNAME/telegram-spam-bot.git
git branch -M main
git push -u origin main
```

#### 2. Railway Projekt erstellen

1. Gehe zu [Railway](https://railway.app)
2. Klicke auf "New Project"
3. Wähle "Deploy from GitHub repo"
4. Wähle dein Repository aus

#### 3. MongoDB hinzufügen

1. Im Railway Dashboard: "New" → "Database" → "Add MongoDB"
2. Warte bis MongoDB deployed ist
3. Kopiere die Connection String aus den MongoDB-Variablen

#### 4. Umgebungsvariablen setzen

Gehe zu deinem Service → "Variables" und füge hinzu:

```
TELEGRAM_TOKEN=dein_bot_token_hier
MONGODB_URL=mongodb://mongo:password@host:port
ADMIN_USER_ID=deine_user_id
PORT=8000
```

**Wichtig**: Die `MONGODB_URL` findest du in den MongoDB-Service-Variablen als `MONGO_URL` oder `DATABASE_URL`.

#### 5. Bot-Berechtigungen in Telegram-Gruppe

1. Füge deinen Bot zur Gruppe hinzu
2. Mache ihn zum **Administrator** mit folgenden Rechten:
   - ✅ Delete messages
   - ✅ Ban users (optional, für zukünftige Features)
3. **Wichtig**: Gehe zu Bot-Einstellungen bei @BotFather
   - Sende `/mybots`
   - Wähle deinen Bot
   - Gehe zu "Bot Settings" → "Group Privacy"
   - **Deaktiviere** "Group Privacy" (damit Bot alle Nachrichten sehen kann)

#### 6. Deployment starten

Railway deployed automatisch nach jedem Push zu GitHub!

```bash
# Änderungen pushen
git add .
git commit -m "Update bot"
git push
```

## 📋 Bot Commands

### Für alle User
- `/start` - Bot starten und Willkommensnachricht anzeigen
- `/help` - Hilfe und verfügbare Commands anzeigen

### Nur für Admin
- `/stats` - Heutige Spam-Statistiken anzeigen
- `/config` - Aktuelle Bot-Konfiguration anzeigen
- `/whitelist list` - Alle Whitelist-User anzeigen
- `/whitelist add <user_id>` - User zur Whitelist hinzufügen
- `/whitelist remove <user_id>` - User von Whitelist entfernen

### Beispiele

```
/stats
→ Zeigt Spam-Statistiken des heutigen Tages

/whitelist add 123456789
→ Fügt User mit ID 123456789 zur Whitelist hinzu

/whitelist list
→ Zeigt alle User auf der Whitelist
```

## ⚙️ Konfiguration

Die Konfiguration erfolgt in der `config.py` Datei:

### Spam-Schwellenwerte anpassen

```python
# Anzahl Keywords für Spam-Erkennung
SPAM_KEYWORD_THRESHOLD = 3

# Anzahl Emojis (mit Links) für Spam
EMOJI_THRESHOLD = 10

# Niedrigere Schwelle für neue User
NEW_USER_KEYWORD_THRESHOLD = 2

# Zeitfenster für "neue User" (in Sekunden)
NEW_USER_WINDOW = 3600  # 1 Stunde
```

### Spam-Keywords erweitern

```python
SPAM_KEYWORDS: List[str] = [
    'pump', 'airdrop', 'casino', 'bet',
    # Füge hier weitere Keywords hinzu
    'dein_keyword',
]
```

### Verdächtige Domains hinzufügen

```python
SUSPICIOUS_DOMAINS: List[str] = [
    'bit.ly', 'tinyurl.com',
    # Füge hier weitere Domains hinzu
    'deine-domain.com',
]
```

## 🏗️ Projektstruktur

```
telegram-spam-bot/
├── main.py              # Hauptdatei mit Bot-Logik
├── config.py            # Zentrale Konfiguration
├── database.py          # MongoDB Handler
├── spam_detector.py     # Spam-Erkennungs-Engine
├── handlers.py          # Command Handlers
├── requirements.txt     # Python Dependencies
├── Procfile            # Railway Deployment Config
├── runtime.txt         # Python Version
├── .env.example        # Beispiel für Umgebungsvariablen
├── .gitignore          # Git Ignore Datei
└── README.md           # Diese Datei
```

## 🔧 Lokale Entwicklung

### Setup

```bash
# Repository klonen
git clone https://github.com/DEIN_USERNAME/telegram-spam-bot.git
cd telegram-spam-bot

# Virtual Environment erstellen
python -m venv venv
source venv/bin/activate  # Linux/Mac
# oder
venv\Scripts\activate  # Windows

# Dependencies installieren
pip install -r requirements.txt

# .env Datei erstellen
cp .env.example .env
# Bearbeite .env und füge deine Credentials ein
```

### Bot lokal starten

```bash
python main.py
```

Der Bot läuft nun lokal und ist über `http://localhost:8000` erreichbar.

## 📊 API Endpoints

Der Bot stellt folgende HTTP-Endpoints bereit:

- `GET /` - Bot-Status und Version
- `GET /health` - Health Check für Railway
- `GET /stats` - Aktuelle Statistiken (JSON)

### Beispiel

```bash
curl https://dein-bot.railway.app/health
```

Response:
```json
{
  "status": "healthy",
  "bot_running": true,
  "mongodb_available": true,
  "stats": {
    "spam_blocked": 42,
    "messages_total": 1337,
    "spam_rate": 3.1,
    "source": "MongoDB"
  },
  "timestamp": "2025-01-11T12:00:00"
}
```

## 🛠️ Troubleshooting

### Bot antwortet nicht auf Nachrichten

1. **Prüfe Bot-Berechtigungen**:
   - Bot muss Admin in der Gruppe sein
   - "Delete messages" Berechtigung muss aktiviert sein

2. **Prüfe Group Privacy**:
   - Bei @BotFather: Bot Settings → Group Privacy → **OFF**
   - Sonst sieht der Bot keine Nachrichten!

3. **Prüfe Logs in Railway**:
   - Railway Dashboard → Dein Service → "Deployments" → Logs ansehen

### MongoDB Verbindung fehlgeschlagen

1. **Prüfe MONGODB_URL**:
   - Muss vollständige Connection String sein
   - Format: `mongodb://username:password@host:port/database`

2. **Prüfe MongoDB Service**:
   - Ist MongoDB in Railway gestartet?
   - Sind beide Services im selben Projekt?

3. **Fallback-Modus**:
   - Bot läuft auch ohne MongoDB (Memory-Fallback)
   - Statistiken gehen bei Restart verloren

### Bot löscht keine Spam-Nachrichten

1. **Admin-Rechte prüfen**: Bot braucht "Delete messages"
2. **Logs prüfen**: Wird Spam erkannt? (Score >= 50)
3. **Schwellenwerte anpassen**: In `config.py` Werte reduzieren

## 📝 Lizenz

Dieses Projekt ist Open Source und frei verwendbar.

## 🤝 Support

Bei Fragen oder Problemen:
1. Prüfe die Logs in Railway
2. Prüfe die Bot-Berechtigungen in Telegram
3. Erstelle ein Issue auf GitHub

## 🔄 Updates

Um den Bot zu aktualisieren:

```bash
git pull origin main
git add .
git commit -m "Update"
git push
```

Railway deployed automatisch die neueste Version!

---

**Viel Erfolg mit deinem Spam-Bot! 🚀**
