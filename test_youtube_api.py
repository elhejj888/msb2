#!/usr/bin/env python3
"""
Test YouTube API endpoints to debug connection persistence issue
"""
import requests
import json

def test_youtube_connection_status():
    """Test YouTube connection status endpoint"""
    print("Testing YouTube connection status...")
    
    # You'll need to get a valid JWT token from the browser's localStorage
    # For now, let's test without authentication to see what happens
    
    try:
        response = requests.get('http://localhost:5000/api/youtube/connection-status')
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 401:
            print("❌ Authentication required - need JWT token")
            return False
        elif response.status_code == 200:
            data = response.json()
            print(f"✅ Connection status: {data}")
            return True
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing connection status: {e}")
        return False

def test_with_jwt_token(jwt_token):
    """Test YouTube endpoints with JWT token"""
    headers = {
        'Authorization': f'Bearer {jwt_token}',
        'Content-Type': 'application/json'
    }
    
    print(f"Testing with JWT token: {jwt_token[:50]}...")
    
    try:
        # Test connection status
        response = requests.get('http://localhost:5000/api/youtube/connection-status', headers=headers)
        print(f"Connection Status - Code: {response.status_code}")
        print(f"Connection Status - Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status', {}).get('connected'):
                print("✅ YouTube is connected!")
                return True
            else:
                print("❌ YouTube is not connected")
                return False
        else:
            print(f"❌ Connection status check failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing with JWT: {e}")
        return False

if __name__ == "__main__":
    print("YouTube API Test")
    print("=" * 40)
    
    # First test without authentication
    test_youtube_connection_status()
    
    print("\n" + "=" * 40)
    print("To test with authentication:")
    print("1. Open browser and login to the app")
    print("2. Open browser console (F12)")
    print("3. Run: localStorage.getItem('token')")
    print("4. Copy the JWT token")
    print("5. Run: python test_youtube_api.py <jwt_token>")
    
    # If JWT token provided as command line argument
    import sys
    if len(sys.argv) > 1:
        jwt_token = sys.argv[1]
        print(f"\nTesting with provided JWT token...")
        test_with_jwt_token(jwt_token)
