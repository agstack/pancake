"""
Pancake Flask Application Factory
"""
import os
import logging
from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()


def create_app(config_name=None):
    """
    Application factory pattern
    """
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    
    # Load configuration
    from config import config
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app, origins=app.config['CORS_ORIGINS'])
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, app.config['LOG_LEVEL']),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Register blueprints
    from app.routes import intake_bp, packets_bp, shares_bp, chat_bp, graph_bp, health_bp
    app.register_blueprint(health_bp)
    app.register_blueprint(intake_bp, url_prefix='/intake')
    app.register_blueprint(packets_bp, url_prefix='/packets')
    app.register_blueprint(shares_bp, url_prefix='/shares')
    app.register_blueprint(chat_bp, url_prefix='/chat')
    app.register_blueprint(graph_bp, url_prefix='/graph')
    
    return app

