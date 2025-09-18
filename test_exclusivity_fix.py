#!/usr/bin/env python3
"""
Test script to validate the exclusivity logic fix
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_connection_flow():
    """Test the complete connection flow with debugging"""
    try:
        from models import db, SocialMediaConnection, User
        from flaskapp import app
        from connection_service import ConnectionService
        
        with app.app_context():
            # Clear all connections first
            SocialMediaConnection.query.delete()
            db.session.commit()
            print("✅ Cleared all existing connections")
            
            # Test 1: Check availability when no connections exist
            print("\n🔍 Test 1: Check availability when no connections exist")
            result = ConnectionService.check_account_availability('reddit', 'test_user_123')
            print(f"Result: {result}")
            assert result['available'] == True, f"Expected available=True, got {result['available']}"
            print("✅ Test 1 passed")
            
            # Test 2: Create a connection
            print("\n🔍 Test 2: Create a new connection")
            create_result = ConnectionService.create_connection(
                user_id=1,
                platform='reddit',
                platform_user_id='test_user_123',
                platform_username='test_user'
            )
            print(f"Create result: {create_result}")
            assert create_result['success'] == True, f"Expected success=True, got {create_result['success']}"
            print("✅ Test 2 passed")
            
            # Test 3: Check availability for same account (should be unavailable)
            print("\n🔍 Test 3: Check availability for same account (should be unavailable)")
            result = ConnectionService.check_account_availability('reddit', 'test_user_123')
            print(f"Result: {result}")
            assert result['available'] == False, f"Expected available=False, got {result['available']}"
            print("✅ Test 3 passed")
            
            # Test 4: Check availability for different account (should be available)
            print("\n🔍 Test 4: Check availability for different account (should be available)")
            result = ConnectionService.check_account_availability('reddit', 'different_user_456')
            print(f"Result: {result}")
            assert result['available'] == True, f"Expected available=True, got {result['available']}"
            print("✅ Test 4 passed")
            
            # Test 5: Check availability for same user (should be available for updates)
            print("\n🔍 Test 5: Check availability for same user (should be available for updates)")
            result = ConnectionService.check_account_availability('reddit', 'test_user_123', current_user_id=1)
            print(f"Result: {result}")
            assert result['available'] == True, f"Expected available=True for same user, got {result['available']}"
            print("✅ Test 5 passed")
            
            # Test 6: Try to create connection for different user (should fail)
            print("\n🔍 Test 6: Try to create connection for different user (should fail)")
            create_result = ConnectionService.create_connection(
                user_id=2,
                platform='reddit',
                platform_user_id='test_user_123',
                platform_username='test_user'
            )
            print(f"Create result: {create_result}")
            assert create_result['success'] == False, f"Expected success=False, got {create_result['success']}"
            assert create_result['error'] == 'account_unavailable', f"Expected error='account_unavailable', got {create_result['error']}"
            print("✅ Test 6 passed")
            
            # Clean up
            SocialMediaConnection.query.delete()
            db.session.commit()
            print("\n✅ All tests passed! Exclusivity logic is working correctly.")
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    print("🚀 Testing account exclusivity logic...")
    success = test_connection_flow()
    if success:
        print("\n🎉 All tests completed successfully!")
    else:
        print("\n💥 Tests failed - exclusivity logic needs more work")
