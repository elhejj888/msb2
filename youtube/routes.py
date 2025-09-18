from flask import jsonify, request
from .controller import YouTubeManager
import tempfile
import os
from jwt_utils import jwt_required_custom, get_current_user_from_token
from connection_service import ConnectionService

def setup_youtube_routes(app):
    print("🔧 Setting up YouTube routes...")
    
    def get_youtube_manager(current_user_id=None):
        return YouTubeManager(user_id=current_user_id)

    @app.route('/api/youtube/validate-credentials', methods=['GET'])
    @jwt_required_custom
    def validate_youtube_credentials(current_user=None, current_user_id=None):
        try:
            youtube_manager = get_youtube_manager(current_user_id)
            is_valid = youtube_manager.validate_credentials()
            return jsonify({
                'success': True,
                'is_valid': is_valid
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/youtube/shorts', methods=['GET'])
    @jwt_required_custom
    def get_youtube_shorts(current_user=None, current_user_id=None):
        try:
            youtube_manager = get_youtube_manager(current_user_id)
            shorts = youtube_manager.get_channel_videos()
            if shorts is not None:
                return jsonify({
                    'success': True,
                    'shorts': shorts
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to retrieve Shorts'}), 500
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/youtube/shorts', methods=['POST'])
    @jwt_required_custom
    def create_youtube_short(current_user=None, current_user_id=None):
        try:
            youtube_manager = get_youtube_manager(current_user_id)
            # Handle multipart form data for video upload
            title = request.form.get('title', '')
            description = request.form.get('description', '')
            link = request.form.get('link', '')
            privacy_status = request.form.get('privacyStatus', 'public')
            
            # Get the uploaded video file
            if 'video' not in request.files:
                return jsonify({'success': False, 'error': 'Video file is required'}), 400
            
            video_file = request.files['video']
            if video_file.filename == '':
                return jsonify({'success': False, 'error': 'No video file selected'}), 400
            
            # Save video to temp file
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
                    video_file.save(tmp_file.name)
                    video_path = tmp_file.name
            except Exception as e:
                return jsonify({'success': False, 'error': f'Error processing video: {str(e)}'}), 400
            
            # Upload the Short
            scheduled_time = request.form.get('scheduled_time')
            short_data = youtube_manager.upload_short(
                video_path=video_path,
                title=title,
                description=description,
                privacy_status=privacy_status,
                link=link,
                scheduled_time=scheduled_time
            )
            
            # Clean up temp file
            if video_path and os.path.exists(video_path):
                os.unlink(video_path)
            
            if short_data:
                return jsonify({
                    'success': True,
                    'short': short_data
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to upload Short'}), 500
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/youtube/shorts/<video_id>', methods=['GET'])
    @jwt_required_custom
    def get_youtube_short(current_user=None, current_user_id=None, video_id=None):
        try:
            youtube_manager = get_youtube_manager(current_user_id)
            short_data = youtube_manager.get_short(video_id)
            if short_data:
                return jsonify({
                    'success': True,
                    'short': short_data
                })
            else:
                return jsonify({'success': False, 'error': 'Short not found'}), 404
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/youtube/shorts/<video_id>', methods=['DELETE'])
    @jwt_required_custom
    def delete_youtube_short(current_user=None, current_user_id=None, video_id=None):
        try:
            youtube_manager = get_youtube_manager(current_user_id)
            success = youtube_manager.delete_short(video_id)
            if success:
                return jsonify({
                    'success': True,
                    'message': 'Short deleted successfully'
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to delete Short'}), 500
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/youtube/connection-status', methods=['GET'])
    @jwt_required_custom
    def get_youtube_connection_status(current_user=None, current_user_id=None):
        try:
            print(f"Checking YouTube connection status for user {current_user_id}")
            
            # Check database connection status first (Pinterest approach)
            connection_status = ConnectionService.get_user_connection_status(current_user_id, 'youtube')
            print(f"Database connection status: {connection_status}")
            
            if connection_status['connected']:
                print(f"✅ Database shows YouTube connection exists: {connection_status['username']}")
                return jsonify({
                    'success': True,
                    'status': {
                        'connected': True,
                        'username': connection_status['username'],
                        'message': f'Connected to YouTube as {connection_status["username"]}' if connection_status['username'] else 'Connected to YouTube'
                    }
                })
            else:
                print("❌ No YouTube connection found in database")
                return jsonify({
                    'success': True,
                    'status': {
                        'connected': False,
                        'message': 'Not connected to YouTube'
                    }
                })
        except Exception as e:
            print(f"Error checking YouTube connection status: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': True,
                'status': {
                    'connected': False,
                    'message': 'Not connected to YouTube'
                }
            })

    @app.route('/api/youtube/connect', methods=['POST'])
    @jwt_required_custom
    def connect_youtube(current_user=None, current_user_id=None):
        print(f"🎯 YouTube connect route called! User ID: {current_user_id}")
        try:
            youtube_manager = get_youtube_manager(current_user_id)
            
            # First check if already connected
            if youtube_manager.validate_credentials():
                # Already connected, get user info
                user_info = youtube_manager.get_user_info()
                if user_info:
                    platform_user_id = user_info.get('id', '')
                    platform_username = user_info.get('username', '')
                    print(f"YouTube already connected - User: {current_user_id}, Platform User ID: {platform_user_id}, Username: {platform_username}")
                else:
                    return jsonify({
                        'success': False,
                        'error': 'Failed to get user information from YouTube'
                    }), 500
            else:
                # Need to start OAuth flow
                try:
                    print(f"Starting YouTube OAuth flow for user {current_user_id}")
                    access_token = youtube_manager.get_access_token()
                    if not access_token:
                        return jsonify({
                            'success': False,
                            'error': 'Failed to complete YouTube OAuth flow'
                        }), 500
                    
                    # Get user info after successful OAuth
                    user_info = youtube_manager.get_user_info()
                    if not user_info:
                        return jsonify({
                            'success': False,
                            'error': 'Failed to get user information from YouTube after OAuth'
                        }), 500
                    
                    platform_user_id = user_info.get('id', '')
                    platform_username = user_info.get('username', '')
                    
                    print(f"YouTube OAuth completed - User: {current_user_id}, Platform User ID: {platform_user_id}, Username: {platform_username}")
                    
                except Exception as oauth_error:
                    print(f"YouTube OAuth failed for user {current_user_id}: {oauth_error}")
                    return jsonify({
                        'success': False,
                        'error': f'YouTube OAuth failed: {str(oauth_error)}'
                    }), 500
            
            # Validate we have the required information
            if not platform_user_id:
                return jsonify({
                    'success': False,
                    'error': 'Failed to get user ID from YouTube'
                }), 500
            
            # Check account exclusivity and create connection
            print(f"Preparing to save YouTube connection to database:")
            print(f"  User ID: {current_user_id}")
            print(f"  Platform User ID: {platform_user_id}")
            print(f"  Platform Username: {platform_username}")
            print(f"  Has Access Token: {bool(youtube_manager.access_token)}")
            print(f"  Has Refresh Token: {bool(youtube_manager.refresh_token)}")
            
            try:
                connection_result = ConnectionService.create_connection(
                    user_id=current_user_id,
                    platform='youtube',
                    platform_user_id=platform_user_id,
                    platform_username=platform_username,
                    access_token=youtube_manager.access_token if hasattr(youtube_manager, 'access_token') else None,
                    additional_data={
                        'refresh_token': youtube_manager.refresh_token if hasattr(youtube_manager, 'refresh_token') else None
                    }
                )
                
                print(f"ConnectionService.create_connection result: {connection_result}")
                
                if connection_result['success']:
                    print(f"✅ YouTube connection successfully saved to database!")
                    return jsonify({
                        'success': True,
                        'message': f'Successfully connected to YouTube as {platform_username}!',
                        'username': platform_username
                    })
                else:
                    # Connection save failed
                    print(f"❌ YouTube connection save failed: {connection_result.get('error')}")
                    if connection_result['error'] == 'account_unavailable':
                        print(f"Account unavailable - already connected to: {connection_result.get('connected_username')}")
                        return jsonify({
                            'success': False,
                            'error': 'This YouTube account is already connected to another user',
                            'account_unavailable': True,
                            'connected_username': connection_result.get('connected_username')
                        }), 409
                    else:
                        print(f"Database save error: {connection_result.get('error')}")
                        return jsonify({
                            'success': False,
                            'error': f'Failed to save connection: {connection_result["error"]}'
                        }), 500
                        
            except Exception as e:
                print(f"Error creating YouTube connection: {e}")
                import traceback
                traceback.print_exc()
                return jsonify({
                    'success': False,
                    'error': f'Failed to create connection: {str(e)}'
                }), 500
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/youtube/disconnect', methods=['POST'])
    @jwt_required_custom
    def disconnect_youtube(current_user=None, current_user_id=None):
        try:
            youtube_manager = get_youtube_manager(current_user_id)
            # Disconnect from database first
            disconnect_result = ConnectionService.disconnect_user_platform(current_user_id, 'youtube')
            
            if disconnect_result['success']:
                # Also try to disconnect from YouTube manager if available
                try:
                    youtube_manager.revoke_token()
                except Exception as e:
                    print(f"Warning: Failed to disconnect from YouTube manager: {e}")
                
                return jsonify({
                    'success': True,
                    'message': 'Successfully disconnected from YouTube'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Failed to disconnect: {disconnect_result["error"]}'
                })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/youtube/analytics', methods=['GET'])
    @jwt_required_custom
    def get_youtube_analytics(current_user=None, current_user_id=None):
        try:
            youtube_manager = get_youtube_manager(current_user_id)
            analytics = youtube_manager.get_channel_analytics()
            if analytics:
                return jsonify({
                    'success': True,
                    'analytics': analytics
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to retrieve analytics'}), 500
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    print("✅ YouTube routes setup completed successfully!")
    print("📋 Registered routes:")
    print("  - GET  /api/youtube/connection-status")
    print("  - POST /api/youtube/connect")
    print("  - POST /api/youtube/disconnect")
    print("  - GET  /api/youtube/shorts")
    print("  - POST /api/youtube/shorts")
    print("  - GET  /api/youtube/analytics")
