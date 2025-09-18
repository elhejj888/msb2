"""
JWT utilities for authentication
"""
from functools import wraps
from flask import request, jsonify, current_app
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
import jwt
from models import User

def jwt_required_custom(f):
    """
    Custom JWT required decorator that handles authentication
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            # Try to verify JWT token
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            
            if not user_id:
                return jsonify({'success': False, 'error': 'Invalid token: No user identity'}), 401
            
            # Convert user_id to int if it's a string
            try:
                user_id = int(user_id)
            except (ValueError, TypeError):
                return jsonify({'success': False, 'error': 'Invalid token: Invalid user ID format'}), 401
            
            # Verify user exists
            user = User.query.get(user_id)
            if not user or not user.is_active:
                return jsonify({'success': False, 'error': 'User not found or inactive'}), 401
            
            # Add user to kwargs for the route function
            kwargs['current_user'] = user
            kwargs['current_user_id'] = user_id
            
            return f(*args, **kwargs)
            
        except Exception as e:
            return jsonify({'success': False, 'error': f'Authentication failed: {str(e)}'}), 401
    
    return decorated

def get_current_user_from_token():
    """
    Get current user from JWT token without decorator
    
    Returns:
        tuple: (user_id, user) or (None, None) if invalid
    """
    try:
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        
        if not user_id:
            return None, None
        
        # Convert user_id to int if it's a string
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            return None, None
        
        # Verify user exists
        user = User.query.get(user_id)
        if not user or not user.is_active:
            return None, None
        
        return user_id, user
        
    except Exception as e:
        print(f"Error getting user from token: {e}")
        return None, None

def extract_user_id_from_request():
    """
    Extract user ID from JWT token in request headers
    
    Returns:
        int or None: User ID if valid token, None otherwise
    """
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header.split(' ')[1]
        
        # Decode token without verification first to get user ID
        # This is just for extracting the user ID, actual verification happens elsewhere
        decoded = jwt.decode(token, options={"verify_signature": False})
        user_id = decoded.get('sub')
        
        if user_id:
            return int(user_id)
        
        return None
        
    except Exception as e:
        print(f"Error extracting user ID from request: {e}")
        return None
