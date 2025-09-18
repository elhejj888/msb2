import os
import requests
import time
import json
from datetime import datetime
from .auth import XAuth
from dotenv import load_dotenv

class XManager:
    def __init__(self):
        load_dotenv()  # Load environment variables
        self.api_base_url = 'https://api.twitter.com/2'
        self.token_file = 'x_tokens.json'
        
        # Initialize authentication
        self.auth = XAuth(
            client_id=os.getenv('X_CLIENT_ID'),
            client_secret=os.getenv('X_CLIENT_SECRET'),
            redirect_uri='http://localhost:8081/callback'
        )
        
        # Load existing tokens if available
        self.load_tokens()

    def load_tokens(self):
        """Load tokens from file"""
        try:
            if os.path.exists(self.token_file):
                with open(self.token_file, 'r') as f:
                    token_data = json.load(f)
                    self.auth.access_token = token_data.get('access_token')
                    self.auth.refresh_token = token_data.get('refresh_token')
                    print("Existing X tokens loaded from file.")
                    return True
        except Exception as e:
            print(f"Error loading X tokens: {e}")
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
            print("X tokens saved successfully.")
        except Exception as e:
            print(f"Error saving X tokens: {e}")

    def ensure_authentication(self):
        """Ensure we have valid authentication"""
        if not self.auth.access_token:
            print("No X access token found. Please authenticate first.")
            return False
        
        # Test the token
        if not self.validate_credentials():
            print("X access token invalid. Attempting to refresh...")
            if self.auth.refresh_token:
                if self.auth.refresh_access_token():
                    print("X token refreshed successfully!")
                    return True
                else:
                    print("X token refresh failed. Need to re-authenticate.")
                    return False
            else:
                print("No refresh token available. Need to re-authenticate.")
                return False
        
        return True

    def start_authentication(self):
        """Start the OAuth authentication process"""
        print("Starting X (Twitter) authentication...")
        auth_code = self.auth.start_oauth_flow()
        
        if auth_code:
            success = self.auth.exchange_code_for_tokens(auth_code)
            if success:
                print("X authentication successful!")
                return True
            else:
                print("X authentication failed during token exchange.")
                return False
        else:
            print("X authentication failed during OAuth flow.")
            return False

    def validate_credentials(self):
        """Validate the current access token"""
        if not self.auth.access_token:
            return False
        
        headers = {
            'Authorization': f'Bearer {self.auth.access_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(
                f'{self.api_base_url}/users/me',
                headers=headers,
                timeout=10
            )
            is_valid = response.status_code == 200
            
            if is_valid:
                print("X access token is valid.")
                # Save the valid token
                self.save_tokens()
            else:
                print(f"X access token validation failed: {response.status_code}")
                
            return is_valid
        except Exception as e:
            print(f"Error validating X credentials: {e}")
            return False

    def upload_media(self, media_path):
        """
        Upload media file and return media ID
        
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
        print("If upload fails, consider using text-only tweets.")
        
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
                    timeout=120
                )
                
                if response.status_code == 200:
                    upload_response = response.json()
                    media_id = str(upload_response.get('media_id'))
                    print(f"Media uploaded successfully! Media ID: {media_id}")
                    return media_id
                elif response.status_code == 403:
                    print("⚠️  Media upload failed: OAuth 2.0 user context tokens don't support media upload")
                    print("💡 Creating text-only tweet instead...")
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
                
        except Exception as e:
            print(f"Error during media upload: {e}")
            return None

    def create_tweet(self, text, media_path=None, reply_to_tweet_id=None):
        """
        Create a new tweet
        
        Parameters:
        - text (str): The tweet text (max 280 characters)
        - media_path (str, optional): Path to media file to upload
        - reply_to_tweet_id (str, optional): ID of tweet to reply to
        
        Returns:
        - dict: Tweet information or None if failed
        """
        if not self.ensure_authentication():
            print("Error: X authentication failed. Cannot create tweet.")
            return None
        
        if len(text) > 280:
            print("Error: Tweet text exceeds 280 characters.")
            return None
        
        headers = {
            'Authorization': f'Bearer {self.auth.access_token}',
            'Content-Type': 'application/json'
        }
        
        tweet_data = {'text': text}
        
        # Handle media upload
        if media_path and os.path.exists(media_path):
            print(f"Preparing to upload media: {os.path.basename(media_path)}")
            media_id = self.upload_media(media_path)
            if media_id:
                tweet_data['media'] = {'media_ids': [media_id]}
                print("✅ Media will be included with tweet")
            else:
                print("❌ Media upload failed - creating text-only tweet")
        
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
                    print(f"📝 Tweet ID: {tweet_info['id']}")
                    print(f"🔗 URL: {tweet_info['url']}")
                    
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
                except:
                    print(f"Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error creating tweet: {e}")
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
            print("Error: X authentication failed. Cannot retrieve tweet.")
            return None
        
        headers = {
            'Authorization': f'Bearer {self.auth.access_token}',
            'Content-Type': 'application/json'
        }
        
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
                return None
                
        except Exception as e:
            print(f"Error retrieving tweet: {e}")
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
            print("Error: X authentication failed. Cannot retrieve tweets.")
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
        
        # Ensure max_results is between 5 and 100 as required by X API
        max_results = max(5, min(limit, 100))
        
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
                    
                    return tweets[:limit] if limit < max_results else tweets
                else:
                    print("No tweets found")
                    return []
            else:
                print(f"Error retrieving tweets: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error retrieving tweets: {e}")
            return None

    def delete_tweet(self, tweet_id):
        """
        Delete a tweet
        
        Parameters:
        - tweet_id (str): The ID of the tweet to delete
        
        Returns:
        - bool: True if successful, False otherwise
        """
        if not self.ensure_authentication():
            print("Error: X authentication failed. Cannot delete tweet.")
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
                return False
                
        except Exception as e:
            print(f"Error deleting tweet: {e}")
            return False

    def handle_rate_limit(self, response):
        """
        Handle rate limiting by checking headers and implementing retry logic
        
        Parameters:
        - response: The HTTP response object
        
        Returns:
        - int: Seconds to wait before retrying, or 0 if no rate limit
        """
        if response.status_code == 429:
            reset_time = response.headers.get('x-rate-limit-reset')
            if reset_time:
                try:
                    reset_timestamp = int(reset_time)
                    current_timestamp = int(time.time())
                    wait_time = max(0, reset_timestamp - current_timestamp + 1)
                    print(f"Rate limited. Waiting {wait_time} seconds until reset...")
                    return wait_time
                except (ValueError, TypeError):
                    pass
            
            # Fallback: wait 15 minutes
            print("Rate limited. Waiting 15 minutes...")
            return 15 * 60
        
        return 0