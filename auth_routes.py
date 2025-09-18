# auth_routes.py - Complete version with login and profile endpoints

from flask import request, jsonify, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from PIL import Image
import os
import re
import uuid
import traceback
from models import db, User, UserSession
from flask_jwt_extended import decode_token
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
import jwt as jwt_lib

def debug_jwt_token(token):
    """Debug JWT token to understand what's wrong"""
    try:
        # Remove 'Bearer ' prefix if present
        if token.startswith('Bearer '):
            token = token[7:]
        
        # Try to decode without verification first to see payload
        unverified_payload = jwt_lib.decode(token, options={"verify_signature": False})
        print(f"Token payload: {unverified_payload}")
        
        # Check expiration
        import time
        current_time = time.time()
        exp_time = unverified_payload.get('exp', 0)
        
        print(f"Current time: {current_time}")
        print(f"Token exp time: {exp_time}")
        print(f"Token expired: {current_time > exp_time}")
        
        # Try to decode with verification
        decoded = decode_token(token)
        print(f"Token decoded successfully: {decoded}")
        return True, decoded
        
    except ExpiredSignatureError:
        print("Token has expired")
        return False, "Token has expired"
    except InvalidTokenError as e:
        print(f"Invalid token: {str(e)}")
        return False, f"Invalid token: {str(e)}"
    except Exception as e:
        print(f"Token debug error: {str(e)}")
        return False, f"Token debug error: {str(e)}"

def setup_jwt_error_handlers(jwt_manager):
    """Setup JWT error handlers - call this from your main app file"""
    @jwt_manager.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        print(f"Expired token - Header: {jwt_header}, Payload: {jwt_payload}")
        return jsonify({
            'success': False,
            'error': 'Token has expired',
            'error_type': 'expired_token'
        }), 401

    @jwt_manager.invalid_token_loader
    def invalid_token_callback(error):
        print(f"Invalid token error: {error}")
        return jsonify({
            'success': False,
            'error': 'Invalid token',
            'error_type': 'invalid_token',
            'details': str(error)
        }), 401

    @jwt_manager.unauthorized_loader
    def missing_token_callback(error):
        print(f"Missing token error: {error}")
        return jsonify({
            'success': False,
            'error': 'Token is required',
            'error_type': 'missing_token'
        }), 401

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    """Validate phone number format"""
    pattern = r'^[\+]?[1-9][\d]{0,15}$'
    return re.match(pattern, phone) is not None

def process_profile_picture(file, user_id):
    """Process and save profile picture"""
    if not file or file.filename == '':
        return None
    
    if not allowed_file(file.filename):
        raise ValueError("Invalid file type. Only PNG, JPG, JPEG, and GIF are allowed.")
    
    # Create filename with user ID and timestamp
    filename = secure_filename(file.filename)
    name, ext = os.path.splitext(filename)
    new_filename = f"profile_{user_id}_{int(datetime.now().timestamp())}{ext}"
    
    # Ensure uploads directory exists
    upload_dir = current_app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    
    file_path = os.path.join(upload_dir, new_filename)
    
    # Process image (resize if needed)
    try:
        image = Image.open(file)
        # Resize image to max 500x500 while maintaining aspect ratio
        image.thumbnail((500, 500), Image.Resampling.LANCZOS)
        image.save(file_path, optimize=True, quality=85)
        return new_filename
    except Exception as e:
        raise ValueError(f"Error processing image: {str(e)}")

