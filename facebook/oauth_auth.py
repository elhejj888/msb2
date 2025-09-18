import os
import webbrowser
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import requests
from dotenv import load_dotenv, set_key
import ssl
import socket


class FacebookOAuth:
    def __init__(self, use_https=False):
        load_dotenv()
        self.app_id = os.getenv('FACEBOOK_APP_ID')
        self.app_secret = os.getenv('FACEBOOK_APP_SECRET')
        self.use_https = use_https
        
        # Find available port
        self.port = self._find_available_port()
        
        # Ensure consistent protocol usage
        protocol = 'https' if use_https else 'http'
        self.redirect_uri = f"{protocol}://localhost:{self.port}/auth/callback"
        
        self.scopes = [
            'pages_manage_posts',
            'pages_read_engagement',
            'pages_show_list'
        ]
        self.page_id = None
        self.user_token = None
        self.page_token = None

    def _find_available_port(self, start_port=8085):
        """Find an available port starting from start_port"""
        for port in range(start_port, start_port + 10):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('localhost', port))
                    return port
            except OSError:
                continue
        return start_port  # Fallback to original port

    def get_auth_url(self):
        return (
            f"https://www.facebook.com/v20.0/dialog/oauth?"
            f"client_id={self.app_id}"
            f"&redirect_uri={self.redirect_uri}"
            f"&scope={','.join(self.scopes)}"
            f"&response_type=code"
            f"&state=random_state_string"  # Add state for security
        )

    def authenticate(self):
        print("Starting Facebook OAuth authentication...")
        print(f"Using redirect URI: {self.redirect_uri}")
        
        # Start local server to handle callback
        server = CallbackServer(self.redirect_uri, self.use_https, self.port)
        
        # Start server in a separate thread
        server_thread = threading.Thread(target=server.start_server)
        server_thread.daemon = True
        server_thread.start()
        
        # Give server time to start
        time.sleep(2)
        
        # Open browser for user authentication
        auth_url = self.get_auth_url()
        print(f"Opening browser for Facebook authentication...")
        print(f"Auth URL: {auth_url}")
        webbrowser.open(auth_url)

        # Wait for the callback with timeout
        print("Waiting for authorization callback...")
        timeout = 300  # 5 minutes timeout
        start_time = time.time()
        
        while not server.authorization_code and not server.error_occurred and (time.time() - start_time) < timeout:
            time.sleep(1)
        
        if server.authorization_code:
            print("Authorization code received!")
            success = self.exchange_code_for_token(server.authorization_code)
            server.stop_server()
            return success
        elif server.error_occurred:
            print(f"Authentication error occurred: {server.error_message}")
            server.stop_server()
            return False
        else:
            print("Timeout waiting for authorization callback")
            server.stop_server()
            return False

    def exchange_code_for_token(self, code):
        print("Exchanging authorization code for access token...")
        token_url = (
            f"https://graph.facebook.com/v20.0/oauth/access_token?"
            f"client_id={self.app_id}"
            f"&redirect_uri={self.redirect_uri}"
            f"&client_secret={self.app_secret}"
            f"&code={code}"
        )

        try:
            response = requests.get(token_url)
            response.raise_for_status()
            token_data = response.json()
            
            if 'access_token' in token_data:
                self.user_token = token_data['access_token']
                print("User access token obtained successfully!")
                
                # Save to .env file
                set_key('.env', 'FACEBOOK_USER_TOKEN', self.user_token)
                
                # Get page token
                return self.get_page_access_token()
            else:
                print(f"Error in token response: {token_data}")
                return False
                
        except Exception as e:
            print(f"Error exchanging code for token: {e}")
            return False

    def get_page_access_token(self):
        if not self.user_token:
            print("User token not available")
            return False

        try:
            print("Getting page access token...")
            # Get user's pages
            pages_url = f"https://graph.facebook.com/v20.0/me/accounts?access_token={self.user_token}"
            response = requests.get(pages_url)
            response.raise_for_status()
            pages_data = response.json()

            if 'data' in pages_data and len(pages_data['data']) > 0:
                print(f"Found {len(pages_data['data'])} page(s)")
                
                # Show available pages
                for i, page in enumerate(pages_data['data']):
                    print(f"{i+1}. {page['name']} (ID: {page['id']})")
                
                # For simplicity, use the first page
                page = pages_data['data'][0]
                self.page_id = page['id']
                self.page_token = page['access_token']
                
                print(f"Using page: {page['name']}")
                
                # Save to .env file
                set_key('.env', 'FACEBOOK_PAGE_ID', self.page_id)
                set_key('.env', 'FACEBOOK_PAGE_TOKEN', self.page_token)
                
                return True
            else:
                print("No pages found for this user")
                return False
        except Exception as e:
            print(f"Error getting page access token: {e}")
            return False


