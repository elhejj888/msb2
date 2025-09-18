from flask import jsonify, request
from .controller import TikTokManager
from .auth import TikTokAuth
import tempfile
import os
import traceback

def setup_tiktok_routes(app, tiktok_manager=None):
    if tiktok_manager is None:
        tiktok_manager = TikTokManager()
    
    # Initialize TikTok auth separately for OAuth flow
    tiktok_auth = TikTokAuth()

    @app.route('/api/tiktok/validate-credentials', methods=['GET'])
    def validate_tiktok_credentials():
        try:
            is_valid = tiktok_auth.validate_credentials()
            return jsonify({
                'success': True,
                'is_valid': is_valid
            })
        except Exception as e:
            return jsonify({
                'success': False, 
                'error': str(e),
                'traceback': traceback.format_exc()
            }), 500

    @app.route('/api/tiktok/connection-status', methods=['GET', 'OPTIONS'])
    def get_tiktok_connection_status():
        if request.method == 'OPTIONS':
            return jsonify({'success': True, 'message': 'Preflight OK'})
        
        try:
            print("🔍 Checking TikTok connection status...")
            
            # Check if we have credentials configured
            if not tiktok_auth.client_key or not tiktok_auth.client_secret:
                return jsonify({
                    'success': True,
                    'status': {
                        'connected': False,
                        'message': 'TikTok credentials not configured. Please set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET environment variables.'
                    }
                })
            
            is_valid = tiktok_auth.validate_credentials()
            print(f"✅ Connection status: {'Connected' if is_valid else 'Not connected'}")
            
            return jsonify({
                'success': True,
                'status': {
                    'connected': is_valid,
                    'message': 'Connected to TikTok' if is_valid else 'Not connected to TikTok'
                }
            })
        except Exception as e:
            print(f"❌ Error checking connection status: {e}")
            return jsonify({
                'success': True,  # Don't fail the status check
                'status': {
                    'connected': False,
                    'message': f'TikTok connection error: {str(e)}'
                }
            })

    @app.route('/api/tiktok/connect', methods=['POST', 'OPTIONS'])
    def connect_tiktok():
        if request.method == 'OPTIONS':
            response = jsonify({'success': True, 'message': 'Preflight OK'})
            return response
        
        try:
            print("🚀 TikTok connect endpoint called!")
            
            data = request.get_json() or {}
            force_reauth = data.get('force_reauth', False)
            print(f"📊 Request data: force_reauth={force_reauth}")
            
            # Check if credentials are configured
            if not tiktok_auth.client_key or not tiktok_auth.client_secret:
                error_msg = "TikTok API credentials are not configured. Please set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET environment variables."
                print(f"❌ {error_msg}")
                return jsonify({
                    'success': False,
                    'error': error_msg,
                    'details': {
                        'client_key_present': bool(tiktok_auth.client_key),
                        'client_secret_present': bool(tiktok_auth.client_secret),
                        'redirect_uri': tiktok_auth.redirect_uri
                    }
                }), 400
            
            if force_reauth:
                print("🔄 Force reauth requested, revoking existing tokens...")
                tiktok_auth.revoke_token()
            
            # Check if already authenticated and valid
            if not force_reauth and tiktok_auth.validate_credentials():
                print("✅ Already authenticated with valid credentials")
                return jsonify({
                    'success': True,
                    'message': 'Already connected to TikTok',
                    'authenticated': True
                })
            
            # Generate OAuth URL for authentication
            print("🔗 Generating OAuth URL...")
            try:
                auth_url, csrf_token = tiktok_auth.generate_auth_url()
                print(f"🎯 Generated OAuth URL: {auth_url[:100]}...")
                
                return jsonify({
                    'success': True,
                    'message': 'Please complete authentication in your browser',
                    'auth_url': auth_url,
                    'csrf_token': csrf_token,
                    'authenticated': False
                })
            except Exception as auth_error:
                print(f"❌ Error generating auth URL: {auth_error}")
                return jsonify({
                    'success': False,
                    'error': f'Failed to generate authentication URL: {str(auth_error)}',
                    'details': {
                        'client_key': tiktok_auth.client_key[:10] + '...' if tiktok_auth.client_key else None,
                        'redirect_uri': tiktok_auth.redirect_uri,
                        'scope': tiktok_auth.scope
                    },
                    'traceback': traceback.format_exc()
                }), 500
            
        except Exception as e:
            print(f"💥 Unexpected error in connect endpoint: {e}")
            return jsonify({
                'success': False, 
                'error': f'Failed to initiate TikTok connection: {str(e)}',
                'traceback': traceback.format_exc()
            }), 500

    @app.route('/api/tiktok/callback', methods=['GET', 'POST'])
    def tiktok_callback():
        """Handle TikTok OAuth callback"""
        try:
            print("📞 TikTok callback received")
            code = request.args.get('code')
            state = request.args.get('state')
            error = request.args.get('error')
            error_description = request.args.get('error_description')
            
            print(f"📋 Callback params: code={'present' if code else 'missing'}, state={'present' if state else 'missing'}, error={error}")
            
            if error:
                error_msg = f"OAuth Error: {error}"
                if error_description:
                    error_msg += f" - {error_description}"
                print(f"❌ {error_msg}")
                
                return f"""
                <html>
                    <body style="font-family: Arial, sans-serif; padding: 40px; text-align: center;">
                        <div style="background: #fee; border: 1px solid #fcc; border-radius: 10px; padding: 20px; max-width: 500px; margin: 0 auto;">
                            <h2 style="color: #c33;">Authentication Failed</h2>
                            <p><strong>Error:</strong> {error}</p>
                            {f'<p><strong>Description:</strong> {error_description}</p>' if error_description else ''}
                            <p>Please close this window and try again.</p>
                        </div>
                        <script>
                            setTimeout(() => {{
                                if (window.opener) {{
                                    window.opener.postMessage({{
                                        type: 'TIKTOK_AUTH_ERROR',
                                        data: {{
                                            success: false,
                                            error: '{error_msg}'
                                        }}
                                    }}, '*');
                                    window.close();
                                }}
                            }}, 2000);
                        </script>
                    </body>
                </html>
                """
            
            if not code or not state:
                missing = []
                if not code:
                    missing.append('authorization code')
                if not state:
                    missing.append('state parameter')
                error_msg = f"Missing {' and '.join(missing)}"
                print(f"❌ {error_msg}")
                
                return f"""
                <html>
                    <body style="font-family: Arial, sans-serif; padding: 40px; text-align: center;">
                        <div style="background: #fee; border: 1px solid #fcc; border-radius: 10px; padding: 20px; max-width: 500px; margin: 0 auto;">
                            <h2 style="color: #c33;">Authentication Failed</h2>
                            <p>{error_msg}</p>
                            <p>Please close this window and try again.</p>
                        </div>
                        <script>
                            setTimeout(() => {{
                                if (window.opener) {{
                                    window.opener.postMessage({{
                                        type: 'TIKTOK_AUTH_ERROR',
                                        data: {{
                                            success: false,
                                            error: '{error_msg}'
                                        }}
                                    }}, '*');
                                    window.close();
                                }}
                            }}, 2000);
                        </script>
                    </body>
                </html>
                """
            
            # Exchange code for token
            print("🔄 Exchanging code for access token...")
            token_data = tiktok_auth.exchange_code_for_token(code, state)
            print("✅ Token exchange successful!")
            
            return f"""
            <html>
                <body style="font-family: Arial, sans-serif; padding: 40px; text-align: center;">
                    <div style="background: #efe; border: 1px solid #cfc; border-radius: 10px; padding: 20px; max-width: 500px; margin: 0 auto;">
                        <h2 style="color: #363;">✅ TikTok Connected Successfully!</h2>
                        <p>Your TikTok account has been successfully connected.</p>
                        <p style="font-size: 14px; color: #666;">You can now close this window and return to the app.</p>
                    </div>
                    <script>
                        // Try to close the popup window
                        setTimeout(() => {{
                            if (window.opener) {{
                                window.opener.postMessage({{
                                    type: 'TIKTOK_AUTH_SUCCESS',
                                    data: {{
                                        success: true,
                                        message: 'TikTok connected successfully'
                                    }}
                                }}, '*');
                                window.close();
                            }}
                        }}, 2000);
                    </script>
                </body>
            </html>
            """
            
        except Exception as e:
            error_msg = str(e)
            print(f"💥 Callback error: {error_msg}")
            print(f"📍 Traceback: {traceback.format_exc()}")
            
            return f"""
            <html>
                <body style="font-family: Arial, sans-serif; padding: 40px; text-align: center;">
                    <div style="background: #fee; border: 1px solid #fcc; border-radius: 10px; padding: 20px; max-width: 500px; margin: 0 auto;">
                        <h2 style="color: #c33;">Authentication Failed</h2>
                        <p><strong>Error:</strong> {error_msg}</p>
                        <details style="margin-top: 10px;">
                            <summary>Technical Details</summary>
                            <pre style="text-align: left; font-size: 12px; background: #f5f5f5; padding: 10px; border-radius: 5px; overflow-x: auto;">
{traceback.format_exc()}
                            </pre>
                        </details>
                        <p>Please close this window and try again.</p>
                    </div>
                    <script>
                        setTimeout(() => {{
                            if (window.opener) {{
                                window.opener.postMessage({{
                                    type: 'TIKTOK_AUTH_ERROR',
                                    data: {{
                                        success: false,
                                        error: '{error_msg}'
                                    }}
                                }}, '*');
                                window.close();
                            }}
                        }}, 2000);
                    </script>
                </body>
            </html>
            """

    @app.route('/api/tiktok/disconnect', methods=['POST'])
    def disconnect_tiktok():
        try:
            print("🔌 Disconnecting TikTok...")
            tiktok_auth.revoke_token()
            print("✅ TikTok disconnected successfully")
            
            return jsonify({
                'success': True,
                'message': 'Successfully disconnected from TikTok'
            })
        except Exception as e:
            print(f"❌ Error disconnecting: {e}")
            return jsonify({
                'success': False, 
                'error': str(e),
                'traceback': traceback.format_exc()
            }), 500

    @app.route('/api/tiktok/refresh', methods=['POST'])
    def refresh_tiktok_connection():
        try:
            print("🔄 Refreshing TikTok connection...")
            success = tiktok_auth.refresh_access_token()
            
            if success:
                print("✅ Connection refreshed successfully")
                return jsonify({
                    'success': True,
                    'message': 'Connection refreshed successfully'
                })
            else:
                print("❌ Failed to refresh connection")
                return jsonify({
                    'success': False,
                    'message': 'Failed to refresh connection - may need to reconnect'
                })
        except Exception as e:
            print(f"💥 Error refreshing connection: {e}")
            return jsonify({
                'success': False, 
                'error': str(e),
                'traceback': traceback.format_exc()
            }), 500

    @app.route('/api/tiktok/user-videos', methods=['GET'])
    def get_tiktok_user_videos():
        try:
            print("📹 Fetching user videos...")
            
            # Check authentication first
            if not tiktok_auth.validate_credentials():
                return jsonify({
                    'success': False, 
                    'error': 'Not authenticated with TikTok. Please connect your account first.'
                }), 401
            
            limit = request.args.get('limit', 10, type=int)
            videos = tiktok_manager.get_user_videos(limit=limit)
            
            if videos is not None:
                print(f"✅ Retrieved {len(videos)} videos")
                return jsonify({
                    'success': True,
                    'videos': videos
                })
            else:
                print("❌ Failed to retrieve videos")
                return jsonify({
                    'success': False, 
                    'error': 'Failed to retrieve videos'
                }), 500
                
        except Exception as e:
            print(f"💥 Error fetching videos: {e}")
            return jsonify({
                'success': False, 
                'error': str(e),
                'traceback': traceback.format_exc()
            }), 500

    @app.route('/api/tiktok/video/<video_id>', methods=['GET'])
    def get_tiktok_video(video_id):
        try:
            print(f"🎬 Fetching video info for ID: {video_id}")
            
            # Check authentication first
            if not tiktok_auth.validate_credentials():
                return jsonify({
                    'success': False, 
                    'error': 'Not authenticated with TikTok'
                }), 401
            
            video_data = tiktok_manager.get_video_info(video_id)
            if video_data:
                print("✅ Video info retrieved successfully")
                return jsonify({
                    'success': True,
                    'video': video_data
                })
            else:
                print("❌ Video not found")
                return jsonify({
                    'success': False, 
                    'error': 'Video not found'
                }), 404
                
        except Exception as e:
            print(f"💥 Error fetching video info: {e}")
            return jsonify({
                'success': False, 
                'error': str(e),
                'traceback': traceback.format_exc()
            }), 500

    @app.route('/api/tiktok/video/<video_id>', methods=['DELETE'])
    def delete_tiktok_video(video_id):
        try:
            print(f"🗑️ Deleting video ID: {video_id}")
            
            # Check authentication first
            if not tiktok_auth.validate_credentials():
                return jsonify({
                    'success': False, 
                    'error': 'Not authenticated with TikTok'
                }), 401
            
            success = tiktok_manager.delete_video(video_id)
            if success:
                print("✅ Video deleted successfully")
                return jsonify({
                    'success': True,
                    'message': 'Video deleted successfully'
                })
            else:
                print("❌ Failed to delete video")
                return jsonify({
                    'success': False,
                    'message': 'Failed to delete video. Note: TikTok API may not support video deletion.'
                })
                
        except Exception as e:
            print(f"💥 Error deleting video: {e}")
            return jsonify({
                'success': False, 
                'error': str(e),
                'traceback': traceback.format_exc()
            }), 500

    @app.route('/api/tiktok/upload-video', methods=['POST'])
    def upload_tiktok_video():
        video_path = None
        try:
            print("📤 Starting video upload...")
            
            # Check authentication first
            if not tiktok_auth.validate_credentials():
                return jsonify({
                    'success': False, 
                    'error': 'Not authenticated with TikTok. Please connect your account first.'
                }), 401
            
            # Get form data
            caption = request.form.get('caption', '')
            hashtags = request.form.get('hashtags', '')
            privacy_level = request.form.get('privacy_level', '0')
            
            print(f"📋 Received form data: caption='{caption}', hashtags='{hashtags}', privacy_level='{privacy_level}' (type: {type(privacy_level)})")
            
            # Get video file
            if 'video' not in request.files:
                return jsonify({
                    'success': False, 
                    'error': 'No video file provided'
                }), 400
                    
            video_file = request.files['video']
            if video_file.filename == '':
                return jsonify({
                    'success': False, 
                    'error': 'No video file selected'
                }), 400
            
            # Save video to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
                video_file.save(tmp_file)
                video_path = tmp_file.name
            
            # Upload video - pass privacy_level as integer
            result = tiktok_manager.upload_video_to_inbox(
                video_path=video_path,
                caption=caption,
                hashtags=hashtags,
                # privacy_level=int(privacy_level)  # Convert to int
            )
            
            # Clean up temp file
            if video_path and os.path.exists(video_path):
                os.unlink(video_path)
            
            if result:
                # Check if result contains an error
                if isinstance(result, dict) and 'error' in result:
                    error_type = result['error']
                    
                    # Handle unaudited app restriction (now this should be rare since we use inbox fallback)
                    if error_type == 'unaudited_app_restriction':
                        return jsonify({
                            'success': False,
                            'error': 'unaudited_app',
                            'message': result['message'],
                            'solution': result.get('solution', ''),
                            'details': {
                                'error_code': result.get('code'),
                                'current_privacy': result.get('current_privacy'),
                                'allowed_privacy': result.get('allowed_privacy'),
                                'suggestion': 'Try using inbox upload or apply for TikTok app review'
                            }
                        }), 403
                    
                    # Handle rate limiting
                    elif error_type == 'rate_limited':
                        return jsonify({
                            'success': False,
                            'error': 'rate_limited',
                            'message': result['message'],
                            'retry_after': 1800,
                            'details': {
                                'error_code': result.get('code'),
                                'suggested_action': 'Wait 15-30 minutes before trying again'
                            }
                        }), 429
                    
                    elif result.get('upload_successful'):
                        # Upload worked but publish failed
                        return jsonify({
                            'success': False,
                            'error': 'upload_successful_publish_failed',
                            'message': f"Video uploaded successfully but publishing failed: {result['message']}",
                            'details': {
                                'upload_successful': True,
                                'publish_successful': False,
                                'publish_id': result.get('publish_id'),
                                'error_code': result.get('code')
                            }
                        }), 202
                    else:
                        return jsonify({
                            'success': False,
                            'error': result['error'],
                            'message': result['message'],
                            'code': result.get('code')
                        }), 400
                
                # Handle inbox upload success
                elif isinstance(result, dict) and result.get('inbox_upload'):
                    return jsonify({
                        'success': True,
                        'inbox_upload': True,
                        'message': result['message'],
                        'instructions': result.get('instructions', []),
                        'details': {
                            'upload_successful': True,
                            'publish_successful': False,
                            'requires_manual_publish': True,
                            'publish_id': result.get('publish_id'),
                            'suggested_caption': result.get('suggested_caption'),
                            'suggested_hashtags': result.get('suggested_hashtags')
                        }
                    })
                
                # Handle complete success (Direct Post worked)
                elif isinstance(result, dict) and result.get('publish_successful'):
                    return jsonify({
                        'success': True,
                        'video': result,
                        'message': 'Video uploaded and published successfully!',
                        'details': {
                            'upload_successful': True,
                            'publish_successful': True,
                            'method': 'direct_post'
                        }
                    })
                
                else:
                    # Generic success
                    return jsonify({
                        'success': True,
                        'video': result,
                        'message': 'Video processed successfully!'
                    })
            else:
                return jsonify({
                    'success': False,
                    'error': 'upload_failed',
                    'message': 'Failed to upload video. Check server logs for details.'
                }), 500
                
        except Exception as e:
            # Clean up temp file if it exists
            if video_path and os.path.exists(video_path):
                try:
                    os.unlink(video_path)
                except:
                    pass
            
            error_str = str(e)
            
            # Handle rate limit errors that might come from requests
            if 'spam_risk' in error_str or 'too_many_pending' in error_str:
                return jsonify({
                    'success': False,
                    'error': 'rate_limited',
                    'message': 'TikTok is temporarily rate limiting uploads. Please wait 15-30 minutes before trying again.',
                    'retry_after': 1800
                }), 429
            
            return jsonify({
                'success': False, 
                'error': str(e),
                'traceback': traceback.format_exc()
            }), 500


    @app.route('/api/tiktok/user-info', methods=['GET'])
    def get_tiktok_user_info():
        try:
            print("👤 Fetching user info...")
            
            # Check authentication first
            if not tiktok_auth.validate_credentials():
                return jsonify({
                    'success': False, 
                    'error': 'Not authenticated with TikTok'
                }), 401
            
            user_info = tiktok_manager.get_user_info()
            if user_info:
                print("✅ User info retrieved successfully")
                return jsonify({
                    'success': True,
                    'user': user_info
                })
            else:
                print("❌ Failed to get user info")
                return jsonify({
                    'success': False, 
                    'error': 'Failed to get user info'
                }), 500
                
        except Exception as e:
            print(f"💥 Error fetching user info: {e}")
            return jsonify({
                'success': False, 
                'error': str(e),
                'traceback': traceback.format_exc()
            }), 500