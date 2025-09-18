import os
import requests
import base64
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from urllib.parse import urlencode

class PinterestAuth:
    def __init__(self, user_id=None):
        load_dotenv()
        self.app_id = os.getenv('PINTEREST_APP_ID')
        self.app_secret = os.getenv('PINTEREST_APP_SECRET')
        self.redirect_uri = os.getenv('PINTEREST_REDIRECT_URI')
        self.environment = os.getenv('PINTEREST_ENVIRONMENT', 'production')
        self.api_base_url = (
            "https://api-sandbox.pinterest.com/v5"
            if self.environment == "sandbox"
            else "https://api.pinterest.com/v5"
        )
        
        # Per-user token storage
        self.user_id = user_id
        token_template = os.getenv('PINTEREST_TOKEN_FILE')
        if token_template:
            # Support {user_id} placeholder in env override
            if '{user_id}' in token_template and user_id is not None:
                self.token_file = token_template.replace('{user_id}', str(user_id))
            else:
                # If template provided without placeholder, use as-is (legacy)
                self.token_file = token_template
        else:
            # Default to instance directory with per-user file when user_id is provided
            if user_id is not None:
                self.token_file = os.path.join(
                    os.path.dirname(__file__), '..', 'instance', 'pinterest_tokens', f'{user_id}.json'
                )
            else:
                # Legacy single shared file fallback (not recommended)
                print("Warning: No user_id provided, falling back to legacy single-file token storage.")
                self.token_file = os.path.join(
                    os.path.dirname(__file__), 'pinterest_tokens.json'
                )
        
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
            
            # Ensure directory exists
            try:
                token_dir = os.path.dirname(os.path.abspath(self.token_file))
                if token_dir and not os.path.exists(token_dir):
                    os.makedirs(token_dir, exist_ok=True)
            except Exception as e:
                print(f"Warning: Could not create token directory: {e}")

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

        b64 = base64.b64encode(f"{self.app_id}:{self.app_secret}".encode()).decode()
        try:
            response = requests.post(
                f"{self.api_base_url}/oauth/token",
                headers={
                    "Authorization": f"Basic {b64}",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={
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
            url = f"{self.api_base_url}/user_account"
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(url, headers=headers)
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
        import http.server
        import socketserver
        import threading
        import webbrowser
        
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
        class ReusableTCPServer(socketserver.TCPServer):
            allow_reuse_address = True

        try:
            with ReusableTCPServer(("127.0.0.1", 8080), OAuthHandler) as httpd:
                query = {
                    "response_type": "code",
                    "client_id": self.app_id,
                    "redirect_uri": self.redirect_uri,
                    "scope": "boards:read,boards:write,pins:read,pins:write,user_accounts:read",
                }
                auth_url = "https://www.pinterest.com/oauth/" + "?" + urlencode(query)
                print("\n🔗 Authorization URL:\n", auth_url, "\n")
                webbrowser.open(auth_url)
                httpd.handle_request()  # Wait for the redirect
                code = httpd.auth_code
        except OSError as e:
            # Common on Windows when 8080 is already in use
            print(f"❌ Failed to start local OAuth callback server on port 8080: {e}")
            print("Tip: Close any process using port 8080 (another OAuth flow or dev server) and try again.")
            return None

        # Exchange the code for an access token
        b64 = base64.b64encode(f"{self.app_id}:{self.app_secret}".encode()).decode()
        try:
            response = requests.post(
                f"{self.api_base_url}/oauth/token",
                headers={
                    "Authorization": f"Basic {b64}",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={
                    "grant_type": "authorization_code",
                    "code": code,
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
                # Revoke token with Pinterest API (if they support it)
                # Note: Check Pinterest API docs for token revocation endpoint
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
    auth = PinterestAuth()
    
    # This will automatically handle token refresh or new OAuth flow as needed
    if auth.validate_credentials():
        print("✅ Successfully authenticated with Pinterest")
        print(f"Access token: {auth.access_token[:20]}...")
    else:
        print("❌ Authentication failed")