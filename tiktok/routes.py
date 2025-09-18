from flask import jsonify, request
from .controller import TikTokManager
import tempfile
import os
from jwt_utils import jwt_required_custom, get_current_user_from_token
from connection_service import ConnectionService

def setup_tiktok_routes(app, get_tiktok_manager=None):
    # TikTok Manager - Initialize lazily to avoid startup failures
    tiktok_manager = None
    
    def get_tiktok_manager_instance():
        """Lazy initialization of TikTok manager to avoid startup failures"""
        nonlocal tiktok_manager
        if tiktok_manager is None:
            try:
                tiktok_manager = TikTokManager()
            except Exception as e:
                print(f"Warning: Could not initialize TikTok Manager: {str(e)}")
                tiktok_manager = False  # Mark as failed to avoid repeated attempts
        return tiktok_manager if tiktok_manager is not False else None

    @app.route('/api/tiktok/validate-credentials', methods=['GET'])
    @jwt_required_custom
    def validate_tiktok_credentials(current_user=None, current_user_id=None):
        try:
            manager = get_tiktok_manager_instance()
            if not manager:
                return jsonify({'success': False, 'error': 'TikTok Manager not available'}), 500
            is_valid = manager.validate_credentials()
            return jsonify({
                'success': True,
                'is_valid': is_valid
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/tiktok/connection-status', methods=['GET'])
    @jwt_required_custom
    def get_tiktok_connection_status(current_user=None, current_user_id=None):
        try:
            # Check database connection status first
            connection_status = ConnectionService.get_user_connection_status(current_user_id, 'tiktok')
            
            if connection_status['connected']:
                return jsonify({
                    'success': True,
                    'status': {
                        'connected': True,
                        'username': connection_status['username'],
                        'message': f'Connected to TikTok as @{connection_status["username"]}' if connection_status['username'] else 'Connected to TikTok'
                    }
                })
            else:
                return jsonify({
                    'success': True,
                    'status': {
                        'connected': False,
                        'message': 'Not connected to TikTok'
                    }
                })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/tiktok/connect', methods=['POST'])
    @jwt_required_custom
    def connect_tiktok(current_user=None, current_user_id=None):
        try:
            data = request.get_json() or {}
            force_reauth = data.get('force_reauth', False)
            
            manager = get_tiktok_manager_instance()
            if not manager:
                return jsonify({'success': False, 'error': 'TikTok Manager not available'}), 500
            
            if force_reauth:
                manager.revoke_token()
            
            is_valid = manager.validate_credentials()
            if is_valid:
                # Get user info from TikTok API to check account exclusivity
                try:
                    user_info = manager.get_user_info()  # This should return user ID and username
                    if not user_info:
                        return jsonify({
                            'success': False,
                            'error': 'Failed to get user information from TikTok'
                        }), 500
                    
                    platform_user_id = str(user_info.get('id', '') or user_info.get('user_id', ''))
                    platform_username = user_info.get('username', '') or user_info.get('display_name', '')
                    
                    print(f"TikTok connection attempt - User: {current_user_id}, Platform User ID: {platform_user_id}, Username: {platform_username}")
                    
                    if not platform_user_id:
                        return jsonify({
                            'success': False,
                            'error': 'Failed to get user ID from TikTok'
                        }), 500
                    
                    # Check account exclusivity and create connection
                    connection_result = ConnectionService.create_connection(
                        user_id=current_user_id,
                        platform='tiktok',
                        platform_user_id=platform_user_id,
                        platform_username=platform_username,
                        access_token=manager.access_token if hasattr(manager, 'access_token') else None,
                        additional_data={
                            'refresh_token': manager.refresh_token if hasattr(manager, 'refresh_token') else None
                        }
                    )
                    
                    if connection_result['success']:
                        return jsonify({
                            'success': True,
                            'message': f'Successfully connected to TikTok as @{platform_username}!',
                            'username': platform_username
                        })
                    else:
                        # Account exclusivity violation
                        if connection_result['error'] == 'account_unavailable':
                            return jsonify({
                                'success': False,
                                'error': 'This TikTok account is already connected to another user',
                                'account_unavailable': True,
                                'connected_username': connection_result.get('connected_username')
                            }), 409
                        else:
                            return jsonify({
                                'success': False,
                                'error': f'Failed to save connection: {connection_result["error"]}'
                            }), 500
                            
                except Exception as e:
                    return jsonify({
                        'success': False,
                        'error': f'Failed to process connection: {str(e)}'
                    }), 500
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to connect to TikTok'
                })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/tiktok/disconnect', methods=['POST'])
    @jwt_required_custom
    def disconnect_tiktok(current_user=None, current_user_id=None):
        try:
            # Disconnect from database first
            disconnect_result = ConnectionService.disconnect_user_platform(current_user_id, 'tiktok')
            
            if disconnect_result['success']:
                # Also try to disconnect from TikTok manager if available
                try:
                    manager = get_tiktok_manager_instance()
                    if manager:
                        manager.revoke_token()
                except Exception as e:
                    print(f"Warning: Failed to disconnect from TikTok manager: {e}")
                
                return jsonify({
                    'success': True,
                    'message': 'Successfully disconnected from TikTok'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Failed to disconnect: {disconnect_result["error"]}'
                })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/tiktok/refresh', methods=['POST'])
    @jwt_required_custom
    def refresh_tiktok_connection(current_user=None, current_user_id=None):
        try:
            manager = get_tiktok_manager_instance()
            if not manager:
                return jsonify({'success': False, 'error': 'TikTok Manager not available'}), 500
            success = manager.refresh_connection()
            return jsonify({
                'success': success,
                'message': 'Connection refreshed successfully' if success else 'Failed to refresh connection'
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/tiktok/user-videos', methods=['GET'])
    def get_tiktok_user_videos():
        try:
            manager = get_tiktok_manager_instance()
            if not manager:
                return jsonify({'success': False, 'error': 'TikTok Manager not available'}), 500
            limit = request.args.get('limit', 10, type=int)
            videos = manager.get_user_videos(limit=limit)
            
            if videos is not None:
                return jsonify({
                    'success': True,
                    'videos': videos
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to retrieve videos'}), 500
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/tiktok/video/<video_id>', methods=['GET'])
    def get_tiktok_video(video_id):
        try:
            manager = get_tiktok_manager_instance()
            if not manager:
                return jsonify({'success': False, 'error': 'TikTok Manager not available'}), 500
            video_data = manager.get_video_info(video_id)
            if video_data:
                return jsonify({
                    'success': True,
                    'video': video_data
                })
            else:
                return jsonify({'success': False, 'error': 'Video not found'}), 404
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/tiktok/video/<video_id>', methods=['DELETE'])
    def delete_tiktok_video(video_id):
        try:
            manager = get_tiktok_manager_instance()
            if not manager:
                return jsonify({'success': False, 'error': 'TikTok Manager not available'}), 500
            success = manager.delete_video(video_id)
            return jsonify({
                'success': success,
                'message': 'Video deleted successfully' if success else 'Failed to delete video'
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/tiktok/upload-video', methods=['POST'])
    def upload_tiktok_video():
        try:
            # Get form data
            caption = request.form.get('caption', '')
            hashtags = request.form.get('hashtags', '')
            privacy_level = request.form.get('privacy_level', '0')
            
            # Get video file
            if 'video' not in request.files:
                return jsonify({'success': False, 'error': 'No video file provided'}), 400
                
            video_file = request.files['video']
            if video_file.filename == '':
                return jsonify({'success': False, 'error': 'No video file selected'}), 400
                
            # Save video to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
                video_file.save(tmp_file)
                video_path = tmp_file.name
                
            # Upload video
            manager = get_tiktok_manager_instance()
            if not manager:
                return jsonify({'success': False, 'error': 'TikTok Manager not available'}), 500
            result = manager.upload_video(
                video_path=video_path,
                caption=caption,
                hashtags=hashtags,
                privacy_level=int(privacy_level))
                
            # Clean up temp file
            if video_path and os.path.exists(video_path):
                os.unlink(video_path)
                
            if result:
                return jsonify({
                    'success': True,
                    'video': result
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to upload video'}), 500
                
        except Exception as e:
            # Clean up temp file if it exists
            if 'video_path' in locals() and video_path and os.path.exists(video_path):
                os.unlink(video_path)
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/tiktok/user-info', methods=['GET'])
    def get_tiktok_user_info():
        try:
            manager = get_tiktok_manager_instance()
            if not manager:
                return jsonify({'success': False, 'error': 'TikTok Manager not available'}), 500
            user_info = manager.get_user_info()
            if user_info:
                return jsonify({
                    'success': True,
                    'user': user_info
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to get user info'}), 500
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500