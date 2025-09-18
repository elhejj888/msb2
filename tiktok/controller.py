import os
import requests
from datetime import datetime
from .auth import TikTokAuth
import tempfile
import mimetypes
from io import BytesIO
import time

class TikTokManager(TikTokAuth):
    def __init__(self):
        super().__init__()
        if not self.access_token:
            print("No access token found. Please authenticate first.")
            self.access_token = self.get_access_token()

    def validate_credentials(self):
        return super().validate_credentials()

    def upload_video(self, video_path, caption="", hashtags="", privacy_level=0):
        """Upload a video to TikTok"""
        if not self.validate_credentials():
            print("Error: Invalid credentials. Cannot upload video.")
            return None
        
        if not os.path.exists(video_path):
            print(f"Error: Video file not found at {video_path}")
            return None
        
        try:
            # Step 1: Initialize upload
            init_url = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            init_response = requests.post(init_url, headers=headers)
            init_response.raise_for_status()
            init_data = init_response.json()
            upload_url = init_data["data"]["upload_url"]
            
            # Step 2: Upload the video
            with open(video_path, 'rb') as video_file:
                upload_headers = {
                    "Content-Type": "video/mp4"
                }
                
                # Add retry logic for upload
                for attempt in range(3):
                    try:
                        upload_response = requests.put(
                            upload_url,
                            headers=upload_headers,
                            data=video_file,
                            timeout=60
                        )
                        
                        if upload_response.status_code in [200, 201, 204]:
                            break
                        else:
                            print(f"Upload attempt {attempt + 1} failed: {upload_response.status_code}")
                            print(upload_response.text)
                    except (requests.exceptions.RequestException, ConnectionError) as e:
                        print(f"Upload attempt {attempt + 1} error: {str(e)}")
                    
                    if attempt < 2:
                        time.sleep(2)  # Wait before retrying
                        video_file.seek(0)  # Reset file pointer
                    else:
                        print("Video upload failed after 3 attempts")
                        return None
            
            # Step 3: Create the post
            create_url = "https://open.tiktokapis.com/v2/post/publish/video/publish/"
            create_headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Process hashtags
            hashtag_list = [tag.strip() for tag in hashtags.split(",") if tag.strip()]
            
            payload = {
                "post_info": {
                    "title": caption,
                    "privacy_level": privacy_level,
                    "disable_duet": False,
                    "disable_stitch": False,
                    "disable_comment": False
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_url": upload_url
                }
            }
            
            if hashtag_list:
                payload["post_info"]["hashtags"] = hashtag_list
            
            create_response = requests.post(
                create_url,
                headers=create_headers,
                json=payload
            )
            create_response.raise_for_status()
            
            return create_response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Error uploading video: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return None
        except Exception as e:
            print(f"Error in video upload process: {e}")
            return None

    def get_user_videos(self, limit=10):
        """Get user's videos"""
        if not self.validate_credentials():
            print("Error: Invalid credentials. Cannot get videos.")
            return None
        
        try:
            url = "https://open.tiktokapis.com/v2/post/publish/videos/list/"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            params = {
                "max_count": limit
            }
            
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json().get("data", {}).get("videos", [])
            
        except requests.exceptions.RequestException as e:
            print(f"Error getting user videos: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return None

    def get_video_info(self, video_id):
        """Get details for a specific video"""
        if not self.validate_credentials():
            print("Error: Invalid credentials. Cannot get video details.")
            return None
        
        try:
            url = f"https://open.tiktokapis.com/v2/post/publish/videos/get/?video_id={video_id}"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json().get("data", {}).get("video", {})
            
        except requests.exceptions.RequestException as e:
            print(f"Error getting video info: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return None

    def delete_video(self, video_id):
        """Delete a video"""
        if not self.validate_credentials():
            print("Error: Invalid credentials. Cannot delete video.")
            return False
        
        try:
            url = f"https://open.tiktokapis.com/v2/post/publish/videos/delete/"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "video_id": video_id
            }
            
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json().get("data", {}).get("success", False)
            
        except requests.exceptions.RequestException as e:
            print(f"Error deleting video: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return False

    def get_user_info(self):
        """Get basic user information for exclusivity checks"""
        if not self.validate_credentials():
            print("Error: Invalid credentials. Cannot get user info.")
            return None
        
        try:
            url = "https://open.tiktokapis.com/v2/user/info/"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            params = {
                "fields": "open_id,union_id,avatar_url,display_name"
            }
            
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            user_data = response.json().get("data", {}).get("user", {})
            
            # Return standardized format for exclusivity logic
            return {
                'id': user_data.get('open_id'),
                'username': user_data.get('display_name'),
                'name': user_data.get('display_name')
            }
            
        except requests.exceptions.RequestException as e:
            print(f"Error getting TikTok user info: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return None

    def refresh_connection(self):
        """Refresh the connection by getting a new access token"""
        if not self.refresh_token:
            print("No refresh token available")
            return False
        
        try:
            response = requests.post(
                "https://open.tiktokapis.com/v2/oauth/token/",
                headers={
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={
                    "client_key": self.client_key,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token
                }
            )
            response.raise_for_status()
            token_data = response.json()
            
            self._save_tokens(
                token_data["access_token"],
                token_data.get("refresh_token"),
                token_data.get("expires_in")
            )
            print("✅ Connection refreshed successfully")
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error refreshing connection: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return False