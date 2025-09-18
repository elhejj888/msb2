import os
import requests
from datetime import datetime
from .auth import TikTokAuth
import tempfile
import mimetypes
from io import BytesIO
import time
import traceback

class TikTokManager:
    def __init__(self):
        # Use the TikTokAuth class for authentication instead of inheriting
        self.auth = TikTokAuth()
        
    @property
    def access_token(self):
        """Get the current access token from the auth class"""
        return self.auth.get_access_token()

    def validate_credentials(self):
        """Validate if current credentials are working"""
        return self.auth.validate_credentials()

    def revoke_token(self):
        """Revoke the current token"""
        return self.auth.revoke_token()

    def refresh_connection(self):
        """Refresh the connection by getting a new access token"""
        return self.auth.refresh_access_token()

    def get_creator_info(self):
        """Get creator info - required before posting (per TikTok docs)"""
        print("👤 Getting creator info...")
        
        try:
            url = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json; charset=UTF-8"
            }
            
            response = requests.post(url, headers=headers, timeout=30)
            print(f"📊 Creator info response status: {response.status_code}")
            print(f"📄 Creator info response: {response.text}")
            
            if response.status_code == 200:
                response_data = response.json()
                creator_info = response_data.get('data', {})
                print(f"✅ Creator info retrieved: {creator_info}")
                return creator_info
            else:
                print(f"❌ Failed to get creator info: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Error getting creator info: {e}")
            return None

    def upload_video(self, video_path, caption="", hashtags="", privacy_level=0):
        """Upload a video to TikTok using Direct Post API (immediate publishing)"""
        print(f"🎬 Starting video upload process...")
        
        if not self.validate_credentials():
            error_msg = "Invalid credentials. Cannot upload video."
            print(f"❌ {error_msg}")
            return None
        
        if not os.path.exists(video_path):
            error_msg = f"Video file not found at {video_path}"
            print(f"❌ {error_msg}")
            return None
        
        file_size = os.path.getsize(video_path)
        file_size_mb = file_size / (1024*1024)
        print(f"📊 Video file size: {file_size_mb:.2f} MB")
        
        try:
            # Step 0: Get creator info (required by TikTok API)
            print("👤 Step 0: Getting creator info...")
            creator_info = self.get_creator_info()
            if not creator_info:
                print("⚠️ Could not get creator info, proceeding anyway...")
            
            # Step 1: Initialize Direct Post (NOT inbox)
            print("🚀 Step 1: Initializing Direct Post...")
            init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json; charset=UTF-8"
            }
            
            # Process hashtags
            hashtag_list = []
            if hashtags:
                hashtag_list = [tag.strip().lstrip('#') for tag in hashtags.split(",") if tag.strip()]
                print(f"🏷️ Processed hashtags: {hashtag_list}")
            
            # Convert privacy_level to the correct string format
            privacy_mapping = {
                0: "PUBLIC_TO_EVERYONE",
                1: "MUTUAL_FOLLOW_FRIENDS",  # Fixed: was MUTUAL_FOLLOW_FRIEND
                2: "SELF_ONLY"
            }
            
            privacy_level_int = int(privacy_level) if isinstance(privacy_level, str) else privacy_level
            privacy_level_string = privacy_mapping.get(privacy_level_int, "PUBLIC_TO_EVERYONE")
            
            # Convert privacy_level based on creator info and app status
            privacy_mapping = {
                0: "PUBLIC_TO_EVERYONE",
                1: "MUTUAL_FOLLOW_FRIENDS",
                2: "SELF_ONLY"
            }
            
            privacy_level_int = int(privacy_level) if isinstance(privacy_level, str) else privacy_level
            privacy_level_string = privacy_mapping.get(privacy_level_int, "PUBLIC_TO_EVERYONE")
            
            # Check what privacy levels are allowed for this creator
            allowed_privacy_levels = creator_info.get('privacy_level_options', []) if creator_info else []
            print(f"📋 Allowed privacy levels: {allowed_privacy_levels}")
            
            # If requested privacy level is not allowed, use the most restrictive available
            if privacy_level_string not in allowed_privacy_levels and allowed_privacy_levels:
                original_privacy = privacy_level_string
                if "SELF_ONLY" in allowed_privacy_levels:
                    privacy_level_string = "SELF_ONLY"
                elif "MUTUAL_FOLLOW_FRIENDS" in allowed_privacy_levels:
                    privacy_level_string = "MUTUAL_FOLLOW_FRIENDS"
                elif "PUBLIC_TO_EVERYONE" in allowed_privacy_levels:
                    privacy_level_string = "PUBLIC_TO_EVERYONE"
                
                print(f"⚠️ WARNING: Requested privacy '{original_privacy}' not allowed. Using '{privacy_level_string}' instead.")
                print("💡 TIP: Unaudited TikTok apps can only post privately. Apply for app review to enable public posting.")
            
            print(f"🔒 Privacy mapping: {privacy_level} -> {privacy_level_int} -> {privacy_level_string}")
            
            # Build title with hashtags included (TikTok format)
            title = caption if caption else "Video"
            if hashtag_list:
                hashtags_text = " ".join([f"#{tag}" for tag in hashtag_list])
                title = f"{title} {hashtags_text}".strip()
            
            print(f"📝 Final title: {title}")
            
            # FIXED: Use Direct Post format (immediate publishing)
            init_payload = {
                "post_info": {
                    "title": title,
                    "privacy_level": privacy_level_string,
                    "disable_duet": False,
                    "disable_comment": False,
                    "disable_stitch": False,
                    "video_cover_timestamp_ms": 1000  # Cover frame at 1 second
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": file_size,
                    "chunk_size": file_size,
                    "total_chunk_count": 1
                }
            }
            
            print(f"📋 Init payload: {init_payload}")
            
            init_response = requests.post(init_url, headers=headers, json=init_payload, timeout=30)
            print(f"📊 Init response status: {init_response.status_code}")
            print(f"📄 Init response: {init_response.text}")
            
            if init_response.status_code != 200:
                try:
                    error_data = init_response.json()
                    error_message = error_data.get('error', {}).get('message', 'Unknown error')
                    error_code = error_data.get('error', {}).get('code', '')
                    
                    # Handle rate limiting
                    if 'spam_risk' in error_code or 'too_many' in error_message:
                        return {
                            'error': 'rate_limited',
                            'message': 'TikTok is temporarily rate limiting uploads. Please wait 15-30 minutes before trying again.',
                            'code': error_code
                        }
                    
                    return {
                        'error': 'init_failed',
                        'message': f"Upload initialization failed: {error_message}",
                        'code': error_code
                    }
                except:
                    return {
                        'error': 'init_failed',
                        'message': f"Upload initialization failed: {init_response.status_code}"
                    }
            
            init_data = init_response.json()
            upload_url = init_data["data"]["upload_url"]
            publish_id = init_data["data"].get("publish_id")
            print(f"🔗 Upload URL obtained")
            print(f"🆔 Publish ID: {publish_id}")
            
            # Step 2: Upload the video file
            print("📤 Step 2: Uploading video file...")
            
            with open(video_path, 'rb') as video_file:
                video_content = video_file.read()
                
                upload_headers = {
                    "Content-Type": "video/mp4",
                    "Content-Length": str(file_size),
                    "Content-Range": f"bytes 0-{file_size-1}/{file_size}",
                }
                
                timeout_seconds = max(120, int(file_size_mb / 10 * 60))
                
                upload_response = requests.put(
                    upload_url,
                    headers=upload_headers,
                    data=video_content,
                    timeout=timeout_seconds
                )
                
                print(f"📊 Upload response status: {upload_response.status_code}")
                
                if upload_response.status_code not in [200, 201, 204]:
                    return {
                        'error': 'upload_failed',
                        'message': f"Video upload failed: {upload_response.status_code} - {upload_response.text}"
                    }
            
            print("✅ Video file uploaded successfully!")
            
            # Step 3: Check post status (Direct Post publishes automatically)
            print("📊 Step 3: Checking post status...")
            return self.check_post_status(publish_id)
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"💥 {error_msg}")
            print(f"📍 Traceback: {traceback.format_exc()}")
            return {
                'error': 'unexpected_error',
                'message': error_msg
            }

    def check_post_status(self, publish_id):
        """Check the status of a post using the publish_id"""
        print(f"🔍 Checking post status for ID: {publish_id}")
        
        try:
            url = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json; charset=UTF-8"
            }
            
            payload = {
                "publish_id": publish_id
            }
            
            # Poll for status (TikTok processing can take time)
            max_attempts = 10
            wait_time = 3
            
            for attempt in range(max_attempts):
                print(f"📡 Status check attempt {attempt + 1}/{max_attempts}")
                
                response = requests.post(url, headers=headers, json=payload, timeout=30)
                print(f"📊 Status response: {response.status_code}")
                print(f"📄 Status response: {response.text}")
                
                if response.status_code == 200:
                    response_data = response.json()
                    status_data = response_data.get('data', {})
                    
                    status = status_data.get('status')
                    print(f"📊 Current status: {status}")
                    
                    if status == 'PUBLISHED':
                        print("✅ Video published successfully!")
                        return {
                            'upload_successful': True,
                            'publish_successful': True,
                            'status': status,
                            'publish_id': publish_id,
                            'data': status_data
                        }
                    elif status == 'FAILED':
                        fail_reason = status_data.get('fail_reason', 'Unknown failure reason')
                        print(f"❌ Publishing failed: {fail_reason}")
                        return {
                            'error': 'publish_failed',
                            'message': f"Publishing failed: {fail_reason}",
                            'upload_successful': True,
                            'status': status,
                            'publish_id': publish_id
                        }
                    elif status in ['PROCESSING_DOWNLOAD', 'PROCESSING_UPLOAD', 'PROCESSING']:
                        print(f"⏳ Still processing... waiting {wait_time} seconds")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"⚠️ Unknown status: {status}")
                        time.sleep(wait_time)
                        continue
                else:
                    print(f"❌ Status check failed: {response.status_code}")
                    time.sleep(wait_time)
                    continue
            
            # If we get here, we timed out waiting for completion
            return {
                'error': 'status_timeout',
                'message': 'Video upload completed but status check timed out. Check your TikTok account.',
                'upload_successful': True,
                'publish_id': publish_id
            }
            
        except Exception as e:
            print(f"❌ Error checking post status: {e}")
            return {
                'error': 'status_check_failed',
                'message': f"Could not check post status: {str(e)}",
                'upload_successful': True,
                'publish_id': publish_id
            }

    def upload_video_to_inbox(self, video_path, caption="", hashtags=""):
        """Upload a video to TikTok inbox (draft) - user must manually publish"""
        print(f"📥 Starting inbox video upload...")
        
        if not self.validate_credentials():
            error_msg = "Invalid credentials. Cannot upload video."
            print(f"❌ {error_msg}")
            return None
        
        if not os.path.exists(video_path):
            error_msg = f"Video file not found at {video_path}"
            print(f"❌ {error_msg}")
            return None
        
        file_size = os.path.getsize(video_path)
        file_size_mb = file_size / (1024*1024)
        print(f"📊 Video file size: {file_size_mb:.2f} MB")
        
        try:
            # Step 1: Initialize inbox upload
            print("🚀 Step 1: Initializing inbox upload...")
            init_url = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            init_payload = {
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": file_size,
                    "chunk_size": file_size,
                    "total_chunk_count": 1
                }
            }
            
            init_response = requests.post(init_url, headers=headers, json=init_payload, timeout=30)
            print(f"📊 Init response status: {init_response.status_code}")
            
            if init_response.status_code != 200:
                try:
                    error_data = init_response.json()
                    error_message = error_data.get('error', {}).get('message', 'Unknown error')
                    return {
                        'error': 'init_failed',
                        'message': f"Inbox upload initialization failed: {error_message}"
                    }
                except:
                    return {
                        'error': 'init_failed',
                        'message': f"Inbox upload initialization failed: {init_response.status_code}"
                    }
            
            init_data = init_response.json()
            upload_url = init_data["data"]["upload_url"]
            publish_id = init_data["data"].get("publish_id")
            print(f"🔗 Upload URL obtained")
            print(f"🆔 Publish ID: {publish_id}")
            
            # Step 2: Upload the video file
            print("📤 Step 2: Uploading video file...")
            
            with open(video_path, 'rb') as video_file:
                video_content = video_file.read()
                
                upload_headers = {
                    "Content-Type": "video/mp4",
                    "Content-Length": str(file_size),
                    "Content-Range": f"bytes 0-{file_size-1}/{file_size}",
                }
                
                timeout_seconds = max(120, int(file_size_mb / 10 * 60))
                
                upload_response = requests.put(
                    upload_url,
                    headers=upload_headers,
                    data=video_content,
                    timeout=timeout_seconds
                )
                
                print(f"📊 Upload response status: {upload_response.status_code}")
                
                if upload_response.status_code not in [200, 201, 204]:
                    return {
                        'error': 'upload_failed',
                        'message': f"Video upload failed: {upload_response.status_code}"
                    }
            
            print("✅ Video uploaded to inbox successfully!")
            print("📱 User will receive notification in TikTok app to complete posting")
            
            return {
                'upload_successful': True,
                'publish_successful': False,
                'inbox_upload': True,
                'message': 'Video uploaded to TikTok inbox. User must open TikTok app to complete posting.',
                'publish_id': publish_id
            }
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"💥 {error_msg}")
            print(f"📍 Traceback: {traceback.format_exc()}")
            return {
                'error': 'unexpected_error',
                'message': error_msg
            }

    def get_user_videos(self, limit=10):
        """Get user's videos with correct field parameter format"""
        print(f"📹 Fetching user videos (limit: {limit})...")
        
        if not self.validate_credentials():
            print("❌ Invalid credentials. Cannot get videos.")
            return None
        
        try:
            url = "https://open.tiktokapis.com/v2/video/list/"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # FIXED: Use POST with correct body format
            payload = {
                "max_count": min(limit, 20),
                "fields": [  # Use array format instead of comma-separated string
                    "id",
                    "title", 
                    "video_description",
                    "duration",
                    "cover_image_url",
                    "share_url",
                    "view_count",
                    "like_count",
                    "comment_count",
                    "share_count",
                    "create_time"
                ]
            }
            
            print(f"📡 Making POST request to: {url}")
            print(f"📋 Payload: {payload}")
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            print(f"📊 Response status: {response.status_code}")
            print(f"📄 Response: {response.text}")
            
            if response.status_code == 200:
                response_data = response.json()
                if 'data' in response_data and 'videos' in response_data['data']:
                    videos = response_data['data']['videos']
                    print(f"✅ Retrieved {len(videos)} videos")
                    return videos
                else:
                    print("⚠️ No videos found in response")
                    return []
            else:
                try:
                    error_data = response.json()
                    error_message = error_data.get('error', {}).get('message', 'Unknown error')
                    print(f"❌ API Error: {error_message}")
                except:
                    print(f"❌ HTTP Error: {response.status_code}")
                return []
            
        except Exception as e:
            error_msg = f"Error getting user videos: {str(e)}"
            print(f"❌ {error_msg}")
            print(f"📍 Traceback: {traceback.format_exc()}")
            return None

    def get_video_info(self, video_id):
        """Get details for a specific video with correct parameters"""
        print(f"🎬 Fetching video info for ID: {video_id}")
        
        if not self.validate_credentials():
            print("❌ Invalid credentials. Cannot get video details.")
            return None
        
        try:
            url = "https://open.tiktokapis.com/v2/video/query/"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "video_ids": [video_id],
                "fields": [
                    "id",
                    "title",
                    "video_description", 
                    "create_time",
                    "cover_image_url",
                    "share_url",
                    "duration",
                    "height",
                    "width",
                    "view_count",
                    "like_count",
                    "comment_count",
                    "share_count"
                ]
            }
            
            print(f"📡 Making request to: {url}")
            print(f"📋 Request payload: {payload}")
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            print(f"📊 Response status: {response.status_code}")
            print(f"📄 Response: {response.text}")
            
            if response.status_code != 200:
                try:
                    error_data = response.json()
                    error_message = error_data.get('error', {}).get('message', 'Unknown error')
                    print(f"❌ API Error: {error_message}")
                    return None
                except:
                    return None
            
            response_data = response.json()
            if 'data' in response_data and 'videos' in response_data['data'] and len(response_data['data']['videos']) > 0:
                video_info = response_data['data']['videos'][0]
                print(f"✅ Retrieved video info: {video_info}")
                return video_info
            else:
                print(f"❌ Video not found in response: {response_data}")
                return None
            
        except Exception as e:
            error_msg = f"HTTP error getting video info: {str(e)}"
            print(f"❌ {error_msg}")
            print(f"📍 Traceback: {traceback.format_exc()}")
            return None

    def delete_video(self, video_id):
        """Delete a video (Note: TikTok API may not support video deletion)"""
        print(f"🗑️ Attempting to delete video ID: {video_id}")
        
        if not self.validate_credentials():
            print("❌ Invalid credentials. Cannot delete video.")
            return False
        
        try:
            # Note: As of current TikTok API documentation, there might not be a delete endpoint
            # This is a placeholder implementation - check TikTok API docs for actual endpoint
            print("⚠️ Warning: Video deletion via API may not be supported")
            print("📱 Users may need to manually delete videos from the TikTok app")
            
            # If TikTok adds a delete endpoint in the future, implement it here:
            # url = "https://open.tiktokapis.com/v2/video/delete/"
            # headers = {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}
            # payload = {"video_id": video_id}
            # response = requests.post(url, headers=headers, json=payload)
            # return response.status_code == 200
            
            return False
            
        except requests.exceptions.RequestException as e:
            error_msg = f"HTTP error deleting video: {str(e)}"
            print(f"❌ {error_msg}")
            if hasattr(e, 'response') and e.response:
                print(f"📄 Error response: {e.response.text}")
            print(f"📍 Traceback: {traceback.format_exc()}")
            return False
        except Exception as e:
            error_msg = f"Unexpected error deleting video: {str(e)}"
            print(f"💥 {error_msg}")
            print(f"📍 Traceback: {traceback.format_exc()}")
            return False

    def get_user_info(self):
        """Get basic user information"""
        print("👤 Fetching user information...")
        
        if not self.validate_credentials():
            print("❌ Invalid credentials. Cannot get user info.")
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
            
            print(f"📡 Making request to: {url}")
            print(f"📋 Request params: {params}")
            
            response = requests.get(url, headers=headers, params=params)
            print(f"📊 Response status: {response.status_code}")
            print(f"📄 Response: {response.text}")
            
            if response.status_code != 200:
                error_msg = f"API request failed with status {response.status_code}: {response.text}"
                print(f"❌ {error_msg}")
                return None
            
            response_data = response.json()
            if 'data' in response_data and 'user' in response_data['data']:
                user_info = response_data['data']['user']
                print(f"✅ Retrieved user info: {user_info}")
                return user_info
            else:
                print(f"⚠️ Unexpected response format: {response_data}")
                return None
            
        except requests.exceptions.RequestException as e:
            error_msg = f"HTTP error getting user info: {str(e)}"
            print(f"❌ {error_msg}")
            if hasattr(e, 'response') and e.response:
                print(f"📄 Error response: {e.response.text}")
            print(f"📍 Traceback: {traceback.format_exc()}")
            return None
        except Exception as e:
            error_msg = f"Unexpected error getting user info: {str(e)}"
            print(f"💥 {error_msg}")
            print(f"📍 Traceback: {traceback.format_exc()}")
            return None