"""
Spam Detection Engine
"""
import re
import logging
from typing import List, Tuple, Optional
from datetime import datetime, timedelta
import emoji as emoji_lib
import config

logger = logging.getLogger(__name__)


class SpamDetector:
    """Spam-Erkennungs-Engine"""
    
    def __init__(self):
        self.spam_keywords = config.SPAM_KEYWORDS
        self.suspicious_domains = config.SUSPICIOUS_DOMAINS
        self.learned_keywords = []  # Dynamisch aus DB geladen
    
    def set_learned_keywords(self, keywords: List[str]):
        """Setze gelernte Keywords aus DB"""
        self.learned_keywords = [k.lower() for k in keywords]
        logger.info(f"📚 {len(self.learned_keywords)} gelernte Keywords geladen")
    
    def has_links(self, text: str) -> bool:
        """Prüft ob Text Links enthält"""
        if not text:
            return False
        
        # URL Pattern
        url_pattern = re.compile(
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
            r'|(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}'
        )
        
        return bool(url_pattern.search(text))
    
    def has_suspicious_links(self, text: str) -> Tuple[bool, List[str]]:
        """Prüft ob Text verdächtige/gekürzte URLs enthält"""
        if not text:
            return False, []
        
        text_lower = text.lower()
        found_domains = []
        
        for domain in self.suspicious_domains:
            if domain in text_lower:
                found_domains.append(domain)
        
        return len(found_domains) > 0, found_domains
    
    def count_emojis(self, text: str) -> int:
        """Zählt Emojis im Text"""
        if not text:
            return 0
        
        try:
            # Nutze emoji library
            emoji_count = emoji_lib.emoji_count(text)
            return emoji_count
        except Exception as e:
            logger.warning(f"Emoji counting error: {e}")
            return 0
    
    def contains_spam_keywords(self, text: str) -> List[str]:
        """Findet Spam-Keywords im Text (inkl. gelernte Keywords)"""
        if not text:
            return []
        
        text_lower = text.lower()
        found_keywords = []
        
        # Prüfe statische Keywords aus config.py
        for keyword in self.spam_keywords:
            if keyword in text_lower:
                found_keywords.append(keyword)
        
        # Prüfe dynamisch gelernte Keywords aus DB
        for keyword in self.learned_keywords:
            if keyword in text_lower:
                found_keywords.append(f"{keyword}*")  # * = gelernt
        
        return found_keywords
    
    def has_excessive_caps(self, text: str, threshold: float = 0.6) -> bool:
        """Prüft ob zu viele Großbuchstaben (CAPS LOCK)"""
        if not text or len(text) < 10:
            return False
        
        # Zähle Buchstaben
        letters = [c for c in text if c.isalpha()]
        if len(letters) < 5:
            return False
        
        caps_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        return caps_ratio > threshold
    
    def has_repeated_chars(self, text: str, threshold: int = 5) -> bool:
        """Prüft auf wiederholte Zeichen (z.B. 'aaaaa', '!!!!!')"""
        if not text:
            return False
        
        # Pattern für wiederholte Zeichen
        pattern = re.compile(r'(.)\1{' + str(threshold - 1) + ',}')
        return bool(pattern.search(text))
    
    def detect_spam(
        self, 
        text: str, 
        has_media: bool = False,
        is_new_user: bool = False,
        is_whitelisted: bool = False
    ) -> Tuple[bool, str, int]:
        """
        Hauptfunktion zur Spam-Erkennung
        
        Returns:
            (is_spam, reason, confidence_score)
        """
        
        # Whitelist-User sind immer sicher
        if is_whitelisted:
            return False, "", 0
        
        if not text:
            return False, "", 0
        
        spam_score = 0
        reasons = []
        
        # 1. Verdächtige Links (HOHE PRIORITÄT)
        has_suspicious, domains = self.has_suspicious_links(text)
        if has_suspicious:
            spam_score += 50
            reasons.append(f"Verdächtige URL: {', '.join(domains[:2])}")
        
        # 2. Spam Keywords
        spam_words = self.contains_spam_keywords(text)
        
        # NEUE REGEL: Media + 2 Keywords = Spam (strenger!)
        if has_media:
            keyword_threshold = 2  # Nur 2 Keywords bei Media!
        elif is_new_user:
            keyword_threshold = config.NEW_USER_KEYWORD_THRESHOLD
        else:
            keyword_threshold = config.SPAM_KEYWORD_THRESHOLD
        
        if len(spam_words) >= keyword_threshold:
            spam_score += 30 + (len(spam_words) * 5)
            reasons.append(f"Spam-Keywords ({len(spam_words)}): {', '.join(spam_words[:3])}")
        
        # 3. Zu viele Emojis mit Links
        emoji_count = self.count_emojis(text)
        has_links_bool = self.has_links(text)
        
        if emoji_count > config.EMOJI_THRESHOLD and has_links_bool:
            spam_score += 25
            reasons.append(f"Zu viele Emojis ({emoji_count}) mit Links")
        
        # 4. Excessive CAPS
        if self.has_excessive_caps(text):
            spam_score += 15
            reasons.append("Übermäßige Großbuchstaben")
        
        # 5. Wiederholte Zeichen
        if self.has_repeated_chars(text):
            spam_score += 10
            reasons.append("Wiederholte Zeichen")
        
        # 6. Neue User sind verdächtiger
        if is_new_user and (spam_words or has_links_bool):
            spam_score += 20
            reasons.append("Neuer User mit verdächtigem Inhalt")
        
        # 7. Media mit Spam-Keywords (extra Punkte!)
        if has_media and len(spam_words) >= 2:
            spam_score += 20
            reasons.append("Media mit Spam-Keywords")
        
        # Entscheidung: Spam wenn Score >= 50
        is_spam = spam_score >= 50
        reason = " | ".join(reasons) if reasons else ""
        
        if is_spam:
            logger.info(f"🚫 SPAM erkannt (Score: {spam_score}): {reason}")
        
        return is_spam, reason, spam_score


# Globale Spam-Detector Instanz
spam_detector = SpamDetector()
