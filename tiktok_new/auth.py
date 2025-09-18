import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from urllib.parse import urlencode
import webbrowser
import http.server
import socketserver
import threading
import base64
import hashlib
import secrets

class TikTokAuth:
    def __init__(self):
        load_dotenv()
        self.client_key = os.getenv('TIKTOK_CLIENT_KEY')
        self.client_secret = os.getenv('TIKTOK_CLIENT_SECRET')
        self.redirect_uri = os.getenv('TIKTOK_REDIRECT_URI', 'http://localhost:8080/callback')
        self.scope = os.getenv('TIKTOK_SCOPE', 'user.info.basic,video.list,video.upload')
        
        # API endpoints
        self.auth_url = "https://www.tiktok.com/v2/auth/authorize/"
        self.token_url = "https://open.tiktokapis.com/v2/oauth/token/"
        self.api_base_url = "https://open.tiktokapis.com/v2"
        
        # Token storage
        self.token_file = os.path.join(os.path.dirname(__file__), 'tiktok_tokens.json')
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        
        # Load existing tokens
        self._load_tokens()
        
        # PKCE variables
        self.code_verifier = None
        self.code_challenge = None

    def _load_tokens(self):
        """Load tokens from file if they exist"""
        try:
            if os.path.exists(self.token_file):
                with open(self.token_file, 'r') as f:
                    tokens = json.load(f)
                    self.access_token = tokens.get('access_token')
                    self.refresh_token = tokens.get('refresh_token')
                    expires_str = tokens.get('expires_at')
                    if expires_str:
                        self.token_expires_at = datetime.fromisoformat(expires_str)
        except Exception as e:
            print(f"Warning: Could not load TikTok tokens: {e}")

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
            
            with open(self.token_file, 'w') as f:
                json.dump(tokens, f, indent=2)
            print(f"✅ TikTok tokens saved")
        except Exception as e:
            print(f"Warning: Could not save TikTok tokens: {e}")

    def _is_token_expired(self):
        """Check if the current token is expired"""
        if not self.token_expires_at:
            return False
        return datetime.now() >= self.token_expires_at

    def _generate_pkce_pair(self):
        """Generate PKCE code verifier and challenge"""
        # Generate code verifier (43-128 characters)
        self.code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        
        # Generate code challenge (SHA256 hash of verifier)
        challenge_bytes = hashlib.sha256(self.code_verifier.encode('utf-8')).digest()
        self.code_challenge = base64.urlsafe_b64encode(challenge_bytes).decode('utf-8').rstrip('=')
        
        return self.code_verifier, self.code_challenge

    def _refresh_access_token(self):
        """Refresh the access token using refresh token"""
        if not self.refresh_token:
            return False

        try:
            response = requests.post(
                self.token_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "client_key": self.client_key,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token
                }
            )
            response.raise_for_status()
            token_data = response.json()
            
            self._save_tokens(
                token_data["access_token"],
                token_data.get("refresh_token"),
                token_data.get("expires_in")
            )
            print("✅ TikTok access token refreshed")
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error refreshing TikTok token: {e}")
            return False

    def validate_credentials(self):
        """Validate current credentials, refreshing if necessary"""
        if not self.access_token:
            return False
        
        if self._is_token_expired():
            if not self._refresh_access_token():
                return False
        
        # Test the token with a simple API call
        try:
            response = requests.get(
                f"{self.api_base_url}/user/info/",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params={"fields": "open_id"}
            )
            return response.status_code == 200
        except:
            return False

    def get_access_token(self):
        """Get access token via OAuth flow"""
        if not self.client_key or not self.client_secret:
            print("Error: TikTok client credentials not configured")
            return None

        class OAuthHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                from urllib.parse import parse_qs, urlparse
                params = parse_qs(urlparse(self.path).query)
                if "code" in params:
                    self.server.auth_code = params["code"][0]
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    html = (
                        "<html><body>"
                        "<h1>✅ TikTok Authorization Complete</h1>"
                        "<p>You can close this window now.</p>"
                        "</body></html>"
                    )
                    self.wfile.write(html.encode("utf-8"))
                    threading.Thread(target=self.server.shutdown).start()
                else:
                    self.send_error(400, "Missing authorization code")

        # Start local server for OAuth callback
        try:
            # Try different ports if 8080 is busy
            ports_to_try = [8080, 8081, 8082, 8083, 8084]
            httpd = None
            
            for port in ports_to_try:
                try:
                    httpd = socketserver.TCPServer(("localhost", port), OAuthHandler)
                    self.redirect_uri = f"http://localhost:{port}/callback"
                    print(f"OAuth server started on port {port}")
                    break
                except OSError as e:
                    if e.errno == 10048:  # Port already in use
                        continue
                    else:
                        raise
            
            if httpd is None:
                print("Error: Could not find an available port for OAuth server")
                return None
            
            with httpd:
                # Generate PKCE pair
                self._generate_pkce_pair()
                
                # Build authorization URL with PKCE
                auth_params = {
                    "client_key": self.client_key,
                    "response_type": "code",
                    "scope": self.scope,
                    "redirect_uri": self.redirect_uri,
                    "state": "tiktok_auth",
                    "code_challenge": self.code_challenge,
                    "code_challenge_method": "S256"
                }
                auth_url = self.auth_url + "?" + urlencode(auth_params)
                
                print(f"\n🔗 TikTok Authorization URL:\n{auth_url}\n")
                webbrowser.open(auth_url)
                
                httpd.handle_request()
                auth_code = getattr(httpd, 'auth_code', None)
                
                if not auth_code:
                    print("Error: No authorization code received")
                    return None

            # Exchange code for access token with PKCE
            response = requests.post(
                self.token_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "client_key": self.client_key,
                    "client_secret": self.client_secret,
                    "code": auth_code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri,
                    "code_verifier": self.code_verifier
                }
            )
            response.raise_for_status()
            token_data = response.json()
            
            self._save_tokens(
                token_data["access_token"],
                token_data.get("refresh_token"),
                token_data.get("expires_in")
            )
            
            print("✅ TikTok access token obtained")
            return self.access_token
            
        except Exception as e:
            print(f"Error during TikTok OAuth: {e}")
            return None

    def revoke_token(self):
        """Revoke tokens and clear stored data"""
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        
        try:
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
                print("✅ TikTok tokens cleared")
        except Exception as e:
            print(f"Warning: Could not remove TikTok token file: {e}")
        
        return True
