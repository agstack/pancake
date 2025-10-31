"""
User Registry Client - JWT validation, discoverability, webhooks
Integrates with https://github.com/agstack/user-registry
"""
import logging
import requests
from typing import Optional, Tuple, Dict, Any
from flask import current_app

logger = logging.getLogger(__name__)


class UserRegistryClient:
    """
    Client for User Registry API
    Handles JWT validation, user discoverability checks
    """
    
    def __init__(self, base_url: str = None, timeout: int = 10):
        self.base_url = base_url
        self.timeout = timeout
    
    def _get_base_url(self):
        """Get base URL with lazy initialization"""
        if self.base_url:
            return self.base_url
        try:
            from flask import current_app
            return current_app.config.get('USER_REGISTRY_URL', 'http://localhost:5000')
        except RuntimeError:
            return 'http://localhost:5000'
    
    def verify_token(self, token: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Verify JWT token with User Registry
        
        Returns:
            (is_valid, user_data, error_message)
        """
        try:
            # For MVP: Simple token validation
            # In production, this would call User Registry /verify endpoint
            # For now, we'll decode JWT locally
            import jwt
            secret_key = current_app.config.get('JWT_SECRET_KEY')
            algorithm = current_app.config.get('JWT_ALGORITHM')
            
            try:
                payload = jwt.decode(token, secret_key, algorithms=[algorithm])
                return True, payload, None
            except jwt.ExpiredSignatureError:
                return False, None, "Token expired"
            except jwt.InvalidTokenError:
                return False, None, "Invalid token"
                
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return False, None, str(e)
    
    def check_discoverability(self, user_id: str, token: str = None) -> Tuple[bool, Optional[str]]:
        """
        Check if user is discoverable
        
        Returns:
            (is_discoverable, error_message)
        """
        try:
            # For MVP: Stub implementation
            # In production, would query User Registry for user's discoverable status
            logger.info(f"Checking discoverability for user: {user_id}")
            
            # For now, assume users are discoverable if they have registered
            # This would be replaced with actual User Registry API call
            return True, None
            
        except Exception as e:
            logger.error(f"Discoverability check error: {e}")
            return False, str(e)
    
    def get_user_by_email(self, email: str, token: str = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Get user info by email
        
        Returns:
            (user_data, error_message)
        """
        try:
            # For MVP: Stub implementation
            # In production, would query User Registry
            logger.info(f"Looking up user by email: {email}")
            
            # Stub response
            return None, "User not found (stub)"
            
        except Exception as e:
            logger.error(f"User lookup error: {e}")
            return None, str(e)
    
    def notify_invitation(self, contact_value: str, invite_token: str) -> Tuple[bool, Optional[str]]:
        """
        Notify user about invitation (webhook to User Registry)
        
        Returns:
            (success, error_message)
        """
        try:
            logger.info(f"Sending invitation notification to: {contact_value}")
            
            # For MVP: Stub - just log
            # In production, would call User Registry webhook
            return True, None
            
        except Exception as e:
            logger.error(f"Invitation notification error: {e}")
            return False, str(e)


# Singleton instance
user_registry_client = UserRegistryClient()

