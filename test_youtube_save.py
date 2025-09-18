#!/usr/bin/env python3
"""
Test script to simulate YouTube connection save process
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from connection_service import ConnectionService

def test_youtube_connection_save():
    """Test saving a YouTube connection to database"""
    print("Testing YouTube connection save to database")
    print("=" * 50)
    
    # Test data
    test_user_id = 4
    test_platform_user_id = "test_youtube_channel_123"
    test_platform_username = "TestYouTubeChannel"
    test_access_token = "test_access_token_12345"
    test_refresh_token = "test_refresh_token_67890"
    
    print(f"Test data:")
    print(f"  User ID: {test_user_id}")
    print(f"  Platform User ID: {test_platform_user_id}")
    print(f"  Platform Username: {test_platform_username}")
    print(f"  Has Access Token: {bool(test_access_token)}")
    print(f"  Has Refresh Token: {bool(test_refresh_token)}")
    
    try:
        # Test connection creation
        print("\nAttempting to create connection...")
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
        
        print(f"Connection result: {connection_result}")
        
        if connection_result.get('success'):
            print("✅ Connection created successfully!")
            
            # Test retrieving the connection
            print("\nTesting connection retrieval...")
            status = ConnectionService.get_user_connection_status(test_user_id, 'youtube')
            print(f"Retrieved status: {status}")
            
            if status.get('success') and status.get('connected'):
                print("✅ Connection successfully retrieved!")
                return True
            else:
                print("❌ Failed to retrieve connection")
                return False
        else:
            print(f"❌ Failed to create connection: {connection_result.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Exception during connection test: {e}")
        import traceback
        traceback.print_exc()
        return False

def cleanup_test_connection():
    """Clean up test connection"""
    try:
        print("\nCleaning up test connection...")
        ConnectionService.disconnect_user_platform(4, 'youtube')
        print("✅ Test connection cleaned up")
    except Exception as e:
        print(f"Warning: Could not clean up test connection: {e}")

if __name__ == "__main__":
    success = test_youtube_connection_save()
    
    if success:
        print("\n🎉 YouTube connection save test PASSED")
        cleanup_test_connection()
    else:
        print("\n💥 YouTube connection save test FAILED")
        cleanup_test_connection()
