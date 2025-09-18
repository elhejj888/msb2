import os
import requests
from datetime import datetime
from .auth import FacebookAuth

class FacebookManager(FacebookAuth):
    def __init__(self):
        super().__init__()
        self.page_access_token = self.get_page_access_token()

    def validate_credentials(self):
        if not super().validate_user_token():
            return False
        
        if self.page_access_token:
            try:
                debug_url = f'https://graph.facebook.com/debug_token?input_token={self.page_access_token}&access_token={self.user_access_token}'
                debug_response = requests.get(debug_url)
                debug_response.raise_for_status()
                debug_data = debug_response.json()
                
                if 'data' in debug_data and not debug_data['data'].get('is_valid', False):
                    print("Page token validation failed! Attempting to refresh...")
                    self.page_access_token = self.get_page_access_token()
                    return self.page_access_token is not None
            except Exception as e:
                print(f"Error validating page token: {e}. Attempting to refresh...")
                self.page_access_token = self.get_page_access_token()
                return self.page_access_token is not None
        
        return True

    def create_post(self, message, link=None, image_path=None, scheduled_time=None):
        if not self.validate_credentials():
            print("Error: Invalid credentials. Cannot create post.")
            return None
        
        url = f'https://graph.facebook.com/v20.0/{self.page_id}/feed'
        payload = {
            'message': message,
            'access_token': self.page_access_token
        }
        
        if link:
            payload['link'] = link
        
        files = None
        if image_path and os.path.exists(image_path):
            url = f'https://graph.facebook.com/v20.0/{self.page_id}/photos'
            files = {
                'source': (os.path.basename(image_path), open(image_path, 'rb'))
            }
            payload['caption'] = message
            if 'message' in payload:
                del payload['message']
        
        if scheduled_time:
            payload['published'] = 'false'
            try:
                if isinstance(scheduled_time, str):
                    dt = datetime.strptime(scheduled_time, '%Y-%m-%dT%H:%M')
                    unix_timestamp = int(dt.timestamp())
                else:
                    unix_timestamp = int(scheduled_time)
                payload['scheduled_publish_time'] = unix_timestamp
            except Exception as e:
                print(f'Error parsing scheduled_time: {e}')
                payload['scheduled_publish_time'] = scheduled_time  # fallback
        
        try:
            if files:
                response = requests.post(url, data=payload, files=files)
                files['source'][1].close()
            else:
                response = requests.post(url, data=payload)
            
            response.raise_for_status()
            post_data = response.json()
            
            if 'id' in post_data:
                if not scheduled_time:
                    permalink = self.get_post_permalink(post_data['id'])
                    post_data['permalink'] = permalink
                else:
                    post_data['permalink'] = f"Scheduled post (ID: {post_data['id']})"
            
            print("Post created successfully!")
            return post_data
        except requests.exceptions.RequestException as e:
            print(f"Error creating post: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return None

    def get_post_permalink(self, post_id):
        url = f'https://graph.facebook.com/v20.0/{post_id}?fields=permalink_url&access_token={self.page_access_token}'
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            return data.get('permalink_url', f"https://facebook.com/{post_id}")
        except requests.exceptions.RequestException:
            return f"https://facebook.com/{post_id}"

    def read_post(self, post_id):
        if not self.validate_credentials():
            print("Error: Invalid credentials. Cannot read post.")
            return None
        
        fields = [
            'id', 'message', 'created_time', 'permalink_url',
            'full_picture', 'attachments', 'shares', 'likes.summary(true)',
            'comments.summary(true)', 'reactions.summary(true)'
        ]
        
        url = f'https://graph.facebook.com/v20.0/{post_id}?fields={",".join(fields)}&access_token={self.page_access_token}'
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            post_data = response.json()
            
            formatted_data = {
                'id': post_data.get('id'),
                'message': post_data.get('message', '[No message]'),
                'created_time': post_data.get('created_time'),
                'permalink': post_data.get('permalink_url', f'https://facebook.com/{post_id}'),
                'image_url': post_data.get('full_picture'),
                'likes': post_data.get('likes', {}).get('summary', {}).get('total_count', 0),
                'comments': post_data.get('comments', {}).get('summary', {}).get('total_count', 0),
                'shares': post_data.get('shares', {}).get('count', 0),
                'reactions': post_data.get('reactions', {}).get('summary', {}).get('total_count', 0)
            }
            
            return formatted_data
        except requests.exceptions.RequestException as e:
            print(f"Error reading post: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return None

    def get_page_posts(self, limit=10):
        if not self.validate_credentials():
            print("Error: Invalid credentials. Cannot retrieve posts.")
            return None
        
        fields = [
            'id', 'message', 'created_time', 'permalink_url',
            'full_picture', 'shares', 'likes.summary(true)',
            'comments.summary(true)'
        ]
        
        url = f'https://graph.facebook.com/v20.0/{self.page_id}/posts?fields={",".join(fields)}&limit={limit}&access_token={self.page_access_token}'
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            posts = []
            for post in data.get('data', []):
                formatted_post = {
                    'id': post.get('id'),
                    'message': post.get('message', '[No message]'),
                    'created_time': post.get('created_time'),
                    'permalink': post.get('permalink_url', f'https://facebook.com/{post.get("id")}'),
                    'image_url': post.get('full_picture'),
                    'likes': post.get('likes', {}).get('summary', {}).get('total_count', 0),
                    'comments': post.get('comments', {}).get('summary', {}).get('total_count', 0),
                    'shares': post.get('shares', {}).get('count', 0)
                }
                posts.append(formatted_post)
            
            return posts
        except requests.exceptions.RequestException as e:
            print(f"Error retrieving posts: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return None

    def update_post(self, post_id, new_message=None, link=None):
        if not self.validate_credentials():
            print("Error: Invalid credentials. Cannot update post.")
            return False
        
        if not new_message and not link:
            print("Error: Nothing to update. Provide either new_message or link.")
            return False
        
        url = f'https://graph.facebook.com/v20.0/{post_id}'
        payload = {
            'access_token': self.page_access_token
        }
        
        if new_message:
            payload['message'] = new_message
        if link:
            payload['link'] = link
        
        try:
            response = requests.post(url, data=payload)
            response.raise_for_status()
            print("Post updated successfully!")
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error updating post: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return False

    def delete_post(self, post_id):
        if not self.validate_credentials():
            print("Error: Invalid credentials. Cannot delete post.")
            return False
        
        url = f'https://graph.facebook.com/v20.0/{post_id}'
        payload = {
            'access_token': self.page_access_token
        }
        
        try:
            response = requests.delete(url, data=payload)
            response.raise_for_status()
            
            if response.json().get('success', False):
                print("Post deleted successfully!")
                return True
            else:
                print("Failed to delete post.")
                return False
        except requests.exceptions.RequestException as e:
            print(f"Error deleting post: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return False