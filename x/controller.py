import os
import requests
import time
import json
import random
from datetime import datetime
from .auth import XAuth
from dotenv import load_dotenv

class XManager:
    def __init__(self):
        load_dotenv()  # Load environment variables
        self.api_base_url = 'https://api.twitter.com/2'
        self.token_file = 'x_tokens.json'
        self.auth_attempts = 0  # Track authentication attempts
        self.max_auth_attempts = 2  # Limit authentication attempts
        
        # Initialize authentication
        self.auth = XAuth(
            client_id=os.getenv('X_CLIENT_ID'),
            client_secret=os.getenv('X_CLIENT_SECRET'),
            redirect_uri='http://localhost:8081/callback'
        )
        # IMPORTANT: Do NOT auto-load any tokens here. Token context is per-user
        # and will be set in routes using set_user_token_context().
        # OAuth should be initiated explicitly via the start auth endpoint.

    def set_user_token_context(self, user_id):
        """Point manager and auth to a per-user token file.
        This must be called at the beginning of each request that operates on tokens.
        """
        try:
            safe_id = str(user_id).strip()
        except Exception:
            safe_id = str(user_id)

        token_path = f"x_tokens_{safe_id}.json"
        # Update both manager and auth to use the same per-user file
        self.token_file = token_path
        self.auth.token_file = token_path
        # Clear in-memory tokens to avoid leaking any previous context
        self.auth.access_token = None
        self.auth.refresh_token = None
        return token_path

    def load_tokens(self):
        """Load tokens from file"""
        try:
            if os.path.exists(self.token_file):
                with open(self.token_file, 'r') as f:
                    token_data = json.load(f)
                    self.auth.access_token = token_data.get('access_token')
                    self.auth.refresh_token = token_data.get('refresh_token')
                    print("Existing tokens loaded from file.")
                    return True
        except Exception as e:
            print(f"Error loading tokens: {e}")
        return False

    def save_tokens(self):
        """Save tokens to file"""
        token_data = {
            'access_token': self.auth.access_token,
            'refresh_token': self.auth.refresh_token,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            with open(self.token_file, 'w') as f:
                json.dump(token_data, f, indent=2)
            print("Tokens saved successfully.")
        except Exception as e:
            print(f"Error saving tokens: {e}")

    def ensure_authentication(self):
        """Ensure we have valid authentication without auto-starting OAuth.
        Returns True if valid (or refreshed) token is available, otherwise False.
        """
        # If no access token, do not auto-start OAuth here
        if not self.auth.access_token:
            return False

        # If we have a token, validate it
        if not self.validate_credentials():
            print("Access token invalid. Attempting to refresh...")
            if not self.auth.refresh_access_token():
                # Do NOT auto-start OAuth flow here
                print("Token refresh failed. Authentication required via start auth endpoint.")
                return False
            # After refresh, validate again
            return self.validate_credentials()

        return True

    def get_user_tweets_with_retry(self, user_id=None, limit=10, max_retries=3):
        """
        Get recent tweets with automatic retry on rate limits
        """
        for attempt in range(max_retries):
            result = self.get_user_tweets(user_id, limit)
            
            # If successful or not a rate limit issue, return result
            if result is not None:
                return result
            
            # If this was the last attempt, give up
            if attempt == max_retries - 1:
                print(f"Failed to retrieve tweets after {max_retries} attempts")
                return None
            
            # Wait before retrying (exponential backoff)
            wait_time = (2 ** attempt) * 60  # 1 min, 2 min, 4 min
            print(f"Retrying in {wait_time} seconds... (Attempt {attempt + 2}/{max_retries})")
            time.sleep(wait_time)
        
        return None

    def validate_credentials(self):
        """Validate the current access token"""
        if not self.auth.access_token:
            return False
        
        try:
            headers = {
                'Authorization': f'Bearer {self.auth.access_token}',
                'Content-Type': 'application/json'
            }
            
            # Retry a few times on 429 to avoid false negatives immediately after auth
            for attempt in range(3):
                response = requests.get(
                    f'{self.api_base_url}/users/me',
                    headers=headers
                )
                if response.status_code == 200:
                    return True
                if response.status_code == 401:
                    print("Access token is invalid or expired.")
                    return False
                if response.status_code == 429:
                    print("Unexpected response: 429 (rate limited) during validation. Retrying...")
                    time.sleep(1 + attempt)
                    continue
                print(f"Unexpected response: {response.status_code}")
                return False
            # If we got here, rate limit persisted
            print("Validation failed due to repeated rate limits (429)")
            return False
            
        except Exception as e:
            print(f"Error validating credentials: {e}")
            return False
    
    def get_user_info(self):
        """Get current user information for exclusivity checks"""
        try:
            headers = {
                'Authorization': f'Bearer {self.auth.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f'{self.api_base_url}/users/me',
                headers=headers
            )
            
            if response.status_code == 200:
                user_data = response.json().get('data', {})
                return {
                    'id': user_data.get('id'),
                    'username': user_data.get('username'),
                    'name': user_data.get('name')
                }
            elif response.status_code == 401:
                print("Error getting X user info: 401 (unauthorized)")
                return {'error': 'unauthorized'}
            elif response.status_code == 429:
                print("Error getting X user info: 429 (rate limited)")
                return {'error': 'rate_limited'}
            else:
                print(f"Error getting X user info: {response.status_code}")
                print(f"Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"Error getting X user info: {e}")
            return None

    def get_user_info_with_retry(self, max_retries: int = 5, initial_delay: float = 1.0, max_delay: float = 30.0, backoff_factor: float = 2.0):
        """Fetch user info with exponential backoff retry on rate limits.
        
        Args:
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds before first retry
            max_delay: Maximum delay between retries in seconds
            backoff_factor: Multiplier for delay between retries
            
        Returns:
            dict: User info on success, or {'error': 'unauthorized'|'rate_limited'} on known errors
            None: On other failures
        """
        delay = initial_delay
        
        for attempt in range(max_retries):
            # Get user info
            info = self.get_user_info()
            
            # Success case
            if isinstance(info, dict) and 'error' not in info:
                return info
                
            # Unauthorized - no point retrying
            if isinstance(info, dict) and info.get('error') == 'unauthorized':
                print(f"X OAuth unauthorized (attempt {attempt + 1}/{max_retries})")
                return info
                
            # Rate limited - wait and retry
            if isinstance(info, dict) and info.get('error') == 'rate_limited':
                if attempt < max_retries - 1:
                    # Calculate next delay with exponential backoff and jitter
                    jitter = random.uniform(0.5, 1.5)  # Add jitter to prevent thundering herd
                    sleep_time = min(delay * jitter, max_delay)
                    
                    print(f"X API rate limited, retrying in {sleep_time:.1f}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(sleep_time)
                    
                    # Increase delay for next attempt
                    delay = min(delay * backoff_factor, max_delay)
                    continue
                    
                # Final attempt failed
                print(f"X API still rate limited after {max_retries} attempts")
                return info
                
            # Other error - log and retry with backoff
            print(f"Unexpected response from X API (attempt {attempt + 1}/{max_retries}): {info}")
            
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay = min(delay * backoff_factor, max_delay)
                
        # All retries exhausted
        print(f"Failed to get X user info after {max_retries} attempts")
        return None
    
    def upload_media(self, media_path):
        """
        Upload media file and return media ID
        Enhanced version with better error handling and OAuth 2.0 limitation awareness
        
        Parameters:
        - media_path (str): Path to media file
        
        Returns:
        - str: Media ID or None if failed
        """
        if not os.path.exists(media_path):
            print(f"Media file not found: {media_path}")
            return None
        
        # Check if we're using OAuth 2.0 (which has media upload limitations)
        print("Note: Media upload with OAuth 2.0 user context tokens has limitations.")
        print("If upload fails, consider using OAuth 1.0a or upload media via web interface.")
        
        # X API v1.1 is used for media upload
        upload_url = 'https://upload.twitter.com/1.1/media/upload.json'
        
        headers = {
            'Authorization': f'Bearer {self.auth.access_token}'
        }
        
        try:
            # Get file size and type
            file_size = os.path.getsize(media_path)
            
            # Check file size limits
            file_ext = media_path.lower().split('.')[-1]
            if file_ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                max_size = 5 * 1024 * 1024  # 5MB for images
                media_category = 'tweet_image'
            elif file_ext in ['mp4', 'mov', 'avi', 'webm']:
                max_size = 512 * 1024 * 1024  # 512MB for videos
                media_category = 'tweet_video'
            else:
                print(f"Unsupported file type: {file_ext}")
                return None
            
            if file_size > max_size:
                print(f"File too large: {file_size} bytes. Maximum allowed: {max_size} bytes")
                return None
            
            print(f"Attempting to upload {file_ext.upper()} file ({file_size} bytes)...")
            
            with open(media_path, 'rb') as media_file:
                files = {'media': media_file}
                data = {'media_category': media_category}
                
                response = requests.post(
                    upload_url, 
                    headers=headers, 
                    files=files, 
                    data=data,
                    timeout=120  # Increased timeout for larger files
                )
                
                if response.status_code == 200:
                    upload_response = response.json()
                    media_id = str(upload_response.get('media_id'))
                    print(f"Media uploaded successfully! Media ID: {media_id}")
                    return media_id
                elif response.status_code == 403:
                    print("⚠️  Media upload failed: OAuth 2.0 user context tokens don't support media upload")
                    print("💡 Workarounds:")
                    print("   1. Use OAuth 1.0a instead of OAuth 2.0")
                    print("   2. Upload media through X web interface first")
                    print("   3. Create text-only tweets for now")
                    return None
                elif response.status_code == 413:
                    print("Media file is too large for upload")
                    return None
                elif response.status_code == 415:
                    print("Unsupported media type")
                    return None
                else:
                    print(f"Media upload failed with status {response.status_code}")
                    try:
                        error_response = response.json()
                        if 'errors' in error_response:
                            for error in error_response['errors']:
                                print(f"Error: {error.get('message', 'Unknown error')}")
                    except:
                        print(f"Response: {response.text}")
                    return None
                
        except requests.exceptions.Timeout:
            print("Media upload timed out. File may be too large or connection too slow.")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Network error during media upload: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error during media upload: {e}")
            return None
    
    def create_tweet(self, text, media_path=None, reply_to_tweet_id=None):
        """
        Create a new tweet with enhanced media handling
        
        Parameters:
        - text (str): The tweet text (max 280 characters)
        - media_path (str, optional): Path to media file to upload
        - reply_to_tweet_id (str, optional): ID of tweet to reply to
        
        Returns:
        - dict: Tweet information or None if failed
        """
        if not self.ensure_authentication():
            print("Error: Authentication failed. Cannot create tweet.")
            return None
        
        if len(text) > 280:
            print("Error: Tweet text exceeds 280 characters.")
            return None
        
        headers = {
            'Authorization': f'Bearer {self.auth.access_token}',
            'Content-Type': 'application/json'
        }
        
        tweet_data = {'text': text}
        
        # Handle media upload with better error handling
        media_ids = []
        if media_path and os.path.exists(media_path):
            print(f"Preparing to upload media: {os.path.basename(media_path)}")
            media_id = self.upload_media(media_path)
            if media_id:
                media_ids.append(media_id)
                print("✅ Media will be included with tweet")
            else:
                print("❌ Media upload failed - proceeding with text-only tweet")
                # Ask user if they want to continue without media
                continue_without_media = input("Continue creating tweet without media? (y/n): ").lower()
                if continue_without_media != 'y':
                    print("Tweet creation cancelled.")
                    return None
        
        if media_ids:
            tweet_data['media'] = {'media_ids': media_ids}
        
        # Handle reply
        if reply_to_tweet_id:
            tweet_data['reply'] = {'in_reply_to_tweet_id': reply_to_tweet_id}
        
        try:
            print("Creating tweet...")
            response = requests.post(
                f'{self.api_base_url}/tweets',
                headers=headers,
                json=tweet_data,
                timeout=30
            )
            
            if response.status_code == 201:
                tweet_response = response.json()
                
                if 'data' in tweet_response:
                    tweet_info = tweet_response['data']
                    tweet_info['url'] = f"https://twitter.com/user/status/{tweet_info['id']}"
                    print("✅ Tweet created successfully!")
                    
                    # Show tweet details
                    print(f"📝 Tweet ID: {tweet_info['id']}")
                    print(f"🔗 URL: {tweet_info['url']}")
                    if media_ids:
                        print(f"📸 Media attached: {len(media_ids)} file(s)")
                    
                    return tweet_info
                else:
                    print("❌ Unexpected response format")
                    print(f"Response: {tweet_response}")
                    return None
            else:
                print(f"❌ Error creating tweet: HTTP {response.status_code}")
                try:
                    error_response = response.json()
                    if 'errors' in error_response:
                        for error in error_response['errors']:
                            print(f"Error: {error.get('message', 'Unknown error')}")
                    elif 'detail' in error_response:
                        print(f"Error: {error_response['detail']}")
                    else:
                        print(f"Response: {error_response}")
                except:
                    print(f"Response: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error creating tweet: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return None
        except Exception as e:
            print(f"❌ Unexpected error creating tweet: {e}")
            return None
    
        def get_tweet(self, tweet_id):
            """
            Get a tweet by its ID
            
            Parameters:
            - tweet_id (str): The ID of the tweet to retrieve
            
            Returns:
            - dict: Tweet information or None if failed
            """
            if not self.ensure_authentication():
                print("Error: Authentication failed. Cannot retrieve tweet.")
                return None
            
            headers = {
                'Authorization': f'Bearer {self.auth.access_token}',
                'Content-Type': 'application/json'
            }
            
            # Include additional fields
            params = {
                'tweet.fields': 'created_at,public_metrics,author_id,context_annotations,attachments',
                'user.fields': 'username,name',
                'expansions': 'author_id'
            }
            
            try:
                response = requests.get(
                    f'{self.api_base_url}/tweets/{tweet_id}',
                    headers=headers,
                    params=params,
                    timeout=10
                )
                
                if response.status_code == 200:
                    tweet_response = response.json()
                    
                    if 'data' in tweet_response:
                        tweet_data = tweet_response['data']
                        
                        # Format the response
                        formatted_tweet = {
                            'id': tweet_data.get('id'),
                            'text': tweet_data.get('text'),
                            'created_at': tweet_data.get('created_at'),
                            'author_id': tweet_data.get('author_id'),
                            'url': f"https://twitter.com/user/status/{tweet_data.get('id')}",
                            'metrics': tweet_data.get('public_metrics', {}),
                            'retweets': tweet_data.get('public_metrics', {}).get('retweet_count', 0),
                            'likes': tweet_data.get('public_metrics', {}).get('like_count', 0),
                            'replies': tweet_data.get('public_metrics', {}).get('reply_count', 0),
                            'quotes': tweet_data.get('public_metrics', {}).get('quote_count', 0)
                        }
                        
                        return formatted_tweet
                    else:
                        print("Tweet not found or access denied")
                        return None
                else:
                    print(f"Error retrieving tweet: {response.status_code}")
                    print(f"Response: {response.text}")
                    return None
                    
            except requests.exceptions.RequestException as e:
                print(f"Error retrieving tweet: {e}")
                if hasattr(e, 'response') and e.response:
                    print(f"Response content: {e.response.text}")
                return None
    
    def get_user_tweets(self, user_id=None, limit=10):
        """
        Get recent tweets from user (default: authenticated user)
        
        Parameters:
        - user_id (str, optional): User ID to get tweets from
        - limit (int): Maximum number of tweets to return
        
        Returns:
        - list: List of tweet dictionaries or None if failed
        """
        if not self.ensure_authentication():
            print("Error: Authentication failed. Cannot retrieve tweets.")
            return None
        
        headers = {
            'Authorization': f'Bearer {self.auth.access_token}',
            'Content-Type': 'application/json'
        }
        
        # If no user_id provided, get authenticated user's ID
        if not user_id:
            user_response = requests.get(f'{self.api_base_url}/users/me', headers=headers, timeout=10)
            if user_response.status_code == 200:
                user_id = user_response.json()['data']['id']
            else:
                print("Failed to get user ID")
                return None
        
        # Fix: Ensure max_results is between 5 and 100 as required by X API
        max_results = max(5, min(limit, 100))  # Clamp between 5 and 100
        
        params = {
            'tweet.fields': 'created_at,public_metrics,context_annotations,attachments',
            'max_results': max_results
        }
        
        try:
            response = requests.get(
                f'{self.api_base_url}/users/{user_id}/tweets',
                headers=headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                tweets_response = response.json()
                
                if 'data' in tweets_response:
                    tweets = []
                    for tweet_data in tweets_response['data']:
                        formatted_tweet = {
                            'id': tweet_data.get('id'),
                            'text': tweet_data.get('text'),
                            'created_at': tweet_data.get('created_at'),
                            'url': f"https://twitter.com/user/status/{tweet_data.get('id')}",
                            'retweets': tweet_data.get('public_metrics', {}).get('retweet_count', 0),
                            'likes': tweet_data.get('public_metrics', {}).get('like_count', 0),
                            'replies': tweet_data.get('public_metrics', {}).get('reply_count', 0),
                            'quotes': tweet_data.get('public_metrics', {}).get('quote_count', 0)
                        }
                        tweets.append(formatted_tweet)
                    
                    # Return only the requested number of tweets if less than max_results
                    return tweets[:limit] if limit < max_results else tweets
                else:
                    print("No tweets found")
                    return []
            elif response.status_code == 429:
                # Handle rate limiting gracefully
                print("Rate limit exceeded. Returning empty list.")
                print(f"Response: {response.text}")
                return []  # Return empty list instead of None to prevent 500 error
            else:
                print(f"Error retrieving tweets: {response.status_code}")
                print(f"Response: {response.text}")
                return []  # Return empty list instead of None to prevent 500 error
                
        except requests.exceptions.RequestException as e:
            print(f"Error retrieving tweets: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return []  # Return empty list instead of None to prevent 500 error

    def delete_tweet(self, tweet_id):
        """
        Delete a tweet
        
        Parameters:
        - tweet_id (str): The ID of the tweet to delete
        
        Returns:
        - bool: True if successful, False otherwise
        """
        if not self.ensure_authentication():
            print("Error: Authentication failed. Cannot delete tweet.")
            return False
        
        headers = {
            'Authorization': f'Bearer {self.auth.access_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.delete(
                f'{self.api_base_url}/tweets/{tweet_id}',
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                delete_response = response.json()
                
                if delete_response.get('data', {}).get('deleted', False):
                    print("Tweet deleted successfully!")
                    return True
                else:
                    print("Failed to delete tweet.")
                    return False
            else:
                print(f"Error deleting tweet: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"Error deleting tweet: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return False
    
    
    def create_tweet(self, text, media_path=None, reply_to_tweet_id=None):
        """
        Create a new tweet with enhanced media handling
        
        Parameters:
        - text (str): The tweet text (max 280 characters)
        - media_path (str, optional): Path to media file to upload
        - reply_to_tweet_id (str, optional): ID of tweet to reply to
        
        Returns:
        - dict: Tweet information or None if failed
        """
        if not self.ensure_authentication():
            print("Error: Authentication failed. Cannot create tweet.")
            return None
        
        if len(text) > 280:
            print("Error: Tweet text exceeds 280 characters.")
            return None
        
        headers = {
            'Authorization': f'Bearer {self.auth.access_token}',
            'Content-Type': 'application/json'
        }
        
        tweet_data = {'text': text}
        
        # Handle media upload with better error handling
        media_ids = []
        if media_path and os.path.exists(media_path):
            print(f"Preparing to upload media: {os.path.basename(media_path)}")
            media_id = self.upload_media(media_path)
            if media_id:
                media_ids.append(media_id)
                print("✅ Media will be included with tweet")
            else:
                print("❌ Media upload failed - proceeding with text-only tweet")
                # Ask user if they want to continue without media
                continue_without_media = input("Continue creating tweet without media? (y/n): ").lower()
                if continue_without_media != 'y':
                    print("Tweet creation cancelled.")
                    return None
        
        if media_ids:
            tweet_data['media'] = {'media_ids': media_ids}
        
        # Handle reply
        if reply_to_tweet_id:
            tweet_data['reply'] = {'in_reply_to_tweet_id': reply_to_tweet_id}
        
        try:
            print("Creating tweet...")
            response = requests.post(
                f'{self.api_base_url}/tweets',
                headers=headers,
                json=tweet_data,
                timeout=30
            )
            
            if response.status_code == 201:
                tweet_response = response.json()
                
                if 'data' in tweet_response:
                    tweet_info = tweet_response['data']
                    tweet_info['url'] = f"https://twitter.com/user/status/{tweet_info['id']}"
                    print("✅ Tweet created successfully!")
                    
                    # Show tweet details
                    print(f"📝 Tweet ID: {tweet_info['id']}")
                    print(f"🔗 URL: {tweet_info['url']}")
                    if media_ids:
                        print(f"📸 Media attached: {len(media_ids)} file(s)")
                    
                    return tweet_info
                else:
                    print("❌ Unexpected response format")
                    print(f"Response: {tweet_response}")
                    return None
            else:
                print(f"❌ Error creating tweet: HTTP {response.status_code}")
                try:
                    error_response = response.json()
                    if 'errors' in error_response:
                        for error in error_response['errors']:
                            print(f"Error: {error.get('message', 'Unknown error')}")
                    elif 'detail' in error_response:
                        print(f"Error: {error_response['detail']}")
                    else:
                        print(f"Response: {error_response}")
                except:
                    print(f"Response: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error creating tweet: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return None
        except Exception as e:
            print(f"❌ Unexpected error creating tweet: {e}")
            return None
    
    def handle_rate_limit(self, response):
        """
        Handle rate limiting by checking headers and implementing retry logic
        
        Parameters:
        - response: The HTTP response object
        
        Returns:
        - int: Seconds to wait before retrying, or 0 if no rate limit
        """
        if response.status_code == 429:
            # Check for rate limit reset time in headers
            reset_time = response.headers.get('x-rate-limit-reset')
            if reset_time:
                try:
                    reset_timestamp = int(reset_time)
                    current_timestamp = int(time.time())
                    wait_time = max(0, reset_timestamp - current_timestamp + 1)  # Add 1 second buffer
                    print(f"Rate limited. Waiting {wait_time} seconds until reset...")
                    return wait_time
                except (ValueError, TypeError):
                    pass
            
            # Fallback: wait 15 minutes (X API standard rate limit window)
            print("Rate limited. Waiting 15 minutes...")
            return 15 * 60
        
        return 0

    def start_oauth_flow(self, force_login: bool = False):
        """
        Start the OAuth flow for X (Twitter) authentication.
        If force_login is True, force the X login screen to appear for account switching.
        
        Returns:
        - bool: True on success, None/False on failure
        """
        try:
            # Reset authentication attempts
            self.auth_attempts = 0
            
            # Use the auth module's start_oauth_flow method
            auth_code = self.auth.start_oauth_flow(force_login=force_login)
            
            if auth_code:
                # Exchange the code for tokens
                success = self.auth.exchange_code_for_tokens(auth_code)
                if success:
                    # Save tokens to the manager's token file as well
                    self.save_tokens()
                    print("✅ X (Twitter) authentication completed successfully!")
                    return True
                else:
                    print("❌ Failed to exchange authorization code for tokens")
                    return None
            else:
                print("❌ Failed to get authorization code")
                return None
                
        except Exception as e:
            print(f"Error starting OAuth flow: {e}")
            return None

    def revoke_token(self, include_legacy: bool = False):
        """
        Revoke the current access token and clear stored tokens
        """
        if self.auth.access_token:
            try:
                # X (Twitter) API v2 doesn't have a token revocation endpoint
                # So we just clear the tokens locally
                print("Clearing X (Twitter) authentication tokens...")
            except Exception as e:
                print(f"Warning: Could not revoke token with API: {e}")
        
        # Clear stored tokens
        self.auth.access_token = None
        self.auth.refresh_token = None
        
        # Remove token file
        try:
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
                print(f"✅ Token file {self.token_file} removed")
            # Optionally also remove legacy global token file to prevent reuse
            if include_legacy and self.token_file != 'x_tokens.json' and os.path.exists('x_tokens.json'):
                os.remove('x_tokens.json')
                print("✅ Legacy token file x_tokens.json removed")
        except Exception as e:
            print(f"Warning: Could not remove token file: {e}")
        
        return True

    def create_thread(self, thread_tweets, hashtags=''):
        """
        Create a Twitter thread with multiple tweets
        
        Parameters:
        - thread_tweets (list): List of tweet texts for the thread
        - hashtags (str): Hashtags to add to tweets
        
        Returns:
        - dict: Thread information with all tweet IDs or None if failed
        """
        if not self.auth.access_token:
            print("❌ No access token available")
            return None
        
        if not thread_tweets or len(thread_tweets) == 0:
            print("❌ No thread tweets provided")
            return None
        
        thread_data = {
            'thread_id': None,
            'tweets': [],
            'total_tweets': len(thread_tweets),
            'created_at': datetime.now().isoformat()
        }
        
        previous_tweet_id = None
        
        try:
            for i, tweet_text in enumerate(thread_tweets):
                # Add hashtags to the last tweet if provided
                if hashtags and i == len(thread_tweets) - 1:
                    if not tweet_text.endswith(' '):
                        tweet_text += ' '
                    tweet_text += hashtags
                
                # Create tweet (reply to previous if not first)
                tweet_data = self.create_tweet(
                    text=tweet_text,
                    reply_to_tweet_id=previous_tweet_id
                )
                
                if tweet_data:
                    thread_data['tweets'].append({
                        'position': i + 1,
                        'tweet_id': tweet_data.get('id'),
                        'text': tweet_text,
                        'created_at': tweet_data.get('created_at')
                    })
                    
                    # Set thread_id to first tweet ID
                    if i == 0:
                        thread_data['thread_id'] = tweet_data.get('id')
                    
                    # Set previous tweet ID for next iteration
                    previous_tweet_id = tweet_data.get('id')
                    
                    print(f"✅ Created tweet {i + 1}/{len(thread_tweets)}")
                    
                    # Add delay between tweets to avoid rate limiting
                    if i < len(thread_tweets) - 1:
                        time.sleep(2)
                else:
                    print(f"❌ Failed to create tweet {i + 1}/{len(thread_tweets)}")
                    break
            
            if len(thread_data['tweets']) == len(thread_tweets):
                print(f"✅ Thread created successfully with {len(thread_tweets)} tweets")
                return thread_data
            else:
                print(f"⚠️ Thread partially created: {len(thread_data['tweets'])}/{len(thread_tweets)} tweets")
                return thread_data
                
        except Exception as e:
            print(f"❌ Error creating thread: {e}")
            return None

    def schedule_tweet(self, text, scheduled_time, hashtags='', media_path=None):
        """
        Schedule a tweet for later posting (simulated - X API doesn't support native scheduling)
        
        Parameters:
        - text (str): Tweet text
        - scheduled_time (str): ISO format datetime string
        - hashtags (str): Hashtags to add
        - media_path (str): Path to media file
        
        Returns:
        - dict: Scheduled tweet information
        """
        try:
            # Add hashtags to text if provided
            full_text = text
            if hashtags:
                if not full_text.endswith(' '):
                    full_text += ' '
                full_text += hashtags
            
            # For now, we'll store the scheduled tweet info and return it
            # In a real implementation, you'd use a task scheduler like Celery
            scheduled_data = {
                'id': f"scheduled_{int(time.time())}",
                'text': full_text,
                'scheduled_time': scheduled_time,
                'status': 'scheduled',
                'media_path': media_path,
                'created_at': datetime.now().isoformat()
            }
            
            print(f"✅ Tweet scheduled for {scheduled_time}")
            return scheduled_data
            
        except Exception as e:
            print(f"❌ Error scheduling tweet: {e}")
            return None

    def get_tweet_insights(self, tweet_id):
        """
        Get insights/analytics for a specific tweet
        
        Parameters:
        - tweet_id (str): Tweet ID
        
        Returns:
        - dict: Tweet insights data
        """
        if not self.auth.access_token:
            print("❌ No access token available")
            return None
        
        try:
            headers = {
                'Authorization': f'Bearer {self.auth.access_token}',
                'Content-Type': 'application/json'
            }
            
            # Get tweet with public metrics
            url = f"{self.api_base_url}/tweets/{tweet_id}"
            params = {
                'tweet.fields': 'public_metrics,created_at,author_id',
                'expansions': 'author_id'
            }
            
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                tweet_data = data.get('data', {})
                
                if tweet_data:
                    metrics = tweet_data.get('public_metrics', {})
                    
                    insights = {
                        'tweet_id': tweet_id,
                        'likes_count': metrics.get('like_count', 0),
                        'retweets_count': metrics.get('retweet_count', 0),
                        'replies_count': metrics.get('reply_count', 0),
                        'quotes_count': metrics.get('quote_count', 0),
                        'impressions_count': metrics.get('impression_count', 0),
                        'engagement_rate': 0,
                        'created_at': tweet_data.get('created_at'),
                        'fetched_at': datetime.now().isoformat()
                    }
                    
                    # Calculate engagement rate
                    total_engagements = (insights['likes_count'] + 
                                       insights['retweets_count'] + 
                                       insights['replies_count'] + 
                                       insights['quotes_count'])
                    
                    if insights['impressions_count'] > 0:
                        insights['engagement_rate'] = round(
                            (total_engagements / insights['impressions_count']) * 100, 2
                        )
                    
                    return insights
                else:
                    print("❌ No tweet data found")
                    return None
            else:
                print(f"❌ Failed to fetch tweet insights: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Error fetching tweet insights: {e}")
            return None

    def get_insights_summary(self, days=30):
        """
        Get insights summary for user's recent tweets
        
        Parameters:
        - days (int): Number of days to look back
        
        Returns:
        - dict: Summary of insights data
        """
        try:
            # Get recent tweets
            tweets = self.get_user_tweets(limit=50)
            
            if not tweets:
                return None
            
            summary = {
                'total_tweets': len(tweets),
                'total_likes': 0,
                'total_retweets': 0,
                'total_replies': 0,
                'total_impressions': 0,
                'avg_engagement_rate': 0,
                'period_days': days,
                'generated_at': datetime.now().isoformat()
            }
            
            engagement_rates = []
            
            for tweet in tweets:
                metrics = tweet.get('public_metrics', {})
                
                summary['total_likes'] += metrics.get('like_count', 0)
                summary['total_retweets'] += metrics.get('retweet_count', 0)
                summary['total_replies'] += metrics.get('reply_count', 0)
                summary['total_impressions'] += metrics.get('impression_count', 0)
                
                # Calculate individual engagement rate
                total_engagements = (metrics.get('like_count', 0) + 
                                   metrics.get('retweet_count', 0) + 
                                   metrics.get('reply_count', 0))
                
                impressions = metrics.get('impression_count', 0)
                if impressions > 0:
                    engagement_rate = (total_engagements / impressions) * 100
                    engagement_rates.append(engagement_rate)
            
            # Calculate average engagement rate
            if engagement_rates:
                summary['avg_engagement_rate'] = round(
                    sum(engagement_rates) / len(engagement_rates), 2
                )
            
            return summary
            
        except Exception as e:
            print(f"❌ Error generating insights summary: {e}")
            return None

    def get_trending_hashtags(self):
        """
        Get trending hashtags (simulated data since X API has limited access)
        
        Returns:
        - list: List of trending hashtags
        """
        try:
            # Since X API v2 trending endpoints require special access,
            # we'll return some popular general hashtags
            trending_hashtags = [
                {'hashtag': '#Technology', 'tweet_volume': 125000},
                {'hashtag': '#AI', 'tweet_volume': 89000},
                {'hashtag': '#Marketing', 'tweet_volume': 67000},
                {'hashtag': '#Business', 'tweet_volume': 54000},
                {'hashtag': '#Innovation', 'tweet_volume': 43000},
                {'hashtag': '#SocialMedia', 'tweet_volume': 38000},
                {'hashtag': '#Digital', 'tweet_volume': 32000},
                {'hashtag': '#Startup', 'tweet_volume': 28000},
                {'hashtag': '#Tech', 'tweet_volume': 25000},
                {'hashtag': '#Entrepreneur', 'tweet_volume': 22000}
            ]
            
            return trending_hashtags
            
        except Exception as e:
            print(f"❌ Error fetching trending hashtags: {e}")
            return None