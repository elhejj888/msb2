import os
import requests
from dotenv import load_dotenv

class FacebookAuth:
    def __init__(self):
        load_dotenv()
        self.user_access_token = os.environ.get('FACEBOOK_USER_TOKEN')
        self.page_id = os.environ.get('FACEBOOK_PAGE_ID')
        self.page_access_token = None

    def validate_user_token(self):
        if not self.user_access_token:
            print("Error: User access token is not set.")
            return False
        
        try:
            debug_url = f'https://graph.facebook.com/debug_token?input_token={self.user_access_token}&access_token={self.user_access_token}'
            debug_response = requests.get(debug_url)
            debug_response.raise_for_status()
            debug_data = debug_response.json()
            
            if 'data' in debug_data and not debug_data['data'].get('is_valid', False):
                print("User token validation failed!")
                return False
            return True
        except Exception as e:
            print(f"Error validating user token: {e}")
            return False

    def get_page_access_token(self):
        if not self.user_access_token or not self.page_id:
            print("Error: Missing user access token or page ID")
            return None
        
        page_id = self.clean_page_id(self.page_id)
        version = 'v20.0'
        api_url = f'https://graph.facebook.com/{version}/{page_id}?fields=access_token&access_token={self.user_access_token}'
        
        try:
            response = requests.get(api_url)
            response.raise_for_status()
            data = response.json()
            return data.get('access_token')
        except requests.exceptions.RequestException as e:
            print(f"Error retrieving page token: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return None

    def clean_page_id(self, page_id):
        if 'facebook.com' in page_id:
            if 'profile.php?id=' in page_id:
                page_id = page_id.split('profile.php?id=')[1].split('&')[0]
            elif 'facebook.com/' in page_id:
                page_id = page_id.split('facebook.com/')[1].split('/')[0]
        return page_id