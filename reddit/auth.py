import os
import praw
from flask import Flask, request, redirect
import webbrowser
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from pathlib import Path
from dotenv import load_dotenv


load_dotenv()

class RedditAuth:
    def __init__(self, client_id=None, client_secret=None, credentials_path: Path | None = None, persist_to_file: bool = True):
        # Allow per-user credentials file path to prevent token sharing across app users
        # Default to project instance directory if provided; fallback to home only if explicitly desired
        default_path = Path(os.path.dirname(os.path.abspath(__file__))).parent / 'instance' / 'reddit_tokens.json'
        self.credentials_file = credentials_path if credentials_path else default_path
        self.persist_to_file = persist_to_file
        self.client_id = client_id or os.getenv('REDDIT_CLIENT_ID')
        self.client_secret = client_secret or os.getenv('REDDIT_CLIENT_SECRET')
        self.redirect_uri = os.getenv('REDDIT_REDIRECT_URI')
        self.token = None
        self.reddit = None
        
    def load_credentials(self):
        """Load saved credentials from file (if persistence enabled)"""
        try:
            if not self.persist_to_file:
                return None
            if self.credentials_file and self.credentials_file.exists():
                with open(self.credentials_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Failed to load Reddit credentials from {self.credentials_file}: {e}")
        return None
    
    def save_credentials(self, token_info):
        """Save credentials to file (if persistence enabled)"""
        try:
            if not self.persist_to_file:
                return
            # Ensure parent directory exists
            if self.credentials_file:
                self.credentials_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.credentials_file, 'w') as f:
                    json.dump(token_info, f)
        except Exception as e:
            print(f"Failed to save Reddit credentials to {self.credentials_file}: {e}")
    
    def authenticate(self):
        """Main authentication method"""
        saved_creds = self.load_credentials()
        
        if saved_creds:
            try:
                self.reddit = praw.Reddit(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    refresh_token=saved_creds['refresh_token'],
                    user_agent="RedditCRUDAutomation/1.0"
                )
                # Verify the token works by making a simple API call
                try:
                    self.reddit.user.me()
                    return True
                except Exception as e:
                    print(f"Token verification failed: {e}")
                    # Token might be expired, proceed to OAuth flow
                    return self._oauth_flow()
            except Exception as e:
                print(f"Saved credentials invalid: {e}. Starting new authentication.")
        
        # If no saved credentials or they're invalid, do OAuth flow
        return self._oauth_flow()
    
    def try_restore_connection(self):
        """Try to restore connection using saved credentials without OAuth flow"""
        saved_creds = self.load_credentials()
        
        if saved_creds:
            try:
                self.reddit = praw.Reddit(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    refresh_token=saved_creds['refresh_token'],
                    user_agent="RedditCRUDAutomation/1.0"
                )
                # Verify the token works by making a simple API call
                try:
                    self.reddit.user.me()
                    return True
                except Exception as e:
                    print(f"Token verification failed: {e}")
                    # Don't proceed to OAuth flow, just return False
                    return False
            except Exception as e:
                print(f"Saved credentials invalid: {e}")
                return False
        
        return False
    
    def _oauth_flow(self):
        """Perform OAuth 2.0 flow"""
        # Use a different port to avoid conflicts
        port = 8083  
        
        # Create a temporary Flask server to handle the callback
        app = Flask(__name__)
        
        # Event to signal when auth is complete
        auth_complete = threading.Event()
        
        @app.route('/callback')
        def callback():
            nonlocal auth_complete
            state = request.args.get('state')
            code = request.args.get('code')
            
            if not code:
                auth_complete.set()
                return "Authentication failed: No authorization code received", 400
            
            try:
                self.reddit = praw.Reddit(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    redirect_uri=self.redirect_uri,
                    user_agent="RedditCRUDAutomation/1.0"
                )
                
                # Get refresh token
                refresh_token = self.reddit.auth.authorize(code)
                
                # Save the refresh token
                token_info = {
                    'refresh_token': refresh_token,
                    'client_id': self.client_id,
                    'client_secret': self.client_secret
                }
                self.save_credentials(token_info)
                
                auth_complete.set()
                return "Authentication successful! You can close this window and return to the application."
            except Exception as e:
                auth_complete.set()
                return f"Authentication failed: {str(e)}", 400
        
        # Use a more reliable way to run the server
        def run_server():
            from werkzeug.serving import make_server
            server = make_server('localhost', port, app)
            server.timeout = 300  # 5 minute timeout
            server.serve_forever()
        
        server_thread = threading.Thread(target=run_server)
        server_thread.daemon = True
        server_thread.start()
        
        # Generate OAuth URL and open browser
        reddit = praw.Reddit(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            user_agent="RedditCRUDAutomation/1.0"
        )
        
        scopes = ['identity', 'submit', 'read', 'edit', 'history', 'flair']
        state = "random_state_string"
        url = reddit.auth.url(scopes, state, 'permanent')
        
        print(f"Opening browser for authentication. If it doesn't open automatically, visit this URL:\n{url}")
        webbrowser.open(url)
        
        # Wait for auth to complete with timeout
        auth_complete.wait(timeout=300)  # 5 minute timeout
        
        # Clean up the server
        if hasattr(app, 'shutdown'):
            app.shutdown()
        
        return self.reddit is not None