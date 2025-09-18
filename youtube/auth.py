import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from urllib.parse import urlencode
import webbrowser
import socketserver
import threading
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import time
import random

class YouTubeAuth:
    def __init__(self, user_id=None):
        load_dotenv()
        self.client_id = os.getenv('YOUTUBE_CLIENT_ID')
        self.client_secret = os.getenv('YOUTUBE_CLIENT_SECRET')
        self.redirect_uri = os.getenv('YOUTUBE_REDIRECT_URI', 'http://localhost:8089')
        
        # YouTube API URLs
        self.auth_url = "https://accounts.google.com/o/oauth2/auth"
        self.token_url = "https://oauth2.googleapis.com/token"
        self.api_base_url = "https://www.googleapis.com/youtube/v3"
        
        # Scopes for YouTube Shorts upload and management
        self.scopes = [
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube",
            "https://www.googleapis.com/auth/youtube.readonly",
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email"
        ]
        
        # Use per-user token file under backend/instance/youtube_tokens/{user_id}.json
        from pathlib import Path
        instance_dir = Path(__file__).resolve().parent.parent / 'instance' / 'youtube_tokens'
        instance_dir.mkdir(parents=True, exist_ok=True)
        token_file_template = os.getenv('YOUTUBE_TOKEN_FILE', str(instance_dir / 'youtube_tokens_{user_id}.json'))
        self.user_id = user_id
        if user_id is not None:
            self.token_file = token_file_template.replace('{user_id}', str(user_id))
        else:
            self.token_file = token_file_template.replace('{user_id}', 'default')
        
        # Load existing tokens
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        self._last_validation_time = None  # Cache validation results
        self._load_tokens()

    def _load_tokens(self):
        """Load tokens from database first, then file as fallback"""
        # First try to load from database if user_id is available
        if self.user_id:
            try:
                from connection_service import ConnectionService
                connection_status = ConnectionService.get_user_connection_status(self.user_id, 'youtube')
                if connection_status.get('success') and connection_status.get('connected'):
                    connection_data = connection_status.get('connection_data', {})
                    self.access_token = connection_data.get('access_token')
                    additional_data = connection_data.get('additional_data', {})
                    if isinstance(additional_data, dict):
                        self.refresh_token = additional_data.get('refresh_token')
                    
                    # Set a reasonable expiry if not available (1 hour from now)
                    if self.access_token and not self.token_expires_at:
                        self.token_expires_at = datetime.now() + timedelta(hours=1)
                    
                    if self.access_token:
                        print(f"✅ YouTube tokens loaded from database for user {self.user_id}")
                        return
            except Exception as e:
                print(f"Warning: Could not load tokens from database: {e}")
        
        # Fallback to file-based loading
        try:
            if os.path.exists(self.token_file):
                with open(self.token_file, 'r') as f:
                    tokens = json.load(f)
                    self.access_token = tokens.get('access_token')
                    self.refresh_token = tokens.get('refresh_token')
                    expires_str = tokens.get('expires_at')
                    if expires_str:
                        self.token_expires_at = datetime.fromisoformat(expires_str)
                print(f"✅ YouTube tokens loaded from file: {self.token_file}")
        except Exception as e:
            print(f"Warning: Could not load tokens from file: {e}")

    def _save_tokens(self, access_token, refresh_token=None, expires_in=None):
        """Save tokens to file"""
        try:
            self.access_token = access_token
            if refresh_token:
                self.refresh_token = refresh_token
            
            if expires_in:
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            tokens = {
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
                'expires_at': self.token_expires_at.isoformat() if self.token_expires_at else None
            }
            
            # Ensure directory exists before writing
            try:
                from pathlib import Path as _P
                _P(self.token_file).parent.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            with open(self.token_file, 'w') as f:
                json.dump(tokens, f, indent=2)
            print(f"✅ Tokens saved to {self.token_file}")
        except Exception as e:
            print(f"Warning: Could not save tokens to file: {e}")

    def _clear_token_file(self):
        """Clear the token file when tokens are invalid"""
        try:
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
                print(f"✅ Cleared invalid token file: {self.token_file}")
        except Exception as e:
            print(f"Warning: Could not clear token file: {e}")

    def _is_token_expired(self):
        """Check if the current token is expired"""
        if not self.token_expires_at:
            return False  # If no expiry info, assume it's still valid
        return datetime.now() >= self.token_expires_at

    def _refresh_access_token(self):
        """Refresh the access token using refresh token"""
        if not self.refresh_token:
            print("No refresh token available")
            return False

        try:
            response = requests.post(
                self.token_url,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                }
            )
            response.raise_for_status()
            token_data = response.json()
            
            self._save_tokens(
                token_data["access_token"],
                token_data.get("refresh_token", self.refresh_token),  # Keep existing refresh token if not provided
                token_data.get("expires_in")
            )
            print("✅ Access token refreshed successfully")
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error refreshing access token: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return False

    def get_valid_token(self):
        """Get a valid access token, refreshing if necessary"""
        if not self.access_token:
            return None
        
        if self._is_token_expired():
            if self._refresh_access_token():
                return self.access_token
            else:
                return None
        
        return self.access_token

    def try_restore_connection(self):
        """Try to restore connection using saved credentials without OAuth"""
        # First check if we have tokens
        if not self.access_token and not self.refresh_token:
            return False
            
        # If token is expired but we have refresh token, try to refresh
        if self._is_token_expired() and self.refresh_token:
            if self._refresh_access_token():
                # After refresh, validate with YouTube API
                return self._validate_token_with_api()
            return False
            
        # If we have access token, validate it with YouTube API
        if self.access_token:
            return self._validate_token_with_api()
            
        return False

    def _validate_token_with_api(self):
        """Validate access token by making a test API call to YouTube"""
        if not self.access_token:
            return False
            
        try:
            # Make a simple API call to validate the token with timeout
            response = requests.get(
                f"{self.api_base_url}/channels",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params={"part": "snippet", "mine": "true"},
                timeout=10  # Add timeout to prevent hanging
            )
            
            if response.status_code == 200:
                # Cache successful validation for 5 minutes to reduce API calls
                self._last_validation_time = datetime.now()
                return True
            elif response.status_code == 401:
                # Token is invalid, clear it
                print("Token is invalid, clearing stored tokens")
                self.access_token = None
                self._clear_token_file()
                return False
            else:
                print(f"API validation failed with status: {response.status_code}")
                # Don't clear tokens for temporary API issues
                return False
                
        except requests.exceptions.Timeout:
            print("Token validation timed out, assuming valid to prevent disconnection")
            return True  # Assume valid on timeout to prevent false disconnections
        except Exception as e:
            print(f"Error validating token with API: {e}")
            # Don't clear tokens for network errors
            return True  # Assume valid on error to prevent false disconnections
    
    def _is_validation_cached(self):
        """Check if we have a recent successful validation (within 5 minutes)"""
        if not self._last_validation_time:
            return False
        
        time_since_validation = datetime.now() - self._last_validation_time
        return time_since_validation.total_seconds() < 300  # 5 minutes
    
    def validate_credentials(self):
        """Validate current credentials without triggering OAuth flow"""
        # If we have a recent successful validation, return True without API call
        if self.access_token and self._is_validation_cached():
            return True
        
        # Try to restore existing connection first
        if self.try_restore_connection():
            return True
        
        # If no valid tokens exist, return False without triggering OAuth
        # OAuth should only be triggered explicitly via connect endpoint
        return False

    def get_access_token(self):
        """Get access token via OAuth flow"""
        if not self.client_id or not self.client_secret:
            print("❌ YouTube OAuth credentials not configured")
            return None

        class OAuthHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                params = parse_qs(urlparse(self.path).query)
                if "code" in params:
                    self.server.auth_code = params["code"][0]
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    html = (
                        "<html><body>"
                        "<h1>✅ Authorization complete.</h1>"
                        "<p>You can close this window now.</p>"
                        "</body></html>"
                    )
                    self.wfile.write(html.encode("utf-8"))
                    threading.Thread(target=self.server.shutdown).start()
                else:
                    self.send_error(400, "Missing code parameter")

        # Start local server to receive the OAuth redirect with dynamic port selection
        port = 8089
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                httpd = socketserver.TCPServer(("localhost", port), OAuthHandler)
                break
            except OSError as e:
                if e.errno == 10048:  # Port already in use
                    port = 8089 + random.randint(1, 100)  # Try a different port
                    if attempt < max_attempts - 1:
                        print(f"Port {port - random.randint(1, 100)} in use, trying port {port}")
                        continue
                    else:
                        print(f"Could not find available port after {max_attempts} attempts")
                        return None
                else:
                    raise e
        
        # Update redirect URI to match the port we're actually using
        actual_redirect_uri = f"http://localhost:{port}"
        
        with httpd:
            query = {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": actual_redirect_uri,
                "scope": " ".join(self.scopes),
                "access_type": "offline",  # To get refresh token
                "prompt": "consent"  # Force consent to get refresh token
            }
            auth_url = self.auth_url + "?" + urlencode(query)
            print("\n🔗 Authorization URL:\n", auth_url, "\n")
            webbrowser.open(auth_url)
            httpd.handle_request()  # Wait for the redirect
            code = httpd.auth_code

        # Exchange the code for an access token
        try:
            response = requests.post(
                self.token_url,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": actual_redirect_uri,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                }
            )
            response.raise_for_status()
            token_data = response.json()
            
            # Save tokens
            self._save_tokens(
                token_data["access_token"],
                token_data.get("refresh_token"),
                token_data.get("expires_in")
            )
            
            print("✅ Access token obtained and saved.")
            return self.access_token
        except requests.exceptions.RequestException as e:
            print(f"Error getting access token: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return None

    def revoke_token(self):
        """Revoke the current access token and clear stored tokens"""
        if self.access_token:
            try:
                # Revoke token with Google OAuth
                response = requests.post(
                    "https://oauth2.googleapis.com/revoke",
                    params={"token": self.access_token}
                )
                if response.status_code == 200:
                    print("✅ Token revoked successfully")
            except Exception as e:
                print(f"Warning: Could not revoke token with API: {e}")
        
        # Clear stored tokens
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        
        # Remove token file
        try:
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
                print(f"✅ Token file {self.token_file} removed")
        except Exception as e:
            print(f"Warning: Could not remove token file: {e}")

# Usage example
if __name__ == "__main__":
    auth = YouTubeAuth()
    
    # This will automatically handle token refresh or new OAuth flow as needed
    if auth.validate_credentials():
        print("✅ Successfully authenticated with YouTube")
        print(f"Access token: {auth.access_token[:20]}...")
    else:
        print("❌ Authentication failed")
