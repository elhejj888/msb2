import os
import time
from datetime import datetime
from pathlib import Path
import praw
import prawcore.exceptions
from .auth import RedditAuth

class RedditManager:
    def __init__(self):
        self.auth = RedditAuth()
        self.reddit = None
        self.authenticated = False
        self.current_user_id = None
        # Don't auto-authenticate on initialization
        # Authentication should only happen when user clicks connect

    def _credentials_path_for_user(self, user_id):
        """Return a per-user credentials path to avoid global token sharing"""
        base = Path(__file__).resolve().parent.parent / 'instance' / 'reddit_tokens'
        base.mkdir(parents=True, exist_ok=True)
        return base / f"{user_id}.json"

    def configure_for_user(self, user_id):
        """Configure auth to use per-user credentials path"""
        self.current_user_id = user_id
        creds_path = self._credentials_path_for_user(user_id)
        # Persist to file so silent restore works per user
        self.auth = RedditAuth(credentials_path=creds_path, persist_to_file=True)

    def _initialize_connection(self):
        """Initialize connection if credentials exist"""
        try:
            if self.auth.load_credentials():
                self.authenticated = self.auth.authenticate()
                if self.authenticated:
                    self.reddit = self.auth.reddit
                    print("Automatically connected using saved credentials")
        except Exception as e:
            print(f"Error initializing connection: {e}")
            self.authenticated = False
            self.reddit = None
    
    def _check_existing_credentials(self):
        """Check if we have valid existing credentials without triggering OAuth"""
        try:
            saved_creds = self.auth.load_credentials()
            if saved_creds:
                # Try to create Reddit instance with saved credentials
                self.reddit = praw.Reddit(
                    client_id=self.auth.client_id,
                    client_secret=self.auth.client_secret,
                    refresh_token=saved_creds['refresh_token'],
                    user_agent="RedditCRUDAutomation/1.0"
                )
                # Test the connection
                self.reddit.user.me()
                self.authenticated = True
                print("Found valid saved credentials")
            else:
                print("No saved credentials found")
        except Exception as e:
            print(f"Saved credentials invalid or expired: {e}")
            self.authenticated = False
            self.reddit = None
    
    def connect_reddit_account(self, user_id=None):
        """Manually trigger Reddit authentication for a specific app user"""
        try:
            if user_id is not None:
                self.configure_for_user(user_id)
            if self.auth.authenticate():
                self.reddit = self.auth.reddit
                self.authenticated = True
                return True, "Successfully connected to Reddit!"
            else:
                return False, "Failed to connect to Reddit. Please try again."
        except Exception as e:
            return False, f"Authentication error: {str(e)}"
    
    def is_authenticated(self):
        """Check if user is authenticated"""
        return self.authenticated and self.reddit is not None
    
    def get_user_info(self):
        """Get current user information for exclusivity checks"""
        self._ensure_authenticated()
        try:
            user = self.reddit.user.me()
            return {
                'id': user.id,
                'name': user.name,  # Reddit uses 'name' for username
                'username': user.name
            }
        except Exception as e:
            print(f"Error getting Reddit user info: {e}")
            return None
    
    def get_connection_status(self):
        """Get current connection status"""
        if self.authenticated:
            try:
                username = self.reddit.user.me().name
                return {
                    'connected': True,
                    'username': username,
                    'message': f"Connected as u/{username}"
                }
            except:
                self.authenticated = False
                return {
                    'connected': False,
                    'username': None,
                    'message': "Connection expired. Please reconnect."
                }
        
        # Try to restore connection using saved credentials (without OAuth flow)
        if self.auth.load_credentials():
            if self.auth.try_restore_connection():
                self.authenticated = True
                self.reddit = self.auth.reddit
                try:
                    username = self.reddit.user.me().name
                    return {
                        'connected': True,
                        'username': username,
                        'message': f"Connected as u/{username}"
                    }
                except:
                    self.authenticated = False
                    return {
                        'connected': False,
                        'username': None,
                        'message': "Connection expired. Please reconnect."
                    }
            else:
                return {
                    'connected': False,
                    'username': None,
                    'message': "Credentials found but expired. Click Connect to re-authenticate."
                }
        
        return {
            'connected': False,
            'username': None,
            'message': "Not connected to Reddit"
        }
    
    def disconnect_reddit_account(self, user_id=None):
        """Disconnect from Reddit and clear credentials for a specific user"""
        try:
            if user_id is not None:
                self.configure_for_user(user_id)
            if self.auth.credentials_file and self.auth.credentials_file.exists():
                self.auth.credentials_file.unlink()
            self.authenticated = False
            self.reddit = None
            return True, "Successfully disconnected from Reddit"
        except Exception as e:
            return False, f"Error disconnecting: {str(e)}"
    
    def _ensure_authenticated(self):
        """Helper method to check authentication before API calls"""
        if not self.is_authenticated():
            raise Exception("Not authenticated. Please connect your Reddit account first.")
    
    def validate_subreddit(self, subreddit_name):
        self._ensure_authenticated()
        try:
            clean_name = subreddit_name.strip()
            if clean_name.startswith('r/'):
                clean_name = clean_name[2:]
                
            subreddit = self.reddit.subreddit(clean_name)
            
            try:
                next(subreddit.new(limit=1), None)
                display_name = subreddit.display_name
                print(f"Subreddit r/{display_name} exists and is accessible.")
                return True, clean_name
            except prawcore.exceptions.Redirect:
                print(f"Subreddit r/{clean_name} exists but appears to be private or empty.")
                return False, clean_name
            except StopIteration:
                print(f"Subreddit r/{clean_name} exists but has no posts.")
                return True, clean_name
            
        except prawcore.exceptions.NotFound:
            print(f"Subreddit r/{clean_name} doesn't exist.")
            return False, clean_name
        except prawcore.exceptions.Redirect:
            print(f"Subreddit r/{clean_name} doesn't exist or is not accessible.")
            return False, clean_name
        except Exception as e:
            print(f"Error accessing subreddit r/{clean_name}: {e}")
            return False, clean_name
        
    def create_post(self, subreddit_name, title, content, image_path=None, flair_id=None, is_spoiler=False, nsfw=False):
        self._ensure_authenticated()
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            
            if image_path and os.path.exists(image_path):
                submission = subreddit.submit_image(
                    title=title,
                    image_path=image_path,
                    flair_id=flair_id,
                    nsfw=nsfw,
                    spoiler=is_spoiler
                )
                print(f"Successfully created image post on Reddit: {submission.url}")
            else:
                if image_path and not os.path.exists(image_path):
                    print(f"Warning: Image file {image_path} not found. Creating text post instead.")
                    
                submission = subreddit.submit(
                    title=title,
                    selftext=content,
                    flair_id=flair_id,
                    nsfw=nsfw,
                    spoiler=is_spoiler
                )
                print(f"Successfully created text post on Reddit: {submission.url}")
                
            return submission
        except prawcore.exceptions.Forbidden:
            print(f"Error: You don't have permission to post in r/{subreddit_name}.")
            return None
        except prawcore.exceptions.ServerError:
            print("Error: Reddit servers are currently experiencing issues. Please try again later.")
            return None
        except Exception as e:
            print(f"Error creating post on Reddit: {e}")
            return None
    
    def read_post(self, post_id=None, post_url=None):
        self._ensure_authenticated()
        try:
            if post_id:
                submission = self.reddit.submission(id=post_id)
            elif post_url:
                submission = self.reddit.submission(url=post_url)
            else:
                print("Error: Either post_id or post_url must be provided")
                return None
            
            try:
                submission.comments.replace_more(limit=0)
                comments = [{"author": comment.author.name if comment.author else "[deleted]",
                            "body": comment.body,
                            "score": comment.score,
                            "created_utc": datetime.fromtimestamp(comment.created_utc).strftime('%Y-%m-%d %H:%M:%S')}
                           for comment in submission.comments.list()[:10]]
            except Exception as e:
                print(f"Warning: Unable to retrieve comments: {e}")
                comments = []
            
            post_data = {
                "id": submission.id,
                "url": submission.url,
                "permalink": f"https://www.reddit.com{submission.permalink}",
                "title": submission.title,
                "author": submission.author.name if submission.author else "[deleted]",
                "content": submission.selftext,
                "score": submission.score,
                "upvote_ratio": submission.upvote_ratio,
                "created_utc": datetime.fromtimestamp(submission.created_utc).strftime('%Y-%m-%d %H:%M:%S'),
                "num_comments": submission.num_comments,
                "subreddit": submission.subreddit.display_name,
                "comments": comments
            }
            
            print(f"Successfully read post: {submission.title}")
            return post_data
        except prawcore.exceptions.NotFound:
            print("Error: Post not found.")
            return None
        except prawcore.exceptions.Forbidden:
            print("Error: You don't have permission to access this post.")
            return None
        except Exception as e:
            print(f"Error reading post from Reddit: {e}")
            return None
    
    def update_post(self, post_id=None, post_url=None, new_content=None, mark_nsfw=None, mark_spoiler=None):
        self._ensure_authenticated()
        try:
            if post_id:
                submission = self.reddit.submission(id=post_id)
            elif post_url:
                submission = self.reddit.submission(url=post_url)
            else:
                print("Error: Either post_id or post_url must be provided")
                return False
            
            if submission.author != self.reddit.user.me():
                print("Error: You can only edit your own posts")
                return False
            
            if new_content is not None:
                submission.edit(new_content)
                print(f"Post content updated successfully")
            
            if mark_nsfw is not None:
                if mark_nsfw:
                    submission.mark_nsfw()
                    print("Post marked as NSFW")
                else:
                    submission.unmark_nsfw()
                    print("Post unmarked as NSFW")
            
            if mark_spoiler is not None:
                if mark_spoiler:
                    submission.spoiler()
                    print("Post marked as spoiler")
                else:
                    submission.unspoiler()
                    print("Post unmarked as spoiler")
            
            print(f"Successfully updated post: {submission.url}")
            return True
        except prawcore.exceptions.Forbidden:
            print("Error: You don't have permission to edit this post.")
            return False
        except Exception as e:
            print(f"Error updating post on Reddit: {e}")
            return False
    
    def delete_post(self, post_id=None, post_url=None):
        self._ensure_authenticated()
        try:
            if post_id:
                submission = self.reddit.submission(id=post_id)
            elif post_url:
                submission = self.reddit.submission(url=post_url)
            else:
                print("Error: Either post_id or post_url must be provided")
                return False
            
            if submission.author != self.reddit.user.me():
                print("Error: You can only delete your own posts")
                return False
            
            post_title = submission.title
            submission.delete()
            
            print(f"Successfully deleted post: '{post_title}'")
            return True
        except prawcore.exceptions.Forbidden:
            print("Error: You don't have permission to delete this post.")
            return False
        except Exception as e:
            print(f"Error deleting post from Reddit: {e}")
            return False
    
    def get_user_posts(self, username=None, limit=20):
        self._ensure_authenticated()
        try:
            if username:
                user = self.reddit.redditor(username)
            else:
                user = self.reddit.user.me()
            
            posts = []
            try:
                for submission in user.submissions.new(limit=limit):
                    post_data = {
                        "id": submission.id,
                        "url": submission.url,
                        "permalink": f"https://www.reddit.com{submission.permalink}",
                        "title": submission.title,
                        "subreddit": submission.subreddit.display_name,
                        "score": submission.score,
                        "created_utc": datetime.fromtimestamp(submission.created_utc).strftime('%Y-%m-%d %H:%M:%S'),
                        "num_comments": submission.num_comments,
                        "submission": submission
                    }
                    posts.append(post_data)
            except prawcore.exceptions.NotFound:
                print(f"Error: User '{username}' not found.")
                return []
                
            if username:
                print(f"Successfully retrieved {len(posts)} posts by user '{username}'")
            else:
                print(f"Successfully retrieved {len(posts)} of your posts")
            
            return posts
        except prawcore.exceptions.NotFound:
            print(f"Error: User '{username}' not found.")
            return []
        except Exception as e:
            print(f"Error retrieving user posts from Reddit: {e}")
            return []
    
    def get_subreddit_posts(self, subreddit_name, limit=20):
        self._ensure_authenticated()
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            
            posts = []
            try:
                for submission in subreddit.new(limit=limit):
                    post_data = {
                        "id": submission.id,
                        "url": submission.url,
                        "permalink": f"https://www.reddit.com{submission.permalink}",
                        "title": submission.title,
                        "author": submission.author.name if submission.author else "[deleted]",
                        "score": submission.score,
                        "created_utc": datetime.fromtimestamp(submission.created_utc).strftime('%Y-%m-%d %H:%M:%S'),
                        "num_comments": submission.num_comments,
                    }
                    posts.append(post_data)
            except prawcore.exceptions.Redirect:
                print(f"Error: Cannot access posts in r/{subreddit_name}. The subreddit might be private, restricted, or empty.")
                return []
            
            if not posts:
                print(f"No posts found in r/{subreddit_name}. The subreddit might be empty.")
            else:
                print(f"Successfully retrieved {len(posts)} posts from r/{subreddit_name}")
            
            return posts
        except prawcore.exceptions.Redirect:
            print(f"Error: Subreddit r/{subreddit_name} doesn't exist or is not accessible.")
            return []
        except prawcore.exceptions.Forbidden:
            print(f"Error: You don't have permission to access r/{subreddit_name}.")
            return []
        except Exception as e:
            print(f"Error retrieving posts from r/{subreddit_name}: {e}")
            return []
    
    def comment_on_post(self, post_id=None, post_url=None, comment_text=""):
        self._ensure_authenticated()
        try:
            if post_id:
                submission = self.reddit.submission(id=post_id)
            elif post_url:
                submission = self.reddit.submission(url=post_url)
            else:
                print("Error: Either post_id or post_url must be provided")
                return None
            
            comment = submission.reply(comment_text)
            
            print(f"Successfully commented on post: {submission.title}")
            return comment.id
        except prawcore.exceptions.Forbidden:
            print("Error: You don't have permission to comment on this post.")
            return None
        except Exception as e:
            print(f"Error commenting on Reddit post: {e}")
            return None