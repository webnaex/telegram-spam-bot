"""
Zentrale Konfiguration für den Telegram Anti-Spam Boot
"""
import os
from typing import List

# Telegram Bot Token
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")

# MongoDB Connection
MONGODB_URL = os.getenv("MONGODB_URL", "")

# Admin User IDs (komma-separiert in Railway Variable)
# Beispiel in Railway: ADMIN_USER_IDS=539342443,123456789,987654321
admin_ids_str = os.getenv("ADMIN_USER_IDS", os.getenv("ADMIN_USER_ID", "539342443"))
if ',' in admin_ids_str:
    ADMIN_USER_IDS = [int(uid.strip()) for uid in admin_ids_str.split(',') if uid.strip()]
else:
    ADMIN_USER_IDS = [int(admin_ids_str)]

# Backwards compatibility: ADMIN_USER_ID ist der erste Admin
ADMIN_USER_ID = ADMIN_USER_IDS[0]

# Server Port
PORT = int(os.getenv("PORT", "8000"))

# Spam Detection Keywords
SPAM_KEYWORDS: List[str] = [
    # Crypto/Trading
    'pump', 'pumpfun', 'airdrop', 'claim', 'bonus', 'solana', 'usdt', 'sol',
    'prove', 'tokens', 'allocated', 'eligible', 'wallets', 'distributed',
    'listings', 'upbit', 'bithumb', 'binance', 'tge', 'axiom', 'presale',
    'ico', 'token sale', 'whitelist', 'private sale', 'public sale',
    
    # Gambling/Casino
    'casino', 'bet', 'jackpot', 'slot', 'poker', 'gambling', 'jetluxe', 'vexway',
    'payout', 'withdraw', 'deposit', 'play now', 'player', 'promo code',
    'roulette', 'blackjack', 'sports betting',
    
    # Financial Scams
    'gift', 'free', 'money', 'cash', 'earn', 'income', 'profit', '$600', '$800',
    'investment', 'trading', 'forex', 'crypto', 'bitcoin', 'ethereum',
    'guaranteed', 'risk-free', 'passive income', 'financial freedom',
    
    # Urgency/Pressure
    'limited', 'expire', 'urgent', 'immediate', 'instant', 'quick', 'fast', 'now',
    'hurry', 'act now', 'register', 'sign up', 'join', 'activate', 'redeem',
    'only today', 'last chance', 'don\'t miss', 'limited time', 'ends soon',
    
    # Suspicious Actions
    'visit', 'website', 'click here', 'official', 'welcome', 'honor', 'launch',
    'telegram bot', 'trading bot', 'bot for trading', 'get from', 'can get',
    'dm me', 'contact me', 'private message', 'send me', 'whatsapp',
]

# Suspicious/Shortened URL Domains
SUSPICIOUS_DOMAINS: List[str] = [
    # URL Shorteners
    'clck.ru', 'bit.ly', 'tinyurl.com', 'short.link', 'cutt.ly', 'clk.li',
    't.co', '0.ma', '1.gs', '2.gp', '3.ly', '4.gp', '5.gp', 'is.gd',
    'ow.ly', 'buff.ly', 'su.pr', 'tiny.cc', 'tinyurl.co', 'shorturl.at',
    'rb.gy', 'tny.im', 'v.gd', 'x.co', 'goo.gl',
    
    # Known Scam Domains (kannst du erweitern)
    'free-crypto', 'get-airdrop', 'claim-tokens', 'casino-promo',
]

# Spam Detection Thresholds
SPAM_KEYWORD_THRESHOLD = 3  # Anzahl Keywords für Spam
EMOJI_THRESHOLD = 10  # Anzahl Emojis (mit Links) für Spam
NEW_USER_KEYWORD_THRESHOLD = 2  # Niedrigere Schwelle für neue User

# New User Detection (in Sekunden)
NEW_USER_WINDOW = 3600  # 1 Stunde - User gilt als "neu" wenn vor weniger als 1h beigetreten

# Whitelist Settings
WHITELIST_ENABLED = True
