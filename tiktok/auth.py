import os
import requests
import base64
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from urllib.parse import urlencode
import webbrowser
import http.server
import socketserver
import threading

class TikTokAuth:
    def __init__(self):
        load_dotenv()
        self.client_key = os.getenv('TIKTOK_CLIENT_KEY')
        self.client_secret = os.getenv('TIKTOK_CLIENT_SECRET')
        self.redirect_uri = os.getenv('TIKTOK_REDIRECT_URI')
        self.scope = os.getenv('TIKTOK_SCOPE', 'user.info.basic,video.list,video.upload')
        
        # Token storage file
        self.token_file = os.getenv('TIKTOK_TOKEN_FILE', 'tiktok_tokens.json')
        
        # Load existing tokens
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        self._load_tokens()

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
            
            with open(self.token_file, 'w') as f:
                json.dump(tokens, f, indent=2)
            print(f"✅ Tokens saved to {self.token_file}")
        except Exception as e:
            print(f"Warning: Could not save tokens to file: {e}")

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
                "https://open.tiktokapis.com/v2/oauth/token/",
                headers={
                    "Content-Type": "application/x-www-form-urlencoded"
                },
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
            print("✅ Access token refreshed successfully")
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error refreshing access token: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return False

    def get_valid_token(self):
        """Get a valid access token, refreshing if necessary"""
        # If no token exists, need to do full OAuth flow
        if not self.access_token:
            print("No access token found. Starting OAuth flow...")
            return self.get_access_token()
        
        # If token is expired, try to refresh it
        if self._is_token_expired():
            print("Access token expired. Attempting to refresh...")
            if not self._refresh_access_token():
                print("Token refresh failed. Starting new OAuth flow...")
                return self.get_access_token()
        
        return self.access_token

    def validate_credentials(self):
        """Validate current credentials, getting new ones if needed"""
        token = self.get_valid_token()
        if not token:
            return False
        
        try:
            url = "https://open.tiktokapis.com/v2/user/info/"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            params = {"fields": "open_id,union_id,avatar_url,display_name"}
            
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error validating access token: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            
            # If validation fails, try to get a new token
            print("Token validation failed. Getting new token...")
            return self.get_access_token() is not None

    def get_access_token(self):
        """Get access token via OAuth flow"""
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
                        "<h1>✅ Authorization complete.</h1>"
                        "<p>You can close this window now.</p>"
                        "</body></html>"
                    )
                    self.wfile.write(html.encode("utf-8"))
                    threading.Thread(target=self.server.shutdown).start()
                else:
                    self.send_error(400, "Missing code parameter")

        # Start local server to receive the OAuth redirect
        with socketserver.TCPServer(("localhost", 8080), OAuthHandler) as httpd:
            query = {
                "client_key": self.client_key,
                "response_type": "code",
                "scope": self.scope,
                "redirect_uri": self.redirect_uri,
                "state": "tiktok_auth"
            }
            auth_url = "https://www.tiktok.com/auth/authorize/?" + urlencode(query)
            print("\n🔗 Authorization URL:\n", auth_url, "\n")
            webbrowser.open(auth_url)
            httpd.handle_request()  # Wait for the redirect
            code = httpd.auth_code

        # Exchange the code for an access token
        try:
            response = requests.post(
                "https://open.tiktokapis.com/v2/oauth/token/",
                headers={
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={
                    "client_key": self.client_key,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri
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
                # TikTok doesn't have a token revocation endpoint, so we just clear locally
                pass
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
    auth = TikTokAuth()
    
    # This will automatically handle token refresh or new OAuth flow as needed
    if auth.validate_credentials():
        print("✅ Successfully authenticated with TikTok")
        print(f"Access token: {auth.access_token[:20]}...")
    else:
        print("❌ Authentication failed")