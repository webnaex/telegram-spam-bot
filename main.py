Perfekt! 🔧 Jetzt habe ich **alle MongoDB-Fehler** im Code korrigiert!

## ✅ **Das Problem war:**
- MongoDB Motor Objekte können nicht mit `if not mongodb:` getestet werden
- **Lösung:** Alle `if not mongodb:` → `if mongodb is None:` geändert

## 🚀 **Aktualisierte `main.py` für Railway:**
Action: file_editor view /app/main.py --view-range-start 1 --view-range-end 50
Observation: /app/main.py:
1|# Railway Telegram Anti-Spam Bot mit vollständigen Statistiken
2|# Version 3.0 - Mit allen Statistik-Commands und optimiert für Railway.app
3|
4|from fastapi import FastAPI, HTTPException, Request
5|from pydantic import BaseModel
6|from typing import Optional, List, Dict, Any
7|import os
8|import uuid
9|from datetime import datetime, timedelta
10|import re
11|import logging
12|import asyncio
13|import httpx
14|import emoji
15|from langdetect import detect, LangDetectException
16|from motor.motor_asyncio import AsyncIOMotorClient
17|
18|# Configure logging
19|logging.basicConfig(level=logging.INFO)
20|logger = logging.getLogger(__name__)
21|
22|app = FastAPI(title="Telegram Anti-Spam Bot Railway", version="3.0.0")
23|
24|# Global variables
25|mongodb = None
26|
27|# SPAM DETECTION CONFIGURATION
28|SPAM_KEYWORDS = [
29|    'pump', 'pumpfun', 'airdrop', 'claim', 'bonus', 'solana', 'usdt', 'sol',
30|    'prove', 'tokens', 'allocated', 'eligible', 'wallets', 'distributed',
31|    'listings', 'upbit', 'bithumb', 'binance', 'tge', 'axiom',
32|    'casino', 'bet', 'jackpot', 'slot', 'poker', 'gambling', 'jetluxe', 'vexway',
33|    'payout', 'withdraw', 'deposit', 'play now', 'player', 'promo code',
34|    'gift', 'free', 'money', 'cash', 'earn', 'income', 'profit', '$600', '$800',
35|    'investment', 'trading', 'forex', 'crypto', 'bitcoin',
36|    'limited', 'expire', 'urgent', 'immediate', 'instant', 'quick', 'fast', 'now',
37|    'hurry', 'act now', 'register', 'sign up', 'join', 'activate', 'redeem',
38|    'visit', 'website', 'click here', 'official', 'welcome', 'honor', 'launch',
39|    'telegram bot', 'trading bot', 'bot for trading', 'get from', 'can get'
40|]
41|
42|SUSPICIOUS_DOMAINS = [
43|    'clck.ru', 'bit.ly', 'tinyurl.com', 'short.link', 'cutt.ly', 'clk.li',
44|    't.co', '0.ma', '1.gs', '2.gp', '3.ly', '4.gp', '5.gp', 'is.gd',
45|    'ow.ly', 'buff.ly', 'su.pr', 'tiny.cc', 'tinyurl.co', 'shorturl.at',
46|    'rb.gy', 'v.gd', 'short.gy', 'tiny.one', 'link.ly', 'go.link', 'u.to'
47|]
48|
49|# ADMIN USER IDs
50|def get_admin_user_ids():

