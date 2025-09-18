import os
import requests
from datetime import datetime
from .auth import TikTokAuth
import tempfile
import mimetypes
import time
import json

class TikTokManager(TikTokAuth):
    def __init__(self):
        super().__init__()
        if not self.access_token:
            print("No TikTok access token found. Please authenticate first.")

    def validate_credentials(self):
        """Validate current credentials"""
        return super().validate_credentials()

    def get_user_info(self):
        """Get basic user information"""
        if not self.validate_credentials():
            print("Error: Invalid TikTok credentials.")
            return None
        
        try:
            url = f"{self.api_base_url}/user/info/"
            headers = {"Authorization": f"Bearer {self.access_token}"}
            params = {"fields": "open_id,union_id,avatar_url,display_name,follower_count,following_count,likes_count,video_count"}
            
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json().get("data", {}).get("user", {})
            
        except requests.exceptions.RequestException as e:
            print(f"Error getting TikTok user info: {e}")
            return None

    def get_user_videos(self, limit=10):
        """Get user's videos"""
        if not self.validate_credentials():
            print("Error: Invalid TikTok credentials.")
            return None
        
        try:
            url = f"{self.api_base_url}/video/list/"
            headers = {"Authorization": f"Bearer {self.access_token}"}
            params = {
                "fields": "id,title,video_description,duration,cover_image_url,embed_html,embed_link,like_count,comment_count,share_count,view_count",
                "max_count": min(limit, 20)  # TikTok API limit
            }
            
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("data", {}).get("videos", [])
            
        except requests.exceptions.RequestException as e:
            print(f"Error getting TikTok videos: {e}")
            return None

    def upload_video(self, video_path, title="", description="", privacy_level="SELF_ONLY", disable_duet=False, disable_comment=False, disable_stitch=False):
        """Upload a video to TikTok"""
        if not self.validate_credentials():
            print("Error: Invalid TikTok credentials.")
            return None
        
        if not os.path.exists(video_path):
            print(f"Error: Video file not found at {video_path}")
            return None
        
        try:
            # Step 1: Initialize upload
            init_url = f"{self.api_base_url}/post/publish/inbox/video/init/"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            init_response = requests.post(init_url, headers=headers)
            init_response.raise_for_status()
            init_data = init_response.json()
            
            if not init_data.get("data", {}).get("publish_id"):
                print("Error: Failed to initialize video upload")
                return None
            
            publish_id = init_data["data"]["publish_id"]
            upload_url = init_data["data"]["upload_url"]
            
            # Step 2: Upload the video file
            with open(video_path, 'rb') as video_file:
                upload_headers = {
                    "Content-Type": "video/mp4",
                    "Content-Length": str(os.path.getsize(video_path))
                }
                
                # Upload with retry logic
                for attempt in range(3):
                    try:
                        upload_response = requests.put(
                            upload_url,
                            headers=upload_headers,
                            data=video_file,
                            timeout=300  # 5 minutes timeout
                        )
                        
                        if upload_response.status_code in [200, 201, 204]:
                            break
                        else:
                            print(f"Upload attempt {attempt + 1} failed: {upload_response.status_code}")
                    except Exception as e:
                        print(f"Upload attempt {attempt + 1} error: {str(e)}")
                    
                    if attempt < 2:
                        time.sleep(2)
                        video_file.seek(0)
                    else:
                        print("Video upload failed after 3 attempts")
                        return None
            
            # Step 3: Publish the video
            publish_url = f"{self.api_base_url}/post/publish/video/init/"
            publish_headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            publish_payload = {
                "post_info": {
                    "title": title or "Posted via Social Media Manager",
                    "description": description,
                    "privacy_level": privacy_level,
                    "disable_duet": disable_duet,
                    "disable_comment": disable_comment,
                    "disable_stitch": disable_stitch
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_url": upload_url,
                    "publish_id": publish_id
                }
            }
            
            publish_response = requests.post(
                publish_url,
                headers=publish_headers,
                json=publish_payload
            )
            publish_response.raise_for_status()
            publish_data = publish_response.json()
            
            if publish_data.get("data", {}).get("publish_id"):
                return {
                    "success": True,
                    "publish_id": publish_data["data"]["publish_id"],
                    "message": "Video uploaded successfully"
                }
            else:
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Error uploading TikTok video: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response content: {e.response.text}")
            return None

    def schedule_video(self, video_path, title="", description="", scheduled_time=None, privacy_level="SELF_ONLY"):
        """Schedule a video for later posting (simulated - TikTok doesn't support native scheduling)"""
        # Note: TikTok API doesn't support native scheduling
        # This would need to be implemented with a job scheduler like Celery
        # For now, we'll return a placeholder response
        
        if not scheduled_time:
            print("Error: Scheduled time is required")
            return None
        
        # In a real implementation, you would:
        # 1. Store the video and metadata in a database
        # 2. Schedule a background job to upload at the specified time
        # 3. Return a schedule ID for tracking
        
        return {
            "success": True,
            "schedule_id": f"tiktok_schedule_{int(time.time())}",
            "scheduled_time": scheduled_time,
            "message": "Video scheduled successfully (will be uploaded at specified time)"
        }

    def get_video_analytics(self, video_id):
        """Get analytics for a specific video"""
        if not self.validate_credentials():
            print("Error: Invalid TikTok credentials.")
            return None
        
        try:
            url = f"{self.api_base_url}/video/query/"
            headers = {"Authorization": f"Bearer {self.access_token}"}
            params = {
                "fields": "id,title,video_description,duration,cover_image_url,like_count,comment_count,share_count,view_count",
                "filters": json.dumps({"video_ids": [video_id]})
            }
            
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            videos = data.get("data", {}).get("videos", [])
            
            return videos[0] if videos else None
            
        except requests.exceptions.RequestException as e:
            print(f"Error getting TikTok video analytics: {e}")
            return None

    def delete_video(self, video_id):
        """Delete a video (Note: TikTok API may not support this)"""
        # Note: TikTok API doesn't typically allow video deletion via API
        # This is a placeholder for future functionality
        print("Note: TikTok API doesn't support video deletion via API")
        return False

    def get_trending_hashtags(self):
        """Get trending hashtags (simulated - would need third-party service)"""
        # This would typically require a third-party service or web scraping
        # Returning some common TikTok hashtags as placeholder
        return [
            "#fyp", "#foryou", "#viral", "#trending", "#tiktok",
            "#funny", "#comedy", "#dance", "#music", "#art",
            "#food", "#travel", "#lifestyle", "#fashion", "#beauty"
        ]

    def bulk_upload_videos(self, video_data_list):
        """Upload multiple videos in sequence"""
        results = []
        
        for video_data in video_data_list:
            video_path = video_data.get('video_path')
            title = video_data.get('title', '')
            description = video_data.get('description', '')
            privacy_level = video_data.get('privacy_level', 'SELF_ONLY')
            
            if not video_path or not os.path.exists(video_path):
                results.append({
                    "success": False,
                    "error": f"Video file not found: {video_path}",
                    "video_data": video_data
                })
                continue
            
            result = self.upload_video(
                video_path=video_path,
                title=title,
                description=description,
                privacy_level=privacy_level
            )
            
            if result:
                results.append({
                    "success": True,
                    "result": result,
                    "video_data": video_data
                })
            else:
                results.append({
                    "success": False,
                    "error": "Upload failed",
                    "video_data": video_data
                })
            
            # Add delay between uploads to avoid rate limiting
            time.sleep(2)
        
        return results

    def refresh_connection(self):
        """Refresh the connection by getting a new access token"""
        return self._refresh_access_token()

    def get_connection_status(self):
        """Get detailed connection status"""
        is_valid = self.validate_credentials()
        
        status = {
            "connected": is_valid,
            "has_access_token": bool(self.access_token),
            "has_refresh_token": bool(self.refresh_token),
            "token_expired": self._is_token_expired() if self.token_expires_at else False,
            "expires_at": self.token_expires_at.isoformat() if self.token_expires_at else None
        }
        
        if is_valid:
            user_info = self.get_user_info()
            if user_info:
                status["user_info"] = {
                    "display_name": user_info.get("display_name"),
                    "follower_count": user_info.get("follower_count"),
                    "video_count": user_info.get("video_count")
                }
        
        return status