class CallbackServer:
    def __init__(self, redirect_uri, use_https=False, port=8085):
        self.redirect_uri = redirect_uri
        self.use_https = use_https
        self.port = port
        self.authorization_code = None
        self.error_occurred = False
        self.error_message = None
        self.server = None
        self.running = False

    def start_server(self):
        callback_server = self  # Reference to outer scope
        
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                # Suppress default logging
                pass
                
            def do_GET(self):
                try:
                    print(f"Received callback: {self.path}")
                    query = urlparse(self.path).query
                    params = parse_qs(query)
                    
                    if 'code' in params:
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        
                        success_html = """
                        <html>
                        <head>
                            <title>Authentication Successful</title>
                            <meta charset="UTF-8">
                        </head>
                        <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">
                            <div style="background: rgba(255,255,255,0.1); padding: 40px; border-radius: 10px; backdrop-filter: blur(10px);">
                                <h1 style="color: #4CAF50; margin-bottom: 20px;">✅ Authentication Successful!</h1>
                                <p style="font-size: 18px; margin-bottom: 10px;">You have successfully authenticated with Facebook.</p>
                                <p style="font-size: 16px; opacity: 0.9;">You can now close this window and return to your application.</p>
                                <div style="margin-top: 30px;">
                                    <button onclick="window.close()" style="background: #4CAF50; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-size: 16px;">Close Window</button>
                                </div>
                            </div>
                            <script>
                                setTimeout(function() {
                                    window.close();
                                }, 5000);
                            </script>
                        </body>
                        </html>
                        """
                        self.wfile.write(success_html.encode('utf-8'))
                        callback_server.authorization_code = params['code'][0]
                        print("✅ Authorization code captured successfully!")
                        
                    elif 'error' in params:
                        self.send_response(400)
                        self.send_header('Content-type', 'text/html')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        
                        error_desc = params.get('error_description', ['No description'])[0]
                        error_html = f"""
                        <html>
                        <head>
                            <title>Authentication Failed</title>
                            <meta charset="UTF-8">
                        </head>
                        <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px; background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%); color: white;">
                            <div style="background: rgba(255,255,255,0.1); padding: 40px; border-radius: 10px; backdrop-filter: blur(10px);">
                                <h1 style="color: #FF6B6B; margin-bottom: 20px;">❌ Authentication Failed</h1>
                                <p style="font-size: 18px; margin-bottom: 10px;">Error: {params.get('error', ['Unknown error'])[0]}</p>
                                <p style="font-size: 16px; opacity: 0.9;">Description: {error_desc}</p>
                                <div style="margin-top: 30px;">
                                    <button onclick="window.close()" style="background: #FF6B6B; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-size: 16px;">Close Window</button>
                                </div>
                            </div>
                        </body>
                        </html>
                        """
                        self.wfile.write(error_html.encode('utf-8'))
                        callback_server.error_occurred = True
                        callback_server.error_message = f"{params.get('error', ['Unknown'])[0]}: {error_desc}"
                        print(f"❌ Authentication error: {callback_server.error_message}")
                    else:
                        self.send_response(400)
                        self.send_header('Content-type', 'text/html')
                        self.end_headers()
                        self.wfile.write(b"<html><body><h1>Invalid callback - missing code or error parameter</h1></body></html>")
                        callback_server.error_occurred = True
                        callback_server.error_message = "Invalid callback received"
                        
                except Exception as e:
                    print(f"Error handling callback: {e}")
                    callback_server.error_occurred = True
                    callback_server.error_message = str(e)

        try:
            self.server = HTTPServer(('localhost', self.port), Handler)
            
            if self.use_https:
                # Try to set up HTTPS
                try:
                    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                    context.load_cert_chain('cert.pem', 'key.pem')
                    self.server.socket = context.wrap_socket(
                        self.server.socket, 
                        server_side=True
                    )
                    print(f"🔒 HTTPS server started on https://localhost:{self.port}")
                except FileNotFoundError:
                    print("⚠️  SSL certificates not found. Please generate them first:")
                    print("openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj '/CN=localhost'")
                    self.error_occurred = True
                    self.error_message = "SSL certificates not found"
                    return
                except Exception as e:
                    print(f"⚠️  SSL setup failed: {e}")
                    self.error_occurred = True
                    self.error_message = f"SSL setup failed: {e}"
                    return
            else:
                print(f"🌐 HTTP server started on http://localhost:{self.port}")
            
            self.running = True
            
            # Handle requests until we get the callback or timeout
            while self.running and not self.authorization_code and not self.error_occurred:
                try:
                    self.server.timeout = 1  # 1 second timeout for handle_request
                    self.server.handle_request()
                except socket.timeout:
                    continue  # Continue waiting
                except Exception as e:
                    print(f"Server error: {e}")
                    break
                    
        except Exception as e:
            print(f"❌ Error starting server: {e}")
            self.error_occurred = True
            self.error_message = str(e)
        finally:
            if self.server:
                try:
                    self.server.server_close()
                except:
                    pass

    def stop_server(self):
        self.running = False
        if self.server:
            try:
                self.server.server_close()
            except:
                pass


