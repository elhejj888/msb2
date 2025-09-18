#!/usr/bin/env python3
"""
Test script to simulate YouTube connection process and identify database save issues
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from models import db
from connection_service import ConnectionService
from dotenv import load_dotenv

def create_test_app():
    """Create a test Flask app with database context"""
    load_dotenv()
    
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://username:password@localhost/socialmanager')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    return app

def test_youtube_connection_save():
    """Test YouTube connection save process"""
    print("Testing YouTube Connection Save Process")
    print("=" * 50)
    
    app = create_test_app()
    
    with app.app_context():
        # Test data similar to what YouTube would provide
        test_user_id = 4  # From console logs
        test_platform_user_id = "UCtest123456789"  # YouTube channel ID format
        test_platform_username = "Pamod Ranasingha"  # From console logs
        test_access_token = "ya29.test_access_token_12345"
        test_refresh_token = "1//test_refresh_token_67890"
        
        print(f"Test Parameters:")
        print(f"  User ID: {test_user_id}")
        print(f"  Platform User ID: {test_platform_user_id}")
        print(f"  Platform Username: {test_platform_username}")
        print(f"  Has Access Token: {bool(test_access_token)}")
        print(f"  Has Refresh Token: {bool(test_refresh_token)}")
        
        try:
            # Test the exact same call that YouTube connect route makes
            print(f"\nCalling ConnectionService.create_connection...")
            connection_result = ConnectionService.create_connection(
                user_id=test_user_id,
                platform='youtube',
                platform_user_id=test_platform_user_id,
                platform_username=test_platform_username,
                access_token=test_access_token,
                additional_data={
                    'refresh_token': test_refresh_token
                }
            )
            
            print(f"Connection Result: {connection_result}")
            
            if connection_result.get('success'):
                print("✅ YouTube connection save test PASSED!")
                
                # Test retrieval
                print(f"\nTesting connection retrieval...")
                status = ConnectionService.get_user_connection_status(test_user_id, 'youtube')
                print(f"Retrieved Status: {status}")
                
                if status.get('success') and status.get('connected'):
                    print("✅ Connection successfully retrieved!")
                    return True
                else:
                    print("❌ Failed to retrieve saved connection")
                    return False
            else:
                print(f"❌ YouTube connection save test FAILED: {connection_result.get('error')}")
                return False
                
        except Exception as e:
            print(f"❌ Exception during test: {e}")
            import traceback
            traceback.print_exc()
            return False

def cleanup_test_data():
    """Clean up test data"""
    app = create_test_app()
    with app.app_context():
        try:
            print("\nCleaning up test data...")
            ConnectionService.disconnect_user_platform(4, 'youtube')
            print("✅ Test data cleaned up")
        except Exception as e:
            print(f"Warning: Could not clean up test data: {e}")

if __name__ == "__main__":
    success = test_youtube_connection_save()
    
    if success:
        print("\n🎉 YouTube connection save process works correctly!")
        cleanup_test_data()
    else:
        print("\n💥 YouTube connection save process has issues!")
        cleanup_test_data()
