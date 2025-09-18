from flask import jsonify, request
from .controller import PinterestManager
import tempfile
import os
from jwt_utils import jwt_required_custom, get_current_user_from_token
from connection_service import ConnectionService

def setup_pinterest_routes(app):
    # Do not create a global manager to avoid shared tokens

    @app.route('/api/pinterest/validate-credentials', methods=['GET'])
    @jwt_required_custom
    def validate_pinterest_credentials(current_user=None, current_user_id=None):
        try:
            manager = PinterestManager(user_id=current_user_id)
            is_valid = manager.validate_credentials()
            return jsonify({
                'success': True,
                'is_valid': is_valid
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/pinterest/boards', methods=['GET'])
    @jwt_required_custom
    def get_pinterest_boards(current_user=None, current_user_id=None):
        try:
            manager = PinterestManager(user_id=current_user_id)
            boards = manager.list_boards()
            if boards is not None:
                return jsonify({
                    'success': True,
                    'boards': boards
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to retrieve boards'}), 500
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/pinterest/boards', methods=['POST'])
    @jwt_required_custom
    def create_pinterest_board(current_user=None, current_user_id=None):
        try:
            data = request.get_json()
            name = data.get('name')
            description = data.get('description')
            privacy = data.get('privacy', 'PUBLIC')
            
            if not name:
                return jsonify({'success': False, 'error': 'Board name is required'}), 400
            
            manager = PinterestManager(user_id=current_user_id)
            board_data = manager.create_board(
                name=name,
                description=description,
                privacy=privacy
            )
            
            if board_data:
                return jsonify({
                    'success': True,
                    'board': board_data
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to create board'}), 500
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/pinterest/pins', methods=['POST'])
    @jwt_required_custom
    def create_pinterest_pin(current_user=None, current_user_id=None):
        try:
            data = request.get_json()
            board_id = data.get('board_id')
            title = data.get('title', '')
            description = data.get('description', '')
            link = data.get('link')
            image_base64 = data.get('image_base64')
            
            if not board_id:
                return jsonify({'success': False, 'error': 'Board ID is required'}), 400
            
            if not image_base64:
                return jsonify({'success': False, 'error': 'Image is required'}), 400
            
            # Save base64 image to temp file
            try:
                import base64
                image_data = base64.b64decode(image_base64.split(',')[1])
                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                    tmp_file.write(image_data)
                    image_path = tmp_file.name
            except Exception as e:
                return jsonify({'success': False, 'error': f'Error processing image: {str(e)}'}), 400
            
            manager = PinterestManager(user_id=current_user_id)
            pin_data = manager.create_pin(
                board_id=board_id,
                image_path=image_path,
                title=title,
                description=description,
                link=link
            )
            
            # Clean up temp file
            if image_path and os.path.exists(image_path):
                os.unlink(image_path)
            
            if pin_data:
                return jsonify({
                    'success': True,
                    'pin': pin_data
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to create pin'}), 500
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/pinterest/pins', methods=['GET'])
    @jwt_required_custom
    def get_pinterest_pins(current_user=None, current_user_id=None):
        try:
            limit = request.args.get('limit', 10, type=int)
            manager = PinterestManager(user_id=current_user_id)
            pins = manager.get_all_pins()
            
            if pins is not None:
                # Apply limit if needed
                if limit and len(pins) > limit:
                    pins = pins[:limit]
                    
                return jsonify({
                    'success': True,
                    'pins': pins
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to retrieve pins'}), 500
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/pinterest/pins/<pin_id>', methods=['GET'])
    @jwt_required_custom
    def get_pinterest_pin(current_user=None, current_user_id=None, pin_id=None):
        try:
            manager = PinterestManager(user_id=current_user_id)
            pin_data = manager.get_pin(pin_id)
            if pin_data:
                return jsonify({
                    'success': True,
                    'pin': pin_data
                })
            else:
                return jsonify({'success': False, 'error': 'Pin not found'}), 404
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/pinterest/pins/<pin_id>', methods=['DELETE'])
    @jwt_required_custom
    def delete_pinterest_pin(current_user=None, current_user_id=None, pin_id=None):
        try:
            manager = PinterestManager(user_id=current_user_id)
            success = manager.delete_pin(pin_id)
            return jsonify({
                'success': success,
                'message': 'Pin deleted successfully' if success else 'Failed to delete pin'
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/pinterest/connection-status', methods=['GET'])
    @jwt_required_custom
    def get_pinterest_connection_status(current_user=None, current_user_id=None):
        try:
            # Check database connection status first
            connection_status = ConnectionService.get_user_connection_status(current_user_id, 'pinterest')
            
            if connection_status['connected']:
                return jsonify({
                    'success': True,
                    'status': {
                        'connected': True,
                        'username': connection_status['username'],
                        'message': f'Connected to Pinterest as @{connection_status["username"]}' if connection_status['username'] else 'Connected to Pinterest'
                    }
                })
            else:
                return jsonify({
                    'success': True,
                    'status': {
                        'connected': False,
                        'message': 'Not connected to Pinterest'
                    }
                })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/pinterest/connect', methods=['POST'])
    @jwt_required_custom
    def connect_pinterest(current_user=None, current_user_id=None):
        try:
            manager = PinterestManager(user_id=current_user_id)
            # This will trigger the OAuth flow
            is_valid = manager.validate_credentials()
            if is_valid:
                # Get user info from Pinterest API to check account exclusivity
                try:
                    user_info = manager.get_user_info()  # This should return user ID and username
                    if not user_info:
                        return jsonify({
                            'success': False,
                            'error': 'Failed to get user information from Pinterest'
                        }), 500
                    
                    platform_user_id = str(user_info.get('id', ''))
                    platform_username = user_info.get('username', '')
                    
                    print(f"Pinterest connection attempt - User: {current_user_id}, Platform User ID: {platform_user_id}, Username: {platform_username}")
                    
                    if not platform_user_id:
                        return jsonify({
                            'success': False,
                            'error': 'Failed to get user ID from Pinterest'
                        }), 500
                    
                    # Check account exclusivity and create connection
                    connection_result = ConnectionService.create_connection(
                        user_id=current_user_id,
                        platform='pinterest',
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
                            'message': f'Successfully connected to Pinterest as @{platform_username}!',
                            'username': platform_username
                        })
                    else:
                        # Account exclusivity violation
                        if connection_result['error'] == 'account_unavailable':
                            return jsonify({
                                'success': False,
                                'error': 'This Pinterest account is already connected to another user',
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
                    'error': 'Failed to connect to Pinterest'
                })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/pinterest/disconnect', methods=['POST'])
    @jwt_required_custom
    def disconnect_pinterest(current_user=None, current_user_id=None):
        try:
            # Disconnect from database first
            disconnect_result = ConnectionService.disconnect_user_platform(current_user_id, 'pinterest')
            
            if disconnect_result['success']:
                # Also try to disconnect from Pinterest manager if available
                try:
                    manager = PinterestManager(user_id=current_user_id)
                    manager.revoke_token()
                except Exception as e:
                    print(f"Warning: Failed to disconnect from Pinterest manager: {e}")
                
                return jsonify({
                    'success': True,
                    'message': 'Successfully disconnected from Pinterest'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Failed to disconnect: {disconnect_result["error"]}'
                })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500