# Helper function to generate SSL certificates
def generate_ssl_certificates():
    """Generate self-signed SSL certificates for development"""
    import subprocess
    import os
    
    if os.path.exists('cert.pem') and os.path.exists('key.pem'):
        print("SSL certificates already exist.")
        return True
    
    try:
        cmd = [
            'openssl', 'req', '-x509', '-newkey', 'rsa:4096', 
            '-keyout', 'key.pem', '-out', 'cert.pem', 
            '-days', '365', '-nodes', '-subj', '/CN=localhost'
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        print("✅ SSL certificates generated successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to generate SSL certificates: {e}")
        print("Please install OpenSSL or generate certificates manually.")
        return False
    except FileNotFoundError:
        print("❌ OpenSSL not found. Please install OpenSSL first.")
        return False


# Example usage and test function
def test_facebook_oauth():
    """Test the Facebook OAuth flow"""
    
    # Check if required environment variables are set
    load_dotenv()
    app_id = os.getenv('FACEBOOK_APP_ID')
    app_secret = os.getenv('FACEBOOK_APP_SECRET')
    
    if not app_id or not app_secret:
        print("❌ Missing Facebook app credentials!")
        print("Please set FACEBOOK_APP_ID and FACEBOOK_APP_SECRET in your .env file")
        return False
    
    print("🚀 Starting Facebook OAuth test...")
    print(f"App ID: {app_id}")
    
    # Ask user for HTTPS preference
    use_https = input("Use HTTPS? (y/n) [n]: ").lower().startswith('y')
    
    if use_https:
        if not generate_ssl_certificates():
            print("Falling back to HTTP mode...")
            use_https = False
    
    oauth = FacebookOAuth(use_https=use_https)
    
    print("\n📋 Make sure your Facebook app settings include:")
    print(f"   Valid OAuth Redirect URI: {oauth.redirect_uri}")
    print("   This URI should be added in your Facebook app's OAuth settings")
    print("   App Dashboard -> Settings -> Basic -> Add Platform -> Website")
    print("\nPress Enter to continue...")
    input()
    
    success = oauth.authenticate()
    
    if success:
        print("\n✅ Authentication completed successfully!")
        print(f"User Token: {oauth.user_token[:20]}..." if oauth.user_token else "No user token")
        print(f"Page ID: {oauth.page_id}")
        print(f"Page Token: {oauth.page_token[:20]}..." if oauth.page_token else "No page token")
        
        # Test a simple API call
        if oauth.page_token:
            try:
                test_url = f"https://graph.facebook.com/v20.0/{oauth.page_id}?access_token={oauth.page_token}"
                response = requests.get(test_url)
                if response.status_code == 200:
                    page_info = response.json()
                    print(f"✅ API Test successful! Page: {page_info.get('name', 'Unknown')}")
                else:
                    print(f"⚠️  API Test failed: {response.status_code} - {response.text}")
            except Exception as e:
                print(f"⚠️  API Test error: {e}")
    else:
        print("❌ Authentication failed!")
    
    return success


if __name__ == "__main__":
    test_facebook_oauth()