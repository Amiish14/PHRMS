import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'procam-phrms-2026-secure-key-change-in-prod')
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
    MYSQL_DB = os.environ.get('MYSQL_DB', 'proconnect')
    MYSQL_CURSORCLASS = 'DictCursor'
    ITEMS_PER_PAGE = 50
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB upload limit
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
