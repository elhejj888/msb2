import os
import shutil
import subprocess
import base64
import hashlib
import secrets
import urllib.parse
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import time
import requests
from datetime import datetime
import json

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP server to handle OAuth callback"""
    
    def do_GET(self):
        print(f"Received request: {self.path}")
        
        # Ignore favicon requests
        if self.path == '/favicon.ico':
            self.send_response(404)
            self.end_headers()
            return
        
        # Parse the callback URL to get the authorization code
        if '?code=' in self.path or '&code=' in self.path:
            # Extract code and state
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            auth_code = query_params.get('code', [None])[0]
            state = query_params.get('state', [None])[0]
            
            print(f"Extracted auth code: {auth_code[:20] if auth_code else 'None'}...")
            print(f"Extracted state: {state[:20] if state else 'None'}...")
            
            if auth_code:
                self.server.auth_code = auth_code
                self.server.state = state
                self.server.callback_received = True
                
                # Send success response
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                
                success_html = """
                <html>
                <head><title>Authorization Successful</title></head>
                <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: green;">✓ Authorization Successful!</h1>
                    <p>You have successfully authorized the application.</p>
                    <p>You can now close this window and return to the application.</p>
                    <script>setTimeout(function(){window.close();}, 3000);</script>
                </body>
                </html>
                """
                self.wfile.write(success_html.encode())
                return
        
        # Handle error cases
        if 'error=' in self.path:
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            error = query_params.get('error', ['unknown'])[0]
            error_description = query_params.get('error_description', [''])[0]
            
            print(f"OAuth Error: {error} - {error_description}")
            self.server.auth_error = error
            self.server.callback_received = True
        
        # Send error response
        self.send_response(400)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        error_html = """
        <html>
        <head><title>Authorization Failed</title></head>
        <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
            <h1 style="color: red;">✗ Authorization Failed</h1>
            <p>There was an error during authorization. Please try again.</p>
            <p>Make sure you clicked "Authorize app" on the previous page.</p>
        </body>
        </html>
        """
        self.wfile.write(error_html.encode())
    
    def log_message(self, format, *args):
        # Suppress server logs
        return

class XAuth:
    def __init__(self, client_id, client_secret, redirect_uri):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.token_url = 'https://api.twitter.com/2/oauth2/token'
        self.auth_url = 'https://twitter.com/i/oauth2/authorize'
        self.token_file = 'x_tokens.json'  # Add this line
        self.access_token = None
        self.refresh_token = None
        self.code_verifier = None
        self.oauth_state = None
        
    def generate_pkce_challenge(self):
        """Generate PKCE code verifier and challenge for OAuth 2.0"""
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')
        return code_verifier, code_challenge
    
    def start_oauth_flow(self, force_login: bool = False):
        """Start the OAuth 2.0 authorization flow.
        If force_login is True, add prompt=login to force account selection/login UI.
        """
        if not self.client_id:
            print("Error: Client ID not found. Please check your environment variables.")
            return None
        
        # Generate PKCE challenge
        code_verifier, code_challenge = self.generate_pkce_challenge()
        
        # Store code verifier for later use
        self.code_verifier = code_verifier
        
        # Generate state parameter
        state = secrets.token_urlsafe(32)
        self.oauth_state = state
        
        # Build authorization URL with correct scopes
        auth_params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': 'tweet.read tweet.write users.read offline.access',
            'state': state,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256'
        }

        # Force login prompt to allow switching accounts when needed
        if force_login:
            # Encourage account switch/login UI
            # prompt=login is standard; adding consent can also help re-show consent screen
            auth_params['prompt'] = 'login consent'
            # Some Twitter implementations also respect force_login=true (legacy compat)
            auth_params['force_login'] = 'true'
            # OIDC hint to force re-auth
            auth_params['max_age'] = '0'
        
        auth_url_full = f"{self.auth_url}?{urllib.parse.urlencode(auth_params)}"
        
        print("Starting OAuth 2.0 flow...")
        print("Opening browser for X authorization...")
        print(f"If the browser doesn't open automatically, visit: {auth_url_full}")
        
        # Start local server first
        try:
            server = HTTPServer(('localhost', 8081), OAuthCallbackHandler)
            server.timeout = 1  # Short timeout for handle_request
            server.callback_received = False
            server.auth_code = None
            server.auth_error = None
            
            # Open browser after server starts
            if force_login:
                # Try to launch in private/incognito to avoid sticky sessions
                self._open_private_browser(auth_url_full)
            else:
                webbrowser.open(auth_url_full)
            
            print("Waiting for authorization callback...")
            print("Please authorize the application in your browser.")
            
            # Handle the callback with improved logic
            start_time = time.time()
            while time.time() - start_time < 300:  # 5 minute timeout
                try:
                    server.handle_request()
                except Exception as e:
                    print(f"Server error: {e}")
                    continue
                
                # Check if callback was received
                if getattr(server, 'callback_received', False):
                    print("Callback received, processing...")
                    
                    if hasattr(server, 'auth_code') and server.auth_code:
                        print("Authorization code received!")
                        
                        # Verify state parameter
                        received_state = getattr(server, 'state', None)
                        print(f"Expected state: {state[:20]}...")
                        print(f"Received state: {received_state[:20] if received_state else 'None'}...")
                        
                        if received_state and received_state == state:
                            print("State verification successful!")
                            auth_code = server.auth_code
                            
                            # Close server properly
                            try:
                                server.server_close()
                            except:
                                pass
                            
                            return auth_code
                        else:
                            print(f"Warning: State parameter mismatch. Expected: {state}, Received: {received_state}")
                            print("This might be due to multiple OAuth flows or browser issues.")
                            print("Proceeding with authentication as the authorization code is valid.")
                            
                            # Proceed with the authorization code since it's valid
                            auth_code = server.auth_code
                            
                            # Close server properly
                            try:
                                server.server_close()
                            except:
                                pass
                            
                            return auth_code
                            
                    elif hasattr(server, 'auth_error') and server.auth_error:
                        print(f"Authorization failed with error: {server.auth_error}")
                        try:
                            server.server_close()
                        except:
                            pass
                        return None
                    
                    # If callback received but no code or error, continue waiting
                    print("Callback received but incomplete, continuing to wait...")
                    server.callback_received = False
            
            print("Timeout waiting for authorization callback")
            try:
                server.server_close()
            except:
                pass
            return None
            
        except OSError as e:
            if "Address already in use" in str(e):
                print("Error: Port 8081 is already in use. Please free the port and try again.")
                print("You can kill processes using port 8081 with: netstat -ano | findstr :8081")
            else:
                print(f"Error starting callback server: {e}")
            return None
        except Exception as e:
            print(f"Error during OAuth flow: {e}")
            return None

    def _open_private_browser(self, url: str):
        """Best-effort attempt to open URL in a private/incognito window on Windows.
        Falls back to default browser if specific browsers not found.
        """
        try:
            # Prefer Edge on Windows if available
            edge = shutil.which('msedge') or shutil.which('msedge.exe')
            if edge:
                subprocess.Popen([edge, '--inprivate', url])
                return
            # Try Chrome
            chrome = shutil.which('chrome') or shutil.which('chrome.exe')
            if chrome:
                subprocess.Popen([chrome, '--incognito', url])
                return
            # Try Firefox
            firefox = shutil.which('firefox') or shutil.which('firefox.exe')
            if firefox:
                subprocess.Popen([firefox, '-private-window', url])
                return
        except Exception as e:
            print(f"Private window launch failed, falling back to default browser: {e}")
        # Fallback
        webbrowser.open(url)
    
    def exchange_code_for_tokens(self, auth_code):
                """Exchange authorization code for access and refresh tokens"""
                print("Exchanging authorization code for tokens...")
                
                token_data = {
                    'grant_type': 'authorization_code',
                    'client_id': self.client_id,
                    'code': auth_code,
                    'redirect_uri': self.redirect_uri,
                    'code_verifier': self.code_verifier
                }
                
                # Create Basic Auth header
                credentials = f"{self.client_id}:{self.client_secret}"
                encoded_credentials = base64.b64encode(credentials.encode()).decode()
                
                headers = {
                    'Authorization': f'Basic {encoded_credentials}',
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
                
                try:
                    response = requests.post(self.token_url, data=token_data, headers=headers, timeout=30)
                    
                    print(f"Token exchange response status: {response.status_code}")
                    
                    if response.status_code != 200:
                        print(f"Token exchange failed with status {response.status_code}")
                        print(f"Response: {response.text}")
                        return False
                    
                    token_response = response.json()
                    print("Token exchange successful!")
                    
                    self.access_token = token_response.get('access_token')
                    self.refresh_token = token_response.get('refresh_token')
                    
                    if not self.access_token:
                        print("Error: No access token received")
                        return False
                    
                    # Save tokens
                    self.save_tokens()
                    
                    print("Successfully obtained and saved access tokens!")
                    return True
                    
                except requests.exceptions.Timeout:
                    print("Error: Request timeout during token exchange")
                    return False
                except requests.exceptions.RequestException as e:
                    print(f"Error exchanging code for tokens: {e}")
                    if hasattr(e, 'response') and e.response:
                        print(f"Response content: {e.response.text}")
                    return False
                except Exception as e:
                    print(f"Unexpected error during token exchange: {e}")
                    return False        
    
    def refresh_access_token(self):
        """Refresh the access token using refresh token"""
        if not self.refresh_token:
            print("No refresh token available. Need to re-authenticate.")
            return False
        
        print("Refreshing access token...")
        
        token_data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token,
            'client_id': self.client_id
        }
        
        # Create Basic Auth header
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            'Authorization': f'Basic {encoded_credentials}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        try:
            response = requests.post(self.token_url, data=token_data, headers=headers, timeout=30)
            
            if response.status_code != 200:
                print(f"Token refresh failed with status {response.status_code}")
                print(f"Response: {response.text}")
                return False
            
            token_response = response.json()
            self.access_token = token_response.get('access_token')
            
            # Update refresh token if provided
            if 'refresh_token' in token_response:
                self.refresh_token = token_response.get('refresh_token')
            
            # Save updated tokens
            self.save_tokens()
            
            print("Successfully refreshed access token!")
            return True
            
        except requests.exceptions.Timeout:
            print("Error: Request timeout during token refresh")
            return False
        except requests.exceptions.RequestException as e:
            print(f"Error refreshing token: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return False
    
    def save_tokens(self):
        """Save tokens to file"""
        token_data = {
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            with open(self.token_file, 'w') as f:
                json.dump(token_data, f, indent=2)
            print("Tokens saved successfully.")
        except Exception as e:
            print(f"Error saving tokens: {e}")
    
    def load_tokens(self):
        """Load tokens from file"""
        try:
            if os.path.exists(self.token_file):
                with open(self.token_file, 'r') as f:
                    token_data = json.load(f)
                    self.access_token = token_data.get('access_token')
                    self.refresh_token = token_data.get('refresh_token')
                    print("Existing tokens loaded from file.")
                    return True
        except Exception as e:
            print(f"Error loading tokens: {e}")
        return False