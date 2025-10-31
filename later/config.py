"""
Pancake MVP - Configuration Management
"""
import os
from datetime import timedelta

class Config:
    """Base configuration"""
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'change-me-in-production')
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://pancake_user:pancake_pass@localhost:5432/pancake_db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'change-me-in-production')
    JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # Asset Registry Integration
    ASSET_REGISTRY_URL = os.getenv('ASSET_REGISTRY_URL', 'http://localhost:4000')
    ASSET_REGISTRY_TIMEOUT = int(os.getenv('ASSET_REGISTRY_TIMEOUT', '10'))
    
    # User Registry Integration
    USER_REGISTRY_URL = os.getenv('USER_REGISTRY_URL', 'http://localhost:5000')
    USER_REGISTRY_TIMEOUT = int(os.getenv('USER_REGISTRY_TIMEOUT', '10'))
    
    # Google Notifications (Stubbed for MVP)
    GOOGLE_NOTIFY_ENABLED = os.getenv('GOOGLE_NOTIFY_ENABLED', 'false').lower() == 'true'
    GOOGLE_FCM_CREDENTIALS_PATH = os.getenv('GOOGLE_FCM_CREDENTIALS_PATH', './credentials/fcm-credentials.json')
    GMAIL_API_CREDENTIALS_PATH = os.getenv('GMAIL_API_CREDENTIALS_PATH', './credentials/gmail-credentials.json')
    
    # Packet Limits
    MAX_PACKET_BODY_SIZE_KB = int(os.getenv('MAX_PACKET_BODY_SIZE_KB', '512'))
    CHAT_MESSAGE_MAX_CHARS = int(os.getenv('CHAT_MESSAGE_MAX_CHARS', '250'))
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # CORS
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*')


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'postgresql://pancake_user:pancake_pass@localhost:5432/pancake_test_db'


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

