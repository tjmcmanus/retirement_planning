"""
Schwab OAuth 2.0 Authentication with PKCE
Handles secure authentication flow for Schwab API
"""

import secrets
import hashlib
import base64
import requests
import logging
from urllib.parse import urlencode, parse_qs, urlparse
from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class SchwabOAuth:
    """
    Handle Schwab OAuth 2.0 authentication with PKCE (Proof Key for Code Exchange)
    
    OAuth Flow:
    1. Generate PKCE code verifier and challenge
    2. Create authorization URL
    3. User authorizes in browser
    4. Exchange authorization code for tokens
    5. Store and refresh tokens as needed
    """
    
    # Schwab API endpoints
    AUTH_URL = "https://api.schwabapi.com/v1/oauth/authorize"
    TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"
    
    def __init__(self, app_key: str, app_secret: str, callback_url: str):
        """
        Initialize Schwab OAuth handler
        
        Args:
            app_key: Schwab application key (client ID)
            app_secret: Schwab application secret
            callback_url: OAuth callback URL (must match registered URL)
        """
        self.app_key = app_key
        self.app_secret = app_secret
        self.callback_url = callback_url
        self.code_verifier = None
        
        logger.info("Schwab OAuth initialized")
    
    def generate_pkce_pair(self) -> Tuple[str, str]:
        """
        Generate PKCE code verifier and challenge
        
        PKCE adds security by requiring the client to prove it initiated
        the authorization request. This prevents authorization code interception.
        
        Returns:
            Tuple of (code_verifier, code_challenge)
        """
        # Generate random 32-byte code verifier
        code_verifier = base64.urlsafe_b64encode(
            secrets.token_bytes(32)
        ).decode('utf-8').rstrip('=')
        
        # Create SHA256 hash of verifier for challenge
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')
        
        logger.debug("Generated PKCE pair")
        return code_verifier, code_challenge
    
    def get_authorization_url(self) -> Tuple[str, str]:
        """
        Generate OAuth authorization URL for user to visit
        
        Returns:
            Tuple of (authorization_url, code_verifier)
            Store code_verifier for later token exchange
        """
        # Generate PKCE pair
        self.code_verifier, code_challenge = self.generate_pkce_pair()
        
        # Build authorization URL parameters
        params = {
            'client_id': self.app_key,
            'redirect_uri': self.callback_url,
            'response_type': 'code',
            'scope': 'api',  # Request API access scope
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256'  # SHA256 hashing
        }
        
        auth_url = f"{self.AUTH_URL}?{urlencode(params)}"
        
        logger.info("Generated authorization URL")
        return auth_url, self.code_verifier
    
    def exchange_code_for_token(
        self, 
        auth_code: str, 
        code_verifier: Optional[str] = None
    ) -> Dict:
        """
        Exchange authorization code for access and refresh tokens
        
        Args:
            auth_code: Authorization code from callback
            code_verifier: PKCE code verifier (uses stored if not provided)
            
        Returns:
            Dictionary containing:
                - access_token: Token for API requests
                - refresh_token: Token for refreshing access
                - expires_in: Seconds until access token expires
                - token_type: Usually "Bearer"
                - scope: Granted scopes
                
        Raises:
            requests.HTTPError: If token exchange fails
        """
        if code_verifier is None:
            code_verifier = self.code_verifier
            
        if code_verifier is None:
            raise ValueError("Code verifier not found. Call get_authorization_url first.")
        
        # Prepare token request
        data = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': self.callback_url,
            'client_id': self.app_key,
            'code_verifier': code_verifier
        }
        
        try:
            # Exchange code for tokens
            response = requests.post(
                self.TOKEN_URL,
                data=data,
                auth=(self.app_key, self.app_secret),
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            response.raise_for_status()
            
            token_data = response.json()
            
            # Add expiration timestamp
            token_data['expires_at'] = (
                datetime.now() + timedelta(seconds=token_data['expires_in'])
            ).isoformat()
            
            logger.info("Successfully exchanged code for tokens")
            return token_data
            
        except requests.HTTPError as e:
            logger.error(f"Token exchange failed: {e}")
            logger.error(f"Response: {e.response.text if e.response else 'No response'}")
            raise
    
    def refresh_access_token(self, refresh_token: str) -> Dict:
        """
        Refresh expired access token using refresh token
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            Dictionary with new access_token and updated expires_in
            
        Raises:
            requests.HTTPError: If refresh fails
        """
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': self.app_key
        }
        
        try:
            response = requests.post(
                self.TOKEN_URL,
                data=data,
                auth=(self.app_key, self.app_secret),
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            response.raise_for_status()
            
            token_data = response.json()
            
            # Add expiration timestamp
            token_data['expires_at'] = (
                datetime.now() + timedelta(seconds=token_data['expires_in'])
            ).isoformat()
            
            logger.info("Successfully refreshed access token")
            return token_data
            
        except requests.HTTPError as e:
            logger.error(f"Token refresh failed: {e}")
            logger.error(f"Response: {e.response.text if e.response else 'No response'}")
            raise
    
    def is_token_expired(self, expires_at: str) -> bool:
        """
        Check if access token is expired or about to expire
        
        Args:
            expires_at: ISO format timestamp of expiration
            
        Returns:
            True if token is expired or expires within 5 minutes
        """
        try:
            expiry = datetime.fromisoformat(expires_at)
            # Consider expired if less than 5 minutes remaining
            buffer = timedelta(minutes=5)
            return datetime.now() >= (expiry - buffer)
        except (ValueError, TypeError):
            logger.warning("Invalid expiration timestamp")
            return True
    
    @staticmethod
    def parse_callback_url(callback_url: str) -> Optional[str]:
        """
        Extract authorization code from callback URL
        
        Args:
            callback_url: Full callback URL with query parameters
            
        Returns:
            Authorization code or None if not found
        """
        try:
            parsed = urlparse(callback_url)
            params = parse_qs(parsed.query)
            
            if 'code' in params:
                return params['code'][0]
            
            # Check for error
            if 'error' in params:
                error = params['error'][0]
                error_desc = params.get('error_description', ['Unknown'])[0]
                logger.error(f"OAuth error: {error} - {error_desc}")
                
            return None
            
        except Exception as e:
            logger.error(f"Failed to parse callback URL: {e}")
            return None


class TokenManager:
    """
    Manage token lifecycle including storage and refresh
    Works with CredentialManager for secure storage
    """
    
    def __init__(self, oauth: SchwabOAuth):
        """
        Initialize token manager
        
        Args:
            oauth: SchwabOAuth instance for token refresh
        """
        self.oauth = oauth
        self.access_token = None
        self.refresh_token = None
        self.expires_at = None
    
    def set_tokens(self, token_data: Dict):
        """
        Store tokens from OAuth response
        
        Args:
            token_data: Dictionary with access_token, refresh_token, expires_at
        """
        self.access_token = token_data.get('access_token')
        self.refresh_token = token_data.get('refresh_token')
        self.expires_at = token_data.get('expires_at')
        
        logger.info("Tokens stored in memory")
    
    def get_valid_access_token(self) -> Optional[str]:
        """
        Get valid access token, refreshing if necessary
        
        Returns:
            Valid access token or None if refresh fails
        """
        if not self.access_token:
            logger.warning("No access token available")
            return None
        
        # Check if token needs refresh
        if self.expires_at and self.oauth.is_token_expired(self.expires_at):
            logger.info("Access token expired, refreshing...")
            
            if not self.refresh_token:
                logger.error("No refresh token available")
                return None
            
            try:
                # Refresh token
                token_data = self.oauth.refresh_access_token(self.refresh_token)
                self.set_tokens(token_data)
                
            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
                return None
        
        return self.access_token
    
    def clear_tokens(self):
        """Clear all stored tokens"""
        self.access_token = None
        self.refresh_token = None
        self.expires_at = None
        logger.info("Tokens cleared")

# Made with Bob
