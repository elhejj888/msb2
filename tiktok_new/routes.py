from flask import jsonify, request
from .controller import TikTokManager
import tempfile
import os
import json

def setup_tiktok_routes(app):
    tiktok_manager = TikTokManager()

    @app.route('/api/tiktok/validate-credentials', methods=['GET'])
    def validate_tiktok_credentials():
        try:
            is_valid = tiktok_manager.validate_credentials()
            return jsonify({
                'success': True,
                'is_valid': is_valid
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/tiktok/connection-status', methods=['GET'])
    def get_tiktok_connection_status():
        try:
            status = tiktok_manager.get_connection_status()
            return jsonify({
                'success': True,
                'status': status
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/tiktok/connect', methods=['POST'])
    def connect_tiktok():
        try:
            data = request.get_json() or {}
            force_reauth = data.get('force_reauth', False)
            
            if force_reauth:
                tiktok_manager.revoke_token()
            
            # Trigger OAuth flow if no valid token
            if not tiktok_manager.validate_credentials():
                access_token = tiktok_manager.get_access_token()
                if access_token:
                    return jsonify({
                        'success': True,
                        'message': 'Successfully connected to TikTok'
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': 'Failed to connect to TikTok'
                    })
            else:
                return jsonify({
                    'success': True,
                    'message': 'Already connected to TikTok'
                })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/tiktok/disconnect', methods=['POST'])
    def disconnect_tiktok():
        try:
            tiktok_manager.revoke_token()
            return jsonify({
                'success': True,
                'message': 'Successfully disconnected from TikTok'
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/tiktok/refresh', methods=['POST'])
    def refresh_tiktok_connection():
        try:
            success = tiktok_manager.refresh_connection()
            return jsonify({
                'success': success,
                'message': 'Connection refreshed successfully' if success else 'Failed to refresh connection'
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/tiktok/user-info', methods=['GET'])
    def get_tiktok_user_info():
        try:
            user_info = tiktok_manager.get_user_info()
            if user_info:
                return jsonify({
                    'success': True,
                    'user': user_info
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to get user info'}), 500
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/tiktok/videos', methods=['GET'])
    def get_tiktok_videos():
        try:
            limit = request.args.get('limit', 10, type=int)
            videos = tiktok_manager.get_user_videos(limit=limit)
            
            if videos is not None:
                return jsonify({
                    'success': True,
                    'videos': videos
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to retrieve videos'}), 500
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/tiktok/videos/<video_id>', methods=['GET'])
    def get_tiktok_video_analytics(video_id):
        try:
            video_data = tiktok_manager.get_video_analytics(video_id)
            if video_data:
                return jsonify({
                    'success': True,
                    'video': video_data
                })
            else:
                return jsonify({'success': False, 'error': 'Video not found'}), 404
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/tiktok/upload-video', methods=['POST'])
    def upload_tiktok_video():
        try:
            # Handle both form data and JSON data
            if request.content_type and 'multipart/form-data' in request.content_type:
                # Form data upload
                title = request.form.get('title', '')
                description = request.form.get('description', '')
                privacy_level = request.form.get('privacy_level', 'SELF_ONLY')
                disable_duet = request.form.get('disable_duet', 'false').lower() == 'true'
                disable_comment = request.form.get('disable_comment', 'false').lower() == 'true'
                disable_stitch = request.form.get('disable_stitch', 'false').lower() == 'true'
                
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
            else:
                # JSON data upload (base64 encoded video)
                data = request.get_json()
                if not data:
                    return jsonify({'success': False, 'error': 'No data provided'}), 400
                
                title = data.get('title', '')
                description = data.get('description', '')
                privacy_level = data.get('privacy_level', 'SELF_ONLY')
                disable_duet = data.get('disable_duet', False)
                disable_comment = data.get('disable_comment', False)
                disable_stitch = data.get('disable_stitch', False)
                video_base64 = data.get('video_base64')
                
                if not video_base64:
                    return jsonify({'success': False, 'error': 'No video data provided'}), 400
                
                # Decode base64 video
                try:
                    import base64
                    video_data = base64.b64decode(video_base64.split(',')[1] if ',' in video_base64 else video_base64)
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
                        tmp_file.write(video_data)
                        video_path = tmp_file.name
                except Exception as e:
                    return jsonify({'success': False, 'error': f'Error processing video data: {str(e)}'}), 400
            
            # Upload video
            result = tiktok_manager.upload_video(
                video_path=video_path,
                title=title,
                description=description,
                privacy_level=privacy_level,
                disable_duet=disable_duet,
                disable_comment=disable_comment,
                disable_stitch=disable_stitch
            )
            
            # Clean up temp file
            if video_path and os.path.exists(video_path):
                os.unlink(video_path)
            
            if result:
                return jsonify({
                    'success': True,
                    'result': result
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to upload video'}), 500
                
        except Exception as e:
            # Clean up temp file if it exists
            if 'video_path' in locals() and video_path and os.path.exists(video_path):
                os.unlink(video_path)
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/tiktok/schedule-video', methods=['POST'])
    def schedule_tiktok_video():
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400
            
            video_path = data.get('video_path')
            title = data.get('title', '')
            description = data.get('description', '')
            scheduled_time = data.get('scheduled_time')
            privacy_level = data.get('privacy_level', 'SELF_ONLY')
            
            if not video_path:
                return jsonify({'success': False, 'error': 'Video path is required'}), 400
            
            if not scheduled_time:
                return jsonify({'success': False, 'error': 'Scheduled time is required'}), 400
            
            result = tiktok_manager.schedule_video(
                video_path=video_path,
                title=title,
                description=description,
                scheduled_time=scheduled_time,
                privacy_level=privacy_level
            )
            
            if result:
                return jsonify({
                    'success': True,
                    'result': result
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to schedule video'}), 500
                
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/tiktok/bulk-upload', methods=['POST'])
    def bulk_upload_tiktok_videos():
        try:
            data = request.get_json()
            if not data or 'videos' not in data:
                return jsonify({'success': False, 'error': 'No video data provided'}), 400
            
            video_data_list = data['videos']
            if not isinstance(video_data_list, list):
                return jsonify({'success': False, 'error': 'Videos must be a list'}), 400
            
            results = tiktok_manager.bulk_upload_videos(video_data_list)
            
            return jsonify({
                'success': True,
                'results': results,
                'total_videos': len(video_data_list),
                'successful_uploads': len([r for r in results if r.get('success')])
            })
                
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/tiktok/trending-hashtags', methods=['GET'])
    def get_trending_hashtags():
        try:
            hashtags = tiktok_manager.get_trending_hashtags()
            return jsonify({
                'success': True,
                'hashtags': hashtags
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/tiktok/analytics/summary', methods=['GET'])
    def get_tiktok_analytics_summary():
        try:
            # Get user info and recent videos for analytics summary
            user_info = tiktok_manager.get_user_info()
            videos = tiktok_manager.get_user_videos(limit=10)
            
            if not user_info:
                return jsonify({'success': False, 'error': 'Failed to get user info'}), 500
            
            # Calculate summary metrics
            total_videos = user_info.get('video_count', 0)
            total_followers = user_info.get('follower_count', 0)
            total_likes = user_info.get('likes_count', 0)
            
            recent_performance = {
                'total_views': 0,
                'total_likes': 0,
                'total_comments': 0,
                'total_shares': 0
            }
            
            if videos:
                for video in videos:
                    recent_performance['total_views'] += video.get('view_count', 0)
                    recent_performance['total_likes'] += video.get('like_count', 0)
                    recent_performance['total_comments'] += video.get('comment_count', 0)
                    recent_performance['total_shares'] += video.get('share_count', 0)
            
            analytics_summary = {
                'account_metrics': {
                    'total_videos': total_videos,
                    'total_followers': total_followers,
                    'total_likes': total_likes,
                    'following_count': user_info.get('following_count', 0)
                },
                'recent_performance': recent_performance,
                'recent_videos_count': len(videos) if videos else 0
            }
            
            return jsonify({
                'success': True,
                'analytics': analytics_summary
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
