# 🚀 Schritt-für-Schritt Setup Anleitung

Diese Anleitung führt dich durch den kompletten Setup-Prozess für deinen Telegram Anti-Spam Bot.

## 📋 Checkliste

Bevor du startest, benötigst du:
- [ ] GitHub Account
- [ ] Railway Account (kostenlos)
- [ ] Telegram Account

## Schritt 1: Telegram Bot erstellen

### 1.1 Bot bei BotFather erstellen

1. Öffne Telegram und suche nach **@BotFather**
2. Starte einen Chat mit `/start`
3. Sende `/newbot`
4. Gib einen Namen für deinen Bot ein (z.B. "Mein Spam Schutz Bot")
5. Gib einen Username ein (muss auf `bot` enden, z.B. `mein_spam_bot`)
6. **Speichere den Token** - du bekommst eine Nachricht wie:
   ```
   Use this token to access the HTTP API:
   1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   ```

### 1.2 Group Privacy deaktivieren

**WICHTIG**: Damit der Bot alle Nachrichten sehen kann!

1. Bei @BotFather: Sende `/mybots`
2. Wähle deinen Bot aus
3. Klicke auf "Bot Settings"
4. Klicke auf "Group Privacy"
5. Klicke auf "Turn off" (muss **disabled** sein!)

### 1.3 Deine User ID herausfinden

1. Suche nach **@userinfobot** in Telegram
2. Starte einen Chat mit `/start`
3. **Speichere deine User ID** (z.B. `539342443`)

## Schritt 2: GitHub Repository erstellen

### 2.1 Repository auf GitHub erstellen

