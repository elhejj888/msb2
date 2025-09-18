from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
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
from tiktok2.routes import setup_tiktok_routes
from youtube.routes import setup_youtube_routes


# Import database models and auth routes
from models import db, bcrypt, User
from auth_routes import setup_auth_routes, setup_jwt_error_handlers
from analytics.routes import setup_analytics_routes
from admin.routes import setup_admin_routes

app = Flask(__name__)
CORS(app)  # Enable CORS for Next.js frontend

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here-change-in-production')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=7)

# PostgreSQL Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://socialmanager_0kq0_user:kljNaNfCvgtHly8erePShitQbUzGiV0R@dpg-d35vapjipnbc739rfjig-a.oregon-postgres.render.com/socialmanager_0kq0')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Initialize extensions
db.init_app(app)
bcrypt.init_app(app)
jwt = JWTManager(app)
migrate = Migrate(app, db)

# Setup JWT error handlers
setup_jwt_error_handlers(jwt)

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

# Database initialization function
def create_tables():
    """Create database tables"""
    try:
        db.create_all()
        print("✅ Database tables created successfully")
    except Exception as e:
        print(f"❌ Error creating database tables: {str(e)}")

# Setup authentication routes first (they configure JWT properly)
setup_auth_routes(app)

# Setup routes for each platform
setup_pinterest_routes(app)
setup_reddit_routes(app, reddit_manager)
setup_facebook_routes(app, facebook_manager)
setup_instagram_routes(app, instagram_manager)
setup_x_routes(app, get_x_manager)  # Pass the lazy loader function
setup_tiktok_routes(app)  # TikTok manager is initialized inside the routes
setup_youtube_routes(app)  # YouTube routes

# Setup analytics routes AFTER JWT is fully configured
setup_analytics_routes(app, db)
setup_admin_routes(app, db)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Route to serve uploaded files (profile pictures)
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files like profile pictures"""
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except Exception as e:
        print(f"Error serving file {filename}: {str(e)}")
        return jsonify({'error': 'File not found'}), 404

# JWT token handlers
@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return jsonify({
        'success': False,
        'error': 'Token has expired'
    }), 401

@jwt.invalid_token_loader
def invalid_token_callback(error):
    return jsonify({
        'success': False,
        'error': 'Invalid token'
    }), 401

@jwt.unauthorized_loader
def missing_token_callback(error):
    return jsonify({
        'success': False,
        'error': 'Token is required'
    }), 401

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
        'timestamp': datetime.now().isoformat()
    })

# Initialize database tables when the app starts (both dev and prod)
with app.app_context():
    create_tables()
    print("🗄️ Database initialization complete")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)