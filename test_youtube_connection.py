#!/usr/bin/env python3
"""
Test script to verify YouTube connection restoration from database
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from youtube.auth import YouTubeAuth
from youtube.controller import YouTubeManager
from connection_service import ConnectionService

def test_youtube_connection_restoration(user_id):
    """Test YouTube connection restoration for a specific user"""
    print(f"Testing YouTube connection restoration for user {user_id}")
    print("=" * 50)
    
    # Check database connection status
    print("1. Checking database connection status...")
    connection_status = ConnectionService.get_user_connection_status(user_id, 'youtube')
    print(f"Database status: {connection_status}")
    
    if connection_status.get('success') and connection_status.get('connected'):
        print("✅ Database shows YouTube connection exists")
        
        # Test YouTube manager creation and token loading
        print("\n2. Creating YouTube manager...")
        youtube_manager = YouTubeManager(user_id=user_id)
        print(f"Access token loaded: {bool(youtube_manager.access_token)}")
        print(f"Refresh token loaded: {bool(youtube_manager.refresh_token)}")
        
        # Test connection restoration
        print("\n3. Testing connection restoration...")
        restored = youtube_manager.try_restore_connection()
        print(f"Connection restored: {restored}")
        
        if restored:
            # Test getting user info
            print("\n4. Testing user info retrieval...")
            user_info = youtube_manager.get_user_info()
            print(f"User info: {user_info}")
            
            if user_info:
                print("✅ YouTube connection fully restored!")
                return True
            else:
                print("❌ Failed to get user info")
                return False
        else:
            print("❌ Failed to restore connection")
            return False
    else:
        print("❌ No YouTube connection found in database")
        return False

if __name__ == "__main__":
    # Test with user ID 4 (from the console logs)
    test_user_id = 4
    success = test_youtube_connection_restoration(test_user_id)
    
    if success:
        print("\n🎉 YouTube connection restoration test PASSED")
    else:
        print("\n💥 YouTube connection restoration test FAILED")
