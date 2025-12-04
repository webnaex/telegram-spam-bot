"""
MongoDB Datenbank-Handler
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import config

logger = logging.getLogger(__name__)


class Database:
    """MongoDB Datenbank Handler mit Fallback"""
    
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        self.available = False
        
        # Fallback Stats (wenn MongoDB nicht verfügbar)
        self.fallback_stats = {
            "spam_blocked_today": 0,
            "messages_today": 0,
            "last_reset": datetime.utcnow().date()
        }
    
    async def connect(self) -> bool:
        """Verbindung zu MongoDB herstellen"""
        if not config.MONGODB_URL:
            logger.warning("⚠️ MONGODB_URL nicht gesetzt - verwende Fallback")
            return False
        
        try:
            logger.info("🔄 Verbinde mit MongoDB...")
            self.client = AsyncIOMotorClient(
                config.MONGODB_URL,
                serverSelectionTimeoutMS=5000
            )
            
            # Test connection
            await self.client.admin.command('ping')
            
            self.db = self.client.telegram_spam_bot
            self.available = True
            
            # Erstelle Indizes
            await self._create_indexes()
            
            logger.info("✅ MongoDB erfolgreich verbunden!")
            return True
            
        except Exception as e:
            logger.error(f"❌ MongoDB Verbindung fehlgeschlagen: {e}")
            self.available = False
            return False
    
    async def _create_indexes(self):
        """Erstelle Datenbank-Indizes für Performance"""
        try:
            if self.db is None:
                return
            
            # Messages Collection
            await self.db.messages.create_index("timestamp")
            await self.db.messages.create_index("chat_id")
            await self.db.messages.create_index("user_id")
            
            # Spam Reports Collection
            await self.db.spam_reports.create_index("timestamp")
            await self.db.spam_reports.create_index("user_id")
            
            # Whitelist Collection
            await self.db.whitelist.create_index("user_id", unique=True)
            
            # CAPTCHA Kicks Collection
            await self.db.captcha_kicks.create_index("timestamp")
            await self.db.captcha_kicks.create_index("user_id")
            
            # Media Blocks Collection
            await self.db.media_blocks.create_index("timestamp")
            await self.db.media_blocks.create_index("user_id")
            
            # Settings Collection
            await self.db.settings.create_index("key", unique=True)
            
            logger.info("✅ Datenbank-Indizes erstellt")
            
        except Exception as e:
            logger.warning(f"⚠️ Index-Erstellung fehlgeschlagen: {e}")
    
    async def close(self):
        """Verbindung schließen"""
        if self.client:
            self.client.close()
            logger.info("MongoDB Verbindung geschlossen")
    
    def _reset_daily_fallback(self):
        """Reset fallback stats wenn neuer Tag"""
        today = datetime.utcnow().date()
        if self.fallback_stats["last_reset"] != today:
            self.fallback_stats["spam_blocked_today"] = 0
            self.fallback_stats["messages_today"] = 0
            self.fallback_stats["last_reset"] = today
    
    async def log_message(self, message_data: Dict[str, Any]) -> bool:
        """Nachricht in Datenbank loggen"""
        try:
            if self.available and self.db is not None:
                await self.db.messages.insert_one(message_data)
                return True
            else:
                # Fallback counter
                self._reset_daily_fallback()
                self.fallback_stats["messages_today"] += 1
                
        except Exception as e:
            logger.error(f"❌ Fehler beim Loggen der Nachricht: {e}")
        
        return False
    
    async def log_spam(self, spam_data: Dict[str, Any]) -> bool:
        """Spam-Report in Datenbank loggen"""
        try:
            if self.available and self.db is not None:
                await self.db.spam_reports.insert_one(spam_data)
                return True
            else:
                # Fallback counter
                self._reset_daily_fallback()
                self.fallback_stats["spam_blocked_today"] += 1
                
        except Exception as e:
            logger.error(f"❌ Fehler beim Loggen des Spam-Reports: {e}")
        
        return False
    
    async def log_captcha_kick(self, kick_data: Dict[str, Any]) -> bool:
        """CAPTCHA-Kick in Datenbank loggen"""
        try:
            if self.available and self.db is not None:
                await self.db.captcha_kicks.insert_one(kick_data)
                return True
        except Exception as e:
            logger.error(f"❌ Fehler beim Loggen des CAPTCHA-Kicks: {e}")
        return False
    
    async def log_media_block(self, block_data: Dict[str, Any]) -> bool:
        """Media-Block in Datenbank loggen"""
        try:
            if self.available and self.db is not None:
                await self.db.media_blocks.insert_one(block_data)
                return True
        except Exception as e:
            logger.error(f"❌ Fehler beim Loggen des Media-Blocks: {e}")
        return False
    
    async def get_today_stats(self) -> Dict[str, Any]:
        """Heutige Statistiken abrufen"""
        try:
            if self.available and self.db is not None:
                today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                
                spam_count = await self.db.spam_reports.count_documents({
                    "timestamp": {"$gte": today}
                })
                
                message_count = await self.db.messages.count_documents({
                    "timestamp": {"$gte": today}
                })
                
                captcha_kicks = await self.db.captcha_kicks.count_documents({
                    "timestamp": {"$gte": today}
                })
                
                media_blocks = await self.db.media_blocks.count_documents({
                    "timestamp": {"$gte": today}
                })
                
                spam_rate = round((spam_count / max(message_count, 1)) * 100, 1)
                
                return {
                    "spam_blocked": spam_count,
                    "captcha_kicks": captcha_kicks,
                    "media_blocks": media_blocks,
                    "messages_total": message_count,
                    "spam_rate": spam_rate,
                    "source": "MongoDB"
                }
        
        except Exception as e:
            logger.error(f"❌ Fehler beim Abrufen der Stats: {e}")
        
        # Fallback
        self._reset_daily_fallback()
        spam_rate = round(
            (self.fallback_stats["spam_blocked_today"] / 
             max(self.fallback_stats["messages_today"], 1)) * 100, 1
        )
        
        return {
            "spam_blocked": self.fallback_stats["spam_blocked_today"],
            "messages_total": self.fallback_stats["messages_today"],
            "spam_rate": spam_rate,
            "source": "Memory-Fallback"
        }
    
    async def add_to_whitelist(self, user_id: int, username: str, added_by: int) -> bool:
        """User zur Whitelist hinzufügen"""
        try:
            if self.available and self.db is not None:
                await self.db.whitelist.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "user_id": user_id,
                            "username": username,
                            "added_by": added_by,
                            "added_at": datetime.utcnow()
                        }
                    },
                    upsert=True
                )
                logger.info(f"✅ User {username} ({user_id}) zur Whitelist hinzugefügt")
                return True
                
        except Exception as e:
            logger.error(f"❌ Fehler beim Hinzufügen zur Whitelist: {e}")
        
        return False
    
    async def remove_from_whitelist(self, user_id: int) -> bool:
        """User von Whitelist entfernen"""
        try:
            if self.available and self.db is not None:
                result = await self.db.whitelist.delete_one({"user_id": user_id})
                if result.deleted_count > 0:
                    logger.info(f"✅ User {user_id} von Whitelist entfernt")
                    return True
                
        except Exception as e:
            logger.error(f"❌ Fehler beim Entfernen von Whitelist: {e}")
        
        return False
    
    async def is_whitelisted(self, user_id: int) -> bool:
        """Prüfen ob User auf Whitelist ist"""
        try:
            if self.available and self.db is not None:
                result = await self.db.whitelist.find_one({"user_id": user_id})
                return result is not None
                
        except Exception as e:
            logger.error(f"❌ Fehler beim Prüfen der Whitelist: {e}")
        
        return False
    
    async def get_whitelist(self) -> List[Dict[str, Any]]:
        """Alle Whitelist-Einträge abrufen"""
        try:
            if self.available and self.db is not None:
                cursor = self.db.whitelist.find().sort("added_at", -1)
                return await cursor.to_list(length=100)
                
        except Exception as e:
            logger.error(f"❌ Fehler beim Abrufen der Whitelist: {e}")
        
        return []
    
    async def get_setting(self, key: str, default: Any = None) -> Any:
        """Einstellung aus DB abrufen"""
        try:
            if self.available and self.db is not None:
                result = await self.db.settings.find_one({"key": key})
                if result:
                    return result.get("value", default)
                
        except Exception as e:
            logger.error(f"❌ Fehler beim Abrufen der Einstellung: {e}")
        
        return default
    
    async def set_setting(self, key: str, value: Any) -> bool:
        """Einstellung in DB speichern"""
        try:
            if self.available and self.db is not None:
                await self.db.settings.update_one(
                    {"key": key},
                    {
                        "$set": {
                            "key": key,
                            "value": value,
                            "updated_at": datetime.utcnow()
                        }
                    },
                    upsert=True
                )
                return True
                
        except Exception as e:
            logger.error(f"❌ Fehler beim Speichern der Einstellung: {e}")
        
        return False
    
    # ===== LEARNED KEYWORDS =====
    
    async def add_learned_keyword(self, keyword: str, category: str, added_by: int, source_message: str = "") -> bool:
        """Neues gelerntes Keyword hinzufügen"""
        try:
            if self.available and self.db is not None:
                # Prüfe ob Keyword schon existiert
                existing = await self.db.learned_keywords.find_one({"keyword": keyword.lower()})
                if existing:
                    logger.info(f"ℹ️ Keyword '{keyword}' existiert bereits")
                    return False
                
                await self.db.learned_keywords.insert_one({
                    "keyword": keyword.lower(),
                    "category": category,
                    "added_by": added_by,
                    "added_at": datetime.utcnow(),
                    "source_message": source_message[:500] if source_message else "",
                    "confidence": 0.8,
                    "active": True
                })
                logger.info(f"✅ Keyword '{keyword}' gelernt!")
                return True
                
        except Exception as e:
            logger.error(f"❌ Fehler beim Hinzufügen von Keyword: {e}")
        
        return False
    
    async def get_learned_keywords(self) -> List[str]:
        """Alle aktiven gelernten Keywords abrufen"""
        try:
            if self.available and self.db is not None:
                cursor = self.db.learned_keywords.find({"active": True})
                keywords = []
                async for doc in cursor:
                    keywords.append(doc["keyword"])
                return keywords
                
        except Exception as e:
            logger.error(f"❌ Fehler beim Abrufen von Keywords: {e}")
        
        return []
    
    async def remove_learned_keyword(self, keyword: str) -> bool:
        """Gelerntes Keyword deaktivieren"""
        try:
            if self.available and self.db is not None:
                result = await self.db.learned_keywords.update_one(
                    {"keyword": keyword.lower()},
                    {"$set": {"active": False, "deactivated_at": datetime.utcnow()}}
                )
                return result.modified_count > 0
                
        except Exception as e:
            logger.error(f"❌ Fehler beim Entfernen von Keyword: {e}")
        
        return False
    
    async def get_learned_keywords_list(self) -> List[Dict[str, Any]]:
        """Alle gelernten Keywords mit Details abrufen"""
        try:
            if self.available and self.db is not None:
                cursor = self.db.learned_keywords.find({"active": True}).sort("added_at", -1)
                return await cursor.to_list(length=100)
                
        except Exception as e:
            logger.error(f"❌ Fehler beim Abrufen von Keywords-Liste: {e}")
        
        return []


# Globale Datenbank-Instanz
db = Database()
