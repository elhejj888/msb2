import os
from datetime import datetime
from dotenv import load_dotenv
from x.controller import XManager

def create_tweets(x_manager):
    """
    Function to handle tweet creation process
    """
    # Ask user for number of tweets
    while True:
        try:
            num_tweets = int(input("How many tweets would you like to create? "))
            if num_tweets > 0:
                break
            else:
                print("Please enter a positive number.")
        except ValueError:
            print("Please enter a valid number.")
    
    # Track created tweets
    created_tweets = []
    
    # Loop through each tweet
    for tweet_num in range(1, num_tweets + 1):
        print(f"\n=== Creating Tweet #{tweet_num} ===")
        
        # Get tweet text
        while True:
            text = input(f"Enter text for tweet #{tweet_num} (max 280 chars): ")
            if len(text) <= 280:
                break
            else:
                print(f"Text is {len(text)} characters. Please keep it under 280 characters.")
        
        # Ask if user wants to upload media
        media_path = None
        include_media = input("Do you want to upload media with this tweet? (y/n): ").lower()
        if include_media == 'y':
            print("Please select a media file from the dialog box...")
            media_path = select_media()
            if not media_path:
                print("No media selected. Creating tweet without media.")
        
        # Ask if this is a reply
        reply_to_id = None
        is_reply = input("Is this a reply to another tweet? (y/n): ").lower()
        if is_reply == 'y':
            reply_to_id = input("Enter the tweet ID to reply to: ")
        
        # Create the tweet
        tweet_data = x_manager.create_tweet(
            text=text,
            media_path=media_path,
            reply_to_tweet_id=reply_to_id
        )
        
        if tweet_data:
            created_tweets.append(tweet_data)
            print(f"Tweet #{tweet_num} created successfully!")
            print(f"Tweet URL: {tweet_data.get('url')}")
        else:
            print(f"Failed to create tweet #{tweet_num}")
            retry_tweet = input("Would you like to retry this tweet? (y/n): ").lower()
            if retry_tweet == 'y':
                # Decrement the counter to retry this tweet number
                tweet_num -= 1
    
    # Display summary of created tweets
    print("\n=== Tweet Creation Summary ===")
    if created_tweets:
        print(f"Successfully created {len(created_tweets)} tweets:")
        for i, tweet in enumerate(created_tweets, 1):
            print(f"{i}. Tweet ID: {tweet.get('id')}")
            print(f"   URL: {tweet.get('url')}")
            print(f"   Text: {tweet.get('text')[:50]}...")
    else:
        print("No tweets were created successfully.")
    
    # Record operation results
    with open("x_operations_log.txt", "a") as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"\n{timestamp} - Created {len(created_tweets)} tweets")
        for tweet in created_tweets:
            f.write(f"\n{timestamp} - Created tweet: {tweet.get('id')}")

def read_all_tweets(x_manager):
    """
    Function to handle reading all tweets from the user with retry logic
    """
    # Get number of tweets to retrieve
    limit = 10  # Default limit
    try:
        user_limit = input("How many tweets would you like to retrieve? (default: 10): ")
        if user_limit:
            limit = int(user_limit)
            # Ensure minimum of 5 for X API
            if limit < 5:
                print("Minimum 5 tweets required by X API. Setting to 5.")
                limit = 5
    except ValueError:
        print("Invalid input. Using default limit of 10 tweets.")
    
    # Get the tweets with retry logic
    tweets = x_manager.get_user_tweets_with_retry(limit=limit)
    
    # Display the tweets
    if tweets:
        print(f"\n=== Latest {len(tweets)} Tweets ===")
        for i, tweet in enumerate(tweets, 1):
            print(f"{i}. Posted: {tweet['created_at']}")
            print(f"   Text: {tweet['text'][:50]}..." if len(tweet['text']) > 50 else f"   Text: {tweet['text']}")
            print(f"   Likes: {tweet['likes']} | Retweets: {tweet['retweets']} | Replies: {tweet['replies']}")
            print(f"   URL: {tweet['url']}")
            print()
            
        # Ask if user wants to view a specific tweet in detail
        while True:
            view_tweet = input("Enter the number of a tweet to view in detail (or 0 to return to main menu): ")
            try:
                tweet_num = int(view_tweet)
                if tweet_num == 0:
                    break
                elif 1 <= tweet_num <= len(tweets):
                    # Get detailed tweet information
                    tweet_detail = x_manager.get_tweet(tweets[tweet_num-1]["id"])
                    if tweet_detail:
                        print("\n=== Tweet Details ===")
                        print(f"Posted: {tweet_detail['created_at']}")
                        print(f"Likes: {tweet_detail['likes']}")
                        print(f"Retweets: {tweet_detail['retweets']}")
                        print(f"Replies: {tweet_detail['replies']}")
                        print(f"Quotes: {tweet_detail['quotes']}")
                        print(f"URL: {tweet_detail['url']}")
                        print("\nText:")
                        print(tweet_detail['text'])
                    else:
                        print("Failed to retrieve detailed tweet information.")
                else:
                    print("Invalid tweet number.")
            except ValueError:
                print("Please enter a valid number.")
    else:
        print("No tweets found or failed to retrieve tweets.")