def setup_auth_routes(app):
    
    @app.route('/api/auth/register', methods=['POST'])
    def register():
        try:
            # Debug: Print request content type and data
            print(f"Content-Type: {request.content_type}")
            print(f"Form data: {request.form}")
            print(f"Files: {request.files}")
            
            # Get form data
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            admin_code = (request.form.get('admin_code') or '').strip()
            role = (request.form.get('role') or 'user').strip().lower()
            country = request.form.get('country')
            age = request.form.get('age')
            phone_number = request.form.get('phone_number')
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            bio = request.form.get('bio')
            
            # Debug: Print received data
            print(f"Received data - Username: {username}, Email: {email}")
            
            # Validate required fields
            if not username or not email or not password:
                return jsonify({
                    'success': False,
                    'error': 'Username, email, and password are required'
                }), 400
            
            # Validate email format
            if not validate_email(email):
                return jsonify({
                    'success': False,
                    'error': 'Invalid email format'
                }), 400
            
            # Validate phone number if provided
            if phone_number and not validate_phone(phone_number):
                return jsonify({
                    'success': False,
                    'error': 'Invalid phone number format'
                }), 400
            
            # Validate age if provided
            if age:
                try:
                    age = int(age)
                    if age < 13 or age > 120:
                        return jsonify({
                            'success': False,
                            'error': 'Age must be between 13 and 120'
                        }), 400
                except ValueError:
                    return jsonify({
                        'success': False,
                        'error': 'Age must be a valid number'
                    }), 400

            # Role & admin code validation
            allowed_roles = {'user', 'admin'}
            if role not in allowed_roles:
                return jsonify({
                    'success': False,
                    'error': 'Invalid role'
                }), 400

            if role == 'admin':
                if admin_code != '201129':
                    return jsonify({
                        'success': False,
                        'error': 'Invalid or missing admin code'
                    }), 400
            
            # Check if username already exists
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                return jsonify({
                    'success': False,
                    'error': 'Username already exists'
                }), 400
            
            # Check if email already exists
            existing_email = User.query.filter_by(email=email).first()
            if existing_email:
                return jsonify({
                    'success': False,
                    'error': 'Email already exists'
                }), 400
            
            # Create new user
            user = User(
                username=username,
                email=email,
                role=role,
                country=country,
                age=age,
                phone_number=phone_number,
                first_name=first_name,
                last_name=last_name,
                bio=bio
            )
            
            # Set password
            try:
                user.set_password(password)
            except Exception as e:
                print(f"Error setting password: {str(e)}")
                return jsonify({
                    'success': False,
                    'error': 'Error processing password'
                }), 500
            
            # Add user to database to get ID
            try:
                db.session.add(user)
                db.session.flush()  # This assigns the ID without committing
                print(f"User created with ID: {user.id}")
            except Exception as e:
                print(f"Database error during user creation: {str(e)}")
                db.session.rollback()
                return jsonify({
                    'success': False,
                    'error': 'Database error during user creation'
                }), 500
            
            # Handle profile picture if provided
            profile_picture = None
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file and file.filename != '':
                    try:
                        profile_picture = process_profile_picture(file, user.id)
                        user.profile_picture = profile_picture
                        print(f"Profile picture processed: {profile_picture}")
                    except ValueError as e:
                        print(f"Profile picture error: {str(e)}")
                        db.session.rollback()
                        return jsonify({
                            'success': False,
                            'error': str(e)
                        }), 400
                    except Exception as e:
                        print(f"Unexpected profile picture error: {str(e)}")
                        db.session.rollback()
                        return jsonify({
                            'success': False,
                            'error': 'Error processing profile picture'
                        }), 500
            
            # Commit the user
            try:
                db.session.commit()
                print("User successfully committed to database")
            except Exception as e:
                print(f"Database commit error: {str(e)}")
                db.session.rollback()
                return jsonify({
                    'success': False,
                    'error': 'Failed to save user to database'
                }), 500
            
            # Generate JWT token (include role as additional claim)
            try:
                access_token = create_access_token(identity=str(user.id), additional_claims={'role': user.role})
                print("JWT token created successfully")
            except Exception as e:
                print(f"JWT token creation error: {str(e)}")
                return jsonify({
                    'success': False,
                    'error': 'Error creating authentication token'
                }), 500
            
            return jsonify({
                'success': True,
                'message': 'Account created successfully',
                'user': user.to_dict(),
                'access_token': access_token
            }), 201
            
        except Exception as e:
            print(f"Unexpected error in registration: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': f'Registration failed: {str(e)}'
            }), 500

    @app.route('/api/auth/login', methods=['POST'])
    def login():
        try:
            # Get JSON data
            data = request.get_json()
            
            if not data:
                return jsonify({
                    'success': False,
                    'error': 'No data provided'
                }), 400
            
            username_or_email = data.get('username_or_email')
            password = data.get('password')
            
            # Debug: Print received data
            print(f"Login attempt - Username/Email: {username_or_email}")
            
            # Validate required fields
            if not username_or_email or not password:
                return jsonify({
                    'success': False,
                    'error': 'Username/email and password are required'
                }), 400
            
            # Find user by username or email
            user = None
            if '@' in username_or_email:
                # It's an email
                user = User.query.filter_by(email=username_or_email).first()
            else:
                # It's a username
                user = User.query.filter_by(username=username_or_email).first()
            
            if not user:
                return jsonify({
                    'success': False,
                    'error': 'Invalid username/email or password'
                }), 401
            
            # Check password
            if not user.check_password(password):
                return jsonify({
                    'success': False,
                    'error': 'Invalid username/email or password'
                }), 401
            
            # Generate JWT token (include role as additional claim)
            try:
                access_token = create_access_token(identity=str(user.id), additional_claims={'role': user.role})
                print(f"Login successful for user: {user.username}")
            except Exception as e:
                print(f"JWT token creation error: {str(e)}")
                return jsonify({
                    'success': False,
                    'error': 'Error creating authentication token'
                }), 500
            
            # Update last login time
            try:
                user.last_login = datetime.utcnow()
                db.session.commit()
            except Exception as e:
                print(f"Error updating last login: {str(e)}")
                # Don't fail login if we can't update last login time
                pass
            
            return jsonify({
                'success': True,
                'message': 'Login successful',
                'user': user.to_dict(),
                'access_token': access_token
            }), 200
            
        except Exception as e:
            print(f"Unexpected error in login: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            return jsonify({
                'success': False,
                'error': f'Login failed: {str(e)}'
            }), 500

    @app.route('/api/auth/profile', methods=['GET'])
    @jwt_required()
    def get_profile():
        try:
            # Get user ID from JWT token
            user_id = get_jwt_identity()
            
            # Find user - convert string user_id to int
            user = User.query.get(int(user_id))
            if not user:
                return jsonify({
                    'success': False,
                    'error': 'User not found'
                }), 404
            
            return jsonify({
                'success': True,
                'user': user.to_dict()
            }), 200
            
        except Exception as e:
            print(f"Error in get_profile: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Failed to get user profile'
            }), 500

    @app.route('/api/auth/profile', methods=['PUT'])
    @jwt_required()
    def update_profile():
        try:
            # Debug: Print authorization header
            auth_header = request.headers.get('Authorization')
            print(f"Authorization header: {auth_header}")
            
            # Debug: Check token
            if auth_header:
                token = auth_header.replace('Bearer ', '')
                is_valid, result = debug_jwt_token(token)
                print(f"Token validation result: {is_valid}, {result}")
            
            # Get user ID from JWT token
            user_id = get_jwt_identity()
            print(f"User ID from token: {user_id}")
            
            # Find user - convert string user_id to int
            user = User.query.get(int(user_id))
            if not user:
                return jsonify({
                    'success': False,
                    'error': 'User not found'
                }), 404
            
            # Get form data
            email = request.form.get('email')
            phone_number = request.form.get('phone_number')
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            country = request.form.get('country')
            age = request.form.get('age')
            bio = request.form.get('bio')
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            
            # Validate email format if provided
            if email and not validate_email(email):
                return jsonify({
                    'success': False,
                    'error': 'Invalid email format'
                }), 400
            
            # Check if email already exists (for other users)
            if email and email != user.email:
                existing_email = User.query.filter_by(email=email).first()
                if existing_email:
                    return jsonify({
                        'success': False,
                        'error': 'Email already exists'
                    }), 400
            
            # Validate phone number if provided
            if phone_number and not validate_phone(phone_number):
                return jsonify({
                    'success': False,
                    'error': 'Invalid phone number format'
                }), 400
            
            # Validate age if provided
            if age:
                try:
                    age = int(age)
                    if age < 13 or age > 120:
                        return jsonify({
                            'success': False,
                            'error': 'Age must be between 13 and 120'
                        }), 400
                except ValueError:
                    return jsonify({
                        'success': False,
                        'error': 'Age must be a valid number'
                    }), 400
            
            # Handle password change
            if current_password or new_password:
                if not current_password:
                    return jsonify({
                        'success': False,
                        'error': 'Current password is required to change password'
                    }), 400
                
                if not new_password:
                    return jsonify({
                        'success': False,
                        'error': 'New password is required'
                    }), 400
                
                # Verify current password
                if not user.check_password(current_password):
                    return jsonify({
                        'success': False,
                        'error': 'Current password is incorrect'
                    }), 400
                
                # Set new password
                user.set_password(new_password)
            
            # Update user fields
            if email:
                user.email = email
            if phone_number is not None:
                user.phone_number = phone_number if phone_number else None
            if first_name is not None:
                user.first_name = first_name if first_name else None
            if last_name is not None:
                user.last_name = last_name if last_name else None
            if country is not None:
                user.country = country if country else None
            if age is not None:
                user.age = age if age else None
            if bio is not None:
                user.bio = bio if bio else None
            
            # Handle profile picture if provided
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file and file.filename != '':
                    try:
                        # Delete old profile picture if exists
                        if user.profile_picture:
                            old_file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], user.profile_picture)
                            if os.path.exists(old_file_path):
                                os.remove(old_file_path)
                        
                        # Process and save new profile picture
                        profile_picture = process_profile_picture(file, user.id)
                        user.profile_picture = profile_picture
                        print(f"Profile picture updated: {profile_picture}")
                    except ValueError as e:
                        print(f"Profile picture error: {str(e)}")
                        return jsonify({
                            'success': False,
                            'error': str(e)
                        }), 400
                    except Exception as e:
                        print(f"Unexpected profile picture error: {str(e)}")
                        return jsonify({
                            'success': False,
                            'error': 'Error processing profile picture'
                        }), 500
            
            # Save changes
            try:
                db.session.commit()
                print("Profile updated successfully")
            except Exception as e:
                print(f"Database commit error: {str(e)}")
                db.session.rollback()
                return jsonify({
                    'success': False,
                    'error': 'Failed to save profile changes'
                }), 500
            
            return jsonify({
                'success': True,
                'message': 'Profile updated successfully',
                'user': user.to_dict()
            }), 200
            
        except Exception as e:
            print(f"Profile update error: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            return jsonify({
                'success': False,
                'error': f'Profile update failed: {str(e)}'
            }), 500

    @app.route('/api/auth/logout', methods=['POST'])
    @jwt_required()
    def logout():
        try:
            # Get user ID from JWT token
            user_id = get_jwt_identity()
            
            # You can add token blacklisting here if needed
            # For now, just return success (frontend will remove token from localStorage)
            
            return jsonify({
                'success': True,
                'message': 'Logout successful'
            }), 200
            
        except Exception as e:
            print(f"Error in logout: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Logout failed'
            }), 500
