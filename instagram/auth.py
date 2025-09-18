import os
import requests
from dotenv import load_dotenv

load_dotenv()

class InstagramAuth:
    def __init__(self):
        self.access_token = os.getenv('INSTAGRAM_ACCESS_TOKEN')
        self.user_id = os.getenv('INSTAGRAM_USER_ID')
        self.api_version = 'v18.0'
        
    def validate(self):
        if not self.access_token or not self.user_id:
            return False
            
        try:
            test_url = f'https://graph.facebook.com/{self.api_version}/{self.user_id}?fields=id,username&access_token={self.access_token}'
            test_response = requests.get(test_url)
            return test_response.status_code == 200
        except Exception:
            return False