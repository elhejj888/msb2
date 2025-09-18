import os
import requests
import json
import hashlib
import secrets
import urllib.parse
import base64
from datetime import datetime, timedelta

class TikTokAuth:
    def __init__(self):
        self.client_key = os.getenv('TIKTOK_CLIENT_KEY')
        self.client_secret = os.getenv('TIKTOK_CLIENT_SECRET')
        self.redirect_uri = os.getenv('TIKTOK_REDIRECT_URI', 'https://api.arabielle.com/api/tiktok/callback')
        self.scope = "user.info.basic,video.list,video.upload,video.publish"
        
        self.is_sandbox = os.getenv('TIKTOK_SANDBOX', 'false').lower() == 'true'
        
        # API URLs - different for sandbox vs production
        if self.is_sandbox:
            print("🧪 Using TikTok Sandbox environment")
            self.base_url = "https://open-api.tiktok-sandbox.com"  # Sandbox URL
            self.oauth_url = "https://www.tiktok-sandbox.com"       # Sandbox OAuth
        else:
            print("🌐 Using TikTok Production environment")
            self.base_url = "https://open.tiktokapis.com"
            self.oauth_url = "https://www.tiktok.com"
        
        # API endpoints
        self.endpoints = {
            'token': f"{self.base_url}/v2/oauth/token/",
            'user_info': f"{self.base_url}/v2/user/info/",
            'video_init': f"{self.base_url}/v2/post/publish/inbox/video/init/",
            'video_post': f"{self.base_url}/v2/post/publish/video/init/",
            'video_list': f"{self.base_url}/v2/video/list/",
            'video_query': f"{self.base_url}/v2/video/query/"
        }

        # File to store tokens (in production, use database)
        self.token_file = 'tiktok_tokens.json'
        
        
        # Load existing tokens
        self.access_token = None
        self.refresh_token = None
        self.expires_at = None
        self._load_tokens()
        
        print(f"🔧 TikTok Environment: {'Sandbox' if self.is_sandbox else 'Production'}")
        print(f"🔗 Base URL: {self.base_url}")
        

        if not self.client_key or not self.client_secret:
            print("Warning: TikTok Client Key and Client Secret are required")
            print("Please set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET environment variables")

    def _load_tokens(self):
        """Load tokens from file"""
        try:
            if os.path.exists(self.token_file):
                with open(self.token_file, 'r') as f:
                    data = json.load(f)
                    self.access_token = data.get('access_token')
                    self.refresh_token = data.get('refresh_token')
                    self.expires_at = data.get('expires_at')
        except Exception as e:
            print(f"Error loading tokens: {e}")

    def _save_tokens(self, access_token, refresh_token=None, expires_in=None):
        """Save tokens to file"""
        try:
            self.access_token = access_token
            if refresh_token:
                self.refresh_token = refresh_token
            
            if expires_in:
                self.expires_at = (datetime.now() + timedelta(seconds=expires_in)).isoformat()
            
            data = {
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
                'expires_at': self.expires_at
            }
            
            with open(self.token_file, 'w') as f:
                json.dump(data, f)
                
        except Exception as e:
            print(f"Error saving tokens: {e}")

    def _generate_pkce_challenge(self):
        """Generate PKCE code verifier and challenge"""
        # Generate a cryptographically random code_verifier
        code_verifier = base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8').rstrip('=')
        
        # Create the code_challenge by hashing the code_verifier with SHA256
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')
        
        return code_verifier, code_challenge

    def generate_auth_url(self):
        """Generate TikTok OAuth URL with sandbox support"""
        if not self.client_key:
            raise Exception("TikTok Client Key is not configured")
        
        # Generate CSRF token and PKCE challenge
        csrf_token = secrets.token_urlsafe(32)
        code_verifier, code_challenge = self._generate_pkce_challenge()
        
        # Save OAuth state
        self._save_oauth_state(csrf_token, code_verifier)
        
        params = {
            'client_key': self.client_key,
            'scope': self.scope,
            'response_type': 'code',
            'redirect_uri': self.redirect_uri,
            'state': csrf_token,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256'
        }
        
        # Use sandbox or production OAuth URL
        auth_url = f"{self.oauth_url}/v2/auth/authorize/?" + urllib.parse.urlencode(params)
        
        print(f"🔗 Generated OAuth URL: {auth_url}")
        print(f"🧪 Environment: {'Sandbox' if self.is_sandbox else 'Production'}")
        
        return auth_url, csrf_token

    def _save_oauth_state(self, csrf_token, code_verifier):
        """Save OAuth state including CSRF token and code verifier"""
        try:
            oauth_state = {
                'csrf_token': csrf_token,
                'code_verifier': code_verifier,
                'created_at': datetime.now().isoformat()
            }
            
            with open('tiktok_oauth_state.json', 'w') as f:
                json.dump(oauth_state, f)
                
            print(f"💾 Saved OAuth state with PKCE data")
        except Exception as e:
            print(f"Error saving OAuth state: {e}")

    def _load_and_verify_oauth_state(self, csrf_token):
        """Load and verify OAuth state, returning code_verifier if valid"""
        try:
            if os.path.exists('tiktok_oauth_state.json'):
                with open('tiktok_oauth_state.json', 'r') as f:
                    data = json.load(f)
                    stored_csrf = data.get('csrf_token')
                    code_verifier = data.get('code_verifier')
                    created_at = datetime.fromisoformat(data.get('created_at'))
                    
                    # Check if token is valid and not expired (5 minutes)
                    if stored_csrf == csrf_token and datetime.now() - created_at < timedelta(minutes=5):
                        # Delete the state file after use
                        os.remove('tiktok_oauth_state.json')
                        print(f"✅ OAuth state verified successfully")
                        return code_verifier
                    else:
                        print(f"❌ OAuth state verification failed - token mismatch or expired")
                        
            return None
        except Exception as e:
            print(f"Error verifying OAuth state: {e}")
            return None

    def exchange_code_for_token(self, code, state):
        """Exchange authorization code for access token"""
        print(f"🔄 Exchanging OAuth code for token...")
        
        # Verify state and get code_verifier
        code_verifier = self._load_and_verify_oauth_state(state)
        if not code_verifier:
            raise Exception("Invalid or expired CSRF token")
        
        try:
            token_data = {
                'client_key': self.client_key,
                'client_secret': self.client_secret,
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': self.redirect_uri,
                'code_verifier': code_verifier
            }
            
            print(f"📡 Making token request to: {self.endpoints['token']}")
            
            response = requests.post(
                self.endpoints['token'],  # Use configured endpoint
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Cache-Control": "no-cache"
                },
                data=token_data
            )
            
            print(f"📊 Token response status: {response.status_code}")
            print(f"📄 Token response: {response.text}")
            
            if response.status_code != 200:
                error_msg = f"Token exchange failed: {response.status_code} - {response.text}"
                raise Exception(error_msg)
            
            response_data = response.json()
            
            if 'access_token' not in response_data:
                raise Exception(f"No access token in response: {response_data}")
            
            # Save tokens
            self._save_tokens(
                response_data['access_token'],
                response_data.get('refresh_token'),
                response_data.get('expires_in')
            )
            
            print(f"✅ Token exchange successful!")
            return response_data
            
        except Exception as e:
            print(f"❌ Token exchange failed: {e}")
            raise

    def validate_credentials(self):
        """Validate credentials using configured endpoints"""
        if not self.access_token:
            return False
        
        try:
            print(f"🔍 Validating credentials against: {self.endpoints['user_info']}")
            
            response = requests.get(
                self.endpoints['user_info'],  # Use configured endpoint
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json"
                },
                params={
                    "fields": "open_id,union_id,avatar_url,display_name"
                }
            )
            
            print(f"📊 Validation response: {response.status_code}")
            if response.status_code != 200:
                print(f"📄 Response: {response.text}")
            
            return response.status_code == 200
            
        except Exception as e:
            print(f"❌ Validation error: {e}")
            return False

    def refresh_access_token(self):
        """Refresh the access token using refresh token"""
        if not self.refresh_token:
            print("❌ No refresh token available")
            return False
        
        try:
            print("🔄 Refreshing access token...")
            
            response = requests.post(
                "https://open.tiktokapis.com/v2/oauth/token/",
                headers={
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={
                    'client_key': self.client_key,
                    'client_secret': self.client_secret,
                    'grant_type': 'refresh_token',
                    'refresh_token': self.refresh_token
                }
            )
            
            print(f"📊 Refresh response status: {response.status_code}")
            print(f"📄 Refresh response: {response.text}")
            
            if response.status_code != 200:
                print(f"❌ Token refresh failed: {response.status_code} - {response.text}")
                return False
            
            token_data = response.json()
            
            self._save_tokens(
                token_data['access_token'],
                token_data.get('refresh_token'),
                token_data.get('expires_in')
            )
            
            print("✅ Access token refreshed successfully")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error refreshing token: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"📄 Error response: {e.response.text}")
            return False

    def revoke_token(self):
        """Revoke the current access token and clear stored tokens"""
        print("🔌 Revoking TikTok tokens...")
        
        if self.access_token:
            try:
                # Try to revoke the token on TikTok's side (if endpoint exists)
                # Note: TikTok API might not have a revoke endpoint, but we'll clear local storage
                pass
            except:
                pass
        
        # Clear local token storage
        self.access_token = None
        self.refresh_token = None
        self.expires_at = None
        
        # Remove token and state files
        files_to_remove = [self.token_file, 'tiktok_oauth_state.json']
        for file in files_to_remove:
            try:
                if os.path.exists(file):
                    os.remove(file)
                    print(f"🗑️ Removed {file}")
            except Exception as e:
                print(f"⚠️ Could not remove {file}: {e}")
        
        print("✅ TikTok tokens cleared")

    def get_access_token(self):
        """Get current access token, refresh if needed"""
        if not self.access_token:
            print("❌ No access token available")
            return None
        
        # Check if token needs refresh
        if self.expires_at:
            try:
                expires_at = datetime.fromisoformat(self.expires_at)
                # Refresh if token expires in less than 5 minutes
                if datetime.now() >= expires_at - timedelta(minutes=5):
                    print("⏰ Token expires soon, attempting refresh...")
                    if self.refresh_access_token():
                        return self.access_token
                    else:
                        print("❌ Token refresh failed")
                        return None
            except Exception as e:
                print(f"⚠️ Error checking token expiry: {e}")
        
        return self.access_token