# Changelog

Alle wichtigen Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

## [4.0.0] - 2025-01-11

### ✨ Komplett neu entwickelt

#### Hinzugefügt
- **Moderne Architektur** mit python-telegram-bot Library (statt manuellem Polling)
- **Erweiterte Spam-Erkennung**:
  - Über 60 Spam-Keywords in verschiedenen Kategorien
  - Verdächtige URL-Erkennung (20+ gekürzte URL-Dienste)
  - Emoji-Analyse mit konfigurierbaren Schwellenwerten
  - CAPS-Lock-Erkennung
  - Wiederholte Zeichen-Erkennung
  - Neue-User-Überwachung mit separaten Schwellenwerten
  - Scoring-System (0-100) für Spam-Wahrscheinlichkeit
  
- **Whitelist-System**:
  - User können zur Whitelist hinzugefügt werden
  - Persistente Speicherung in MongoDB
  - Verwaltung über Commands (`/whitelist add/remove/list`)
  
- **Verbesserte Commands**:
  - `/start` - Willkommensnachricht mit Bot-Info
  - `/help` - Kontextsensitive Hilfe (unterschiedlich für Admin/User)
  - `/stats` - Detaillierte Statistiken mit Spam-Rate
  - `/config` - Aktuelle Konfiguration anzeigen
  - `/whitelist` - Whitelist-Verwaltung
  
- **MongoDB Integration**:
  - Strukturierte Collections (messages, spam_reports, whitelist, settings)
  - Automatische Index-Erstellung für Performance
  - Robuster Fallback-Modus bei Verbindungsproblemen
  - Persistente Statistiken
  
- **Neue-User-Tracking**:
  - Erkennt neue Gruppenmitglieder
  - Strengere Spam-Regeln für neue User
  - Konfigurierbares Zeitfenster (Standard: 1 Stunde)
  
- **Benachrichtigungssystem**:
  - Automatische Benachrichtigung bei Spam-Löschung
  - Zeigt User, Grund und Score an
  - Auto-Löschung nach 10 Sekunden (kein Spam in der Gruppe)
  
- **API Endpoints**:
  - `GET /` - Bot-Status und Version
  - `GET /health` - Health Check für Railway
  - `GET /stats` - JSON-Statistiken
  
- **Deployment**:
  - Railway-optimiert mit Procfile
  - FastAPI für HTTP-Endpoints
  - Automatisches Deployment via GitHub
  - Health-Check-Endpoint für Monitoring
  
- **Dokumentation**:
  - Ausführliches README.md
  - Schritt-für-Schritt SETUP.md
  - Code-Kommentare
  - .env.example für einfaches Setup

#### Verbessert
- **Code-Struktur**: Modularer Aufbau mit separaten Dateien
  - `main.py` - Bot-Hauptlogik
  - `config.py` - Zentrale Konfiguration
  - `database.py` - MongoDB Handler
  - `spam_detector.py` - Spam-Erkennungs-Engine
  - `handlers.py` - Command Handlers
  
- **Error Handling**: Robuste Fehlerbehandlung in allen Modulen
- **Logging**: Strukturiertes Logging mit verschiedenen Levels
- **Performance**: Asynchrone Verarbeitung mit asyncio
- **Skalierbarkeit**: Vorbereitet für mehrere Gruppen

#### Entfernt
- Manuelles Polling (ersetzt durch python-telegram-bot)
- Hardcodierte Konfiguration (jetzt in config.py)
- Unstrukturierte Datenspeicherung

### 🔧 Technische Details

#### Dependencies
- `python-telegram-bot==20.7` - Moderne Telegram Bot Library
- `motor==3.3.2` - Async MongoDB Driver
- `fastapi==0.109.0` - Web Framework für API
- `uvicorn==0.27.0` - ASGI Server
- `emoji==2.10.0` - Emoji-Analyse
- `httpx==0.26.0` - Async HTTP Client

#### Datenbank Schema

**messages Collection**:
```json
{
  "id": "uuid",
  "message_id": 123,
  "chat_id": -123456,
  "user_id": 123456,
  "username": "user",
  "message": "text",
  "has_media": false,
  "is_new_user": false,
  "is_whitelisted": false,
  "timestamp": "2025-01-11T12:00:00"
}
```

**spam_reports Collection**:
```json
{
  "id": "uuid",
  "message_id": 123,
  "chat_id": -123456,
  "user_id": 123456,
  "username": "spammer",
  "reason": "Spam-Keywords (3): pump, airdrop, casino",
  "score": 75,
  "message_preview": "text preview...",
  "timestamp": "2025-01-11T12:00:00"
}
```

**whitelist Collection**:
```json
{
  "user_id": 123456,
  "username": "trusted_user",
  "added_by": 539342443,
  "added_at": "2025-01-11T12:00:00"
}
```

#### Spam-Scoring-System

Der Bot berechnet einen Spam-Score (0-100):
- Verdächtige URLs: +50 Punkte
- Spam-Keywords: +30 + (5 pro Keyword)
- Zu viele Emojis mit Links: +25 Punkte
- Excessive CAPS: +15 Punkte
- Wiederholte Zeichen: +10 Punkte
- Neuer User mit verdächtigem Inhalt: +20 Punkte
- Media mit Spam-Keywords: +15 Punkte

**Spam-Schwelle**: Score >= 50 → Nachricht wird gelöscht

### 🚀 Migration von v3.5

Wenn du von der alten Version (v3.5) migrierst:

1. **Backup**: Sichere deine MongoDB-Daten
2. **Code ersetzen**: Ersetze alle Dateien mit der neuen Version
3. **Dependencies**: Führe `pip install -r requirements.txt` aus
4. **Umgebungsvariablen**: Prüfe `.env` (sollte kompatibel sein)
5. **Bot-Berechtigungen**: Stelle sicher, dass "Group Privacy" OFF ist
6. **Deployment**: Pushe zu GitHub, Railway deployed automatisch

### 📝 Breaking Changes

- **Command-Syntax geändert**: `/whitelist` nutzt jetzt User IDs statt Usernames
- **API-Response-Format**: JSON-Struktur für `/stats` und `/health` geändert
- **Konfiguration**: Jetzt in `config.py` statt Umgebungsvariablen

---

## [3.5.0] - Vorherige Version

### Features (alte Version)
- Basis Spam-Erkennung
- MongoDB mit Fallback
- FastAPI mit manuellem Polling
- `/stats` und `/help` Commands

### Probleme (alte Version)
- Instabiles Polling
- Keine Whitelist
- Begrenzte Spam-Erkennung
- Keine neue-User-Überwachung
- Hardcodierte Konfiguration

---

**Hinweis**: Version 4.0.0 ist ein komplettes Rewrite und deutlich leistungsfähiger als v3.5!
