#!/usr/bin/env python3
"""
Manual token exchange script for YouTube OAuth
Use this if you have an authorization code but the OAuth flow didn't complete
"""

import os
import requests
import json
from dotenv import load_dotenv

def exchange_code_for_tokens(auth_code):
    """Exchange authorization code for access tokens"""
    load_dotenv()
    
    client_id = os.getenv('YOUTUBE_CLIENT_ID')
    client_secret = os.getenv('YOUTUBE_CLIENT_SECRET')
    redirect_uri = os.getenv('YOUTUBE_REDIRECT_URI')
    
    if not all([client_id, client_secret, redirect_uri]):
        print("❌ Missing YouTube OAuth credentials in .env file")
        return False
    
    token_url = "https://oauth2.googleapis.com/token"
    
    try:
        response = requests.post(
            token_url,
            headers={
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret
            }
        )
        response.raise_for_status()
        token_data = response.json()
        
        # Save tokens to file
        token_file = os.getenv('YOUTUBE_TOKEN_FILE', 'youtube_tokens.json')
        tokens = {
            'access_token': token_data["access_token"],
            'refresh_token': token_data.get("refresh_token"),
            'expires_at': None  # Will be calculated when needed
        }
        
        with open(token_file, 'w') as f:
            json.dump(tokens, f, indent=2)
        
        print("✅ Tokens saved successfully!")
        print(f"Access token: {token_data['access_token'][:20]}...")
        if token_data.get('refresh_token'):
            print(f"Refresh token: {token_data['refresh_token'][:20]}...")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error exchanging code for tokens: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Response content: {e.response.text}")
        return False

if __name__ == "__main__":
    print("YouTube Manual Token Exchange")
    print("=" * 40)
    
    # Extract the code from the URL you provided
    auth_code = "4/0AVMBsJgXck_xr9vsCLR7U48Z-EiM2GqpallUlSSfuWi_ixzOMb8oXV6MMsy3lyEmviJinA"
    
    print(f"Using authorization code: {auth_code[:20]}...")
    
    if exchange_code_for_tokens(auth_code):
        print("\n🎉 Success! You can now use YouTube Shorts functionality.")
        print("The connection status should update automatically.")
    else:
        print("\n❌ Failed to exchange tokens. Please try the OAuth flow again.")
