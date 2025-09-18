from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import os
import json
from datetime import datetime, timedelta
import base64
from werkzeug.utils import secure_filename
import tempfile
import sys

# Load environment variables
load_dotenv()

# Add current directory to Python path to ensure local imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import your existing managers
from reddit import RedditManager
from facebook import FacebookManager
from instagram import InstagramManager
from pinterest import PinterestManager
from pinterest.routes import setup_pinterest_routes
from reddit.routes import setup_reddit_routes
from facebook.routes import setup_facebook_routes
from instagram.routes import setup_instagram_routes
from x.routes import setup_x_routes

app = Flask(__name__)
CORS(app)  # Enable CORS for Next.js frontend

# Basic configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here-change-in-production')

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Initialize managers that are always available
facebook_manager = FacebookManager()
instagram_manager = InstagramManager()
pinterest_manager = PinterestManager()
reddit_manager = RedditManager()

# X Manager - Initialize lazily to avoid startup failures
x_manager = None

def get_x_manager():
    """Lazy initialization of X manager to avoid startup failures"""
    global x_manager
    if x_manager is None:
        try:
            from x import XManager
            x_manager = XManager()
        except Exception as e:
            print(f"Warning: Could not initialize X Manager: {str(e)}")
            x_manager = False  # Mark as failed to avoid repeated attempts
    return x_manager if x_manager is not False else None

# Setup routes for each platform
setup_pinterest_routes(app)
setup_reddit_routes(app, reddit_manager)
setup_facebook_routes(app, facebook_manager)
setup_instagram_routes(app, instagram_manager)
setup_x_routes(app, get_x_manager)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Route to serve uploaded files
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files like images and videos"""
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except Exception as e:
        print(f"Error serving file {filename}: {str(e)}")
        return jsonify({'error': 'File not found'}), 404

# Error handler
@app.errorhandler(Exception)
def handle_error(e):
    return jsonify({
        'success': False,
        'error': str(e)
    }), 500

# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'success': True,
        'message': 'API is running',
        'timestamp': datetime.now().isoformat(),
        'available_platforms': {
            'facebook': facebook_manager is not None,
            'instagram': instagram_manager is not None,
            'pinterest': pinterest_manager is not None,
            'reddit': reddit_manager is not None,
            'x': get_x_manager() is not None
        }
    })

# Platform status endpoint
@app.route('/api/platforms/status', methods=['GET'])
def platform_status():
    """Check the status of all platform managers"""
    x_mgr = get_x_manager()
    return jsonify({
        'success': True,
        'platforms': {
            'facebook': {
                'available': facebook_manager is not None,
                'authenticated': hasattr(facebook_manager, 'access_token') and facebook_manager.access_token is not None if facebook_manager else False
            },
            'instagram': {
                'available': instagram_manager is not None,
                'authenticated': hasattr(instagram_manager, 'access_token') and instagram_manager.access_token is not None if instagram_manager else False
            },
            'pinterest': {
                'available': pinterest_manager is not None,
                'authenticated': hasattr(pinterest_manager, 'access_token') and pinterest_manager.access_token is not None if pinterest_manager else False
            },
            'reddit': {
                'available': reddit_manager is not None,
                'authenticated': hasattr(reddit_manager, 'reddit') and reddit_manager.reddit is not None if reddit_manager else False
            },
            'x': {
                'available': x_mgr is not None,
                'authenticated': x_mgr.validate_credentials() if x_mgr else False
            }
        }
    })

if __name__ == '__main__':
    print("Starting Social Media Manager API...")
    print("Available platforms: Facebook, Instagram, Pinterest, Reddit, X (Twitter)")
    app.run(debug=True, host='0.0.0.0', port=5000)