1. Gehe zu [GitHub](https://github.com)
2. Klicke auf "New repository"
3. Name: `telegram-spam-bot` (oder beliebig)
4. Sichtbarkeit: **Private** (empfohlen) oder Public
5. **NICHT** "Initialize with README" ankreuzen
6. Klicke "Create repository"

### 2.2 Code hochladen

Öffne ein Terminal/Command Prompt im Bot-Ordner:

```bash
# Git initialisieren
git init

# Alle Dateien hinzufügen
git add .

# Ersten Commit erstellen
git commit -m "Initial commit: Telegram Anti-Spam Bot"

# Remote hinzufügen (ersetze USERNAME und REPO)
git remote add origin https://github.com/DEIN_USERNAME/telegram-spam-bot.git

# Branch umbenennen
git branch -M main

# Code hochladen
git push -u origin main
```

**Tipp**: Wenn du nach Username/Password gefragt wirst, nutze einen [Personal Access Token](https://github.com/settings/tokens) als Passwort.

## Schritt 3: Railway Setup

### 3.1 Railway Account erstellen

1. Gehe zu [Railway](https://railway.app)
2. Klicke "Login" und nutze GitHub zum Anmelden
3. Bestätige die Berechtigungen

### 3.2 MongoDB Datenbank erstellen

1. Im Railway Dashboard: Klicke "New Project"
2. Klicke "Provision MongoDB"
3. Warte bis MongoDB deployed ist (ca. 1-2 Minuten)
4. Klicke auf die MongoDB-Karte
5. Gehe zum Tab "Variables"
6. **Kopiere** den Wert von `MONGO_URL` (sieht aus wie: `mongodb://mongo:password@...`)

### 3.3 Bot Service hinzufügen

1. Im gleichen Projekt: Klicke "+ New"
2. Wähle "GitHub Repo"
3. Wähle dein `telegram-spam-bot` Repository
4. Railway startet automatisch das Deployment

### 3.4 Umgebungsvariablen setzen

1. Klicke auf die Bot-Service-Karte (nicht MongoDB!)
2. Gehe zum Tab "Variables"
3. Klicke "+ New Variable" und füge hinzu:

```
TELEGRAM_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
MONGODB_URL=mongodb://mongo:password@mongodb.railway.internal:27017
ADMIN_USER_ID=539342443
PORT=8000
```

**Wichtig**: 
- Ersetze `TELEGRAM_TOKEN` mit deinem Bot-Token von BotFather
- Ersetze `MONGODB_URL` mit dem kopierten `MONGO_URL` von MongoDB
- Ersetze `ADMIN_USER_ID` mit deiner User ID
- `PORT` bleibt `8000`

4. Klicke "Deploy" (falls nicht automatisch neu deployed wird)

### 3.5 Deployment überprüfen

1. Gehe zum Tab "Deployments"
2. Warte bis Status "Success" ist (ca. 2-3 Minuten)
3. Klicke auf "View Logs" um zu prüfen ob alles läuft
4. Du solltest sehen: `✅ Bot läuft!`

## Schritt 4: Bot zur Telegram-Gruppe hinzufügen

### 4.1 Bot zur Gruppe hinzufügen

1. Öffne deine Telegram-Gruppe
2. Klicke auf den Gruppennamen (oben)
3. Klicke "Add Members"
4. Suche deinen Bot (Username von Schritt 1.1)
5. Füge ihn hinzu

### 4.2 Bot zum Admin machen

**WICHTIG**: Ohne Admin-Rechte kann der Bot keine Nachrichten löschen!

1. In der Gruppe: Klicke auf den Gruppennamen
2. Klicke "Administrators"
3. Klicke "Add Administrator"
4. Wähle deinen Bot aus
5. Aktiviere folgende Rechte:
   - ✅ **Delete messages** (WICHTIG!)
   - ✅ Ban users (optional)
   - ❌ Alle anderen können deaktiviert bleiben
6. Klicke "Done"

## Schritt 5: Bot testen

### 5.1 Grundfunktionen testen

Sende in der Gruppe:

```
/start
```

Der Bot sollte antworten mit einer Willkommensnachricht.

```
/help
```

Der Bot zeigt alle verfügbaren Commands.

```
/stats
```

Der Bot zeigt die heutigen Statistiken (nur für Admin).

### 5.2 Spam-Erkennung testen

Sende eine Test-Nachricht mit Spam-Keywords:

```
🚀 Free airdrop! Claim your tokens now! 💰
Visit: bit.ly/scam
```

Der Bot sollte:
1. Die Nachricht sofort löschen
2. Eine Benachrichtigung senden (verschwindet nach 10 Sekunden)

### 5.3 Whitelist testen

Füge dich selbst zur Whitelist hinzu:

```
/whitelist add DEINE_USER_ID
```

Jetzt kannst du Spam-Keywords senden ohne blockiert zu werden!

Entferne dich wieder:

```
/whitelist remove DEINE_USER_ID
```

## 🎉 Fertig!

Dein Bot läuft jetzt und schützt deine Gruppe vor Spam!

## 📊 Monitoring

### Railway Logs ansehen

1. Railway Dashboard → Dein Bot Service
2. Tab "Deployments" → Neuestes Deployment
3. Klicke "View Logs"

Hier siehst du:
- Gestartete Nachrichten
- Gelöschte Spam-Nachrichten
- Fehler (falls vorhanden)

### Health Check

Öffne im Browser:

```
https://dein-bot.railway.app/health
```

Du solltest sehen:
```json
{
  "status": "healthy",
  "bot_running": true,
  "mongodb_available": true,
  ...
}
```

## 🔧 Häufige Probleme

### Problem: Bot antwortet nicht

**Lösung**:
1. Prüfe ob Bot in Railway läuft (Logs ansehen)
2. Prüfe ob "Group Privacy" bei @BotFather **OFF** ist
3. Prüfe ob Bot Admin in der Gruppe ist

### Problem: Bot löscht keine Spam-Nachrichten

**Lösung**:
1. Prüfe ob Bot "Delete messages" Berechtigung hat
2. Prüfe Logs: Wird Spam erkannt?
3. Schwellenwerte in `config.py` anpassen (siehe README.md)

### Problem: MongoDB Verbindung fehlgeschlagen

**Lösung**:
1. Prüfe ob `MONGODB_URL` korrekt gesetzt ist
2. Nutze den `MONGO_URL` Wert aus MongoDB-Service
3. Bot läuft auch ohne MongoDB (Memory-Fallback)

### Problem: Railway Deployment failed

**Lösung**:
1. Prüfe Logs in Railway
2. Prüfe ob alle Dateien in GitHub sind
3. Prüfe ob `requirements.txt` korrekt ist

## 🔄 Updates durchführen

Wenn du den Code änderst:

```bash
# Änderungen committen
git add .
git commit -m "Beschreibung der Änderung"

# Zu GitHub pushen
git push

# Railway deployed automatisch!
```

## 📞 Support

Bei Problemen:
1. Prüfe die Logs in Railway
2. Prüfe diese Anleitung nochmal
3. Prüfe das README.md für Details

---

**Viel Erfolg! 🚀**
