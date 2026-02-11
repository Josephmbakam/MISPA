import os
from datetime import timedelta

class Config:
    # Clé secrète
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'mispa-secret-key-2024-mbajo7'
    
    # Base de données
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(BASE_DIR, "database", "mispa.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # Traduction
    SUPPORTED_LANGUAGES = {
        'en': 'English',
        'fr': 'Français',
        'es': 'Español',
        'zh': '中文',
        'hi': 'हिन्दी',
        'ar': 'العربية',
        'pt': 'Português',
        'bn': 'বাংলা',
        'ru': 'Русский',
        'ja': '日本語',
        'de': 'Deutsch',
        'ko': '한국어',
        'it': 'Italiano',
        'tr': 'Türkçe',
        'vi': 'Tiếng Việt',
        'th': 'ไทย',
        'pl': 'Polski',
        'nl': 'Nederlands',
        'sv': 'Svenska',
        'fa': 'فارسی'
    }
    
    # Messages par défaut
    DEFAULT_MESSAGES = {
        'welcome': "Bienvenue sur MISPA - Messagerie Sans Frontières",
        'verse': "Car Dieu a tant aimé le monde qu'il a donné son Fils unique, afin que quiconque croit en lui ne périsse point, mais qu'il ait la vie éternelle. - Jean 3:16"
    }