def delete_tweet(x_manager):
    """
    Function to handle deleting a tweet
    """
    # First show recent tweets
    print("Retrieving recent tweets...")
    tweets = x_manager.get_user_tweets(limit=10)
    
    if not tweets:
        print("No tweets found or failed to retrieve tweets.")
        return
    
    # Display the tweets
    print("\n=== Recent Tweets ===")
    for i, tweet in enumerate(tweets, 1):
        print(f"{i}. Posted: {tweet['created_at']}")
        print(f"   Text: {tweet['text'][:50]}..." if len(tweet['text']) > 50 else f"   Text: {tweet['text']}")
        print(f"   URL: {tweet['url']}")
        print()
    
    # Ask which tweet to delete
    while True:
        try:
            tweet_num = int(input("Enter the number of the tweet you want to delete (or 0 to return to main menu): "))
            if tweet_num == 0:
                return
            elif 1 <= tweet_num <= len(tweets):
                selected_tweet = tweets[tweet_num-1]
                break
            else:
                print("Invalid tweet number.")
        except ValueError:
            print("Please enter a valid number.")
    
    # Confirm deletion
    confirm = input(f"Are you sure you want to delete this tweet? (y/n): ").lower()
    if confirm != 'y':
        print("Deletion cancelled.")
        return
    
    # Delete the tweet
    success = x_manager.delete_tweet(selected_tweet["id"])
    
    if success:
        print(f"Successfully deleted tweet: {selected_tweet['url']}")
        # Record operation in log
        with open("x_operations_log.txt", "a") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"\n{timestamp} - Deleted tweet: {selected_tweet['url']}")
    else:
        print("Failed to delete tweet.")

def display_menu():
    """
    Display the main menu
    """
    print("\n==== X (Twitter) Manager ====")
    print("1. Create Tweet(s)")
    print("2. Read All Tweets")
    print("3. Delete Tweet")
    print("4. Re-authenticate")
    print("0. Exit Program")
    print("=============================")


def main():
    load_dotenv()
    x_manager = XManager()
    
    if not x_manager.auth.access_token:
        print("Error: Failed to authenticate with X. Please check your API credentials.")
        return
    
    while True:
        display_menu()
        try:
            choice = input("Enter your choice (0-4): ")
            if choice == '1':
                create_tweets(x_manager)
            elif choice == '2':
                read_all_tweets(x_manager)
            elif choice == '3':
                delete_tweet(x_manager)
            elif choice == '4':
                print("Starting re-authentication process...")
                auth_code = x_manager.auth.start_oauth_flow()
                if auth_code:
                    x_manager.auth.exchange_code_for_tokens(auth_code)
                    print("Re-authentication successful!")
                else:
                    print("Re-authentication failed.")
            elif choice == '0':
                print("Exiting program. Goodbye!")
                break
            else:
                print("Invalid choice. Please enter a number between 0 and 4.")
        except Exception as e:
            print(f"An error occurred: {e}")
            print("Returning to main menu.")

if __name__ == "__main__":
    main()