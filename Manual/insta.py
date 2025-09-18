import os
import requests
import json
from datetime import datetime
from insta.controller import InstagramManager
from insta.utils import select_images
from dotenv import load_dotenv

def setup_environment():
    load_dotenv()
    print("=== Instagram Manager Setup ===")
    print("Required environment variables:")
    print("- INSTAGRAM_ACCESS_TOKEN")
    print("- INSTAGRAM_USER_ID")
    print("- IMGBB_API_KEY or Cloudinary credentials")
    
    instagram_token = os.getenv('INSTAGRAM_ACCESS_TOKEN')
    instagram_user_id = os.getenv('INSTAGRAM_USER_ID')
    imgbb_key = os.getenv('IMGBB_API_KEY')
    cloudinary_name = os.getenv('CLOUDINARY_CLOUD_NAME')
    
    print("\nCurrent setup status:")
    print(f"Instagram Access Token: {'Configured' if instagram_token else 'Missing'}")
    print(f"Instagram User ID: {'Configured' if instagram_user_id else 'Missing'}")
    print(f"ImgBB API Key: {'Configured' if imgbb_key else 'Missing'}")
    print(f"Cloudinary: {'Configured' if cloudinary_name else 'Missing'}")
    
    return all([instagram_token, instagram_user_id]) and any([imgbb_key, cloudinary_name])

def create_posts(manager):
    """
    Function to handle post creation process
    """
    while True:
        try:
            num_posts = int(input("How many posts would you like to create? "))
            if num_posts > 0:
                break
            else:
                print("Please enter a positive number.")
        except ValueError:
            print("Please enter a valid number.")
    
    created_posts = []
    
    for post_num in range(1, num_posts + 1):
        print(f"\n=== Creating Post #{post_num} ===")
        
        caption = input(f"Enter caption for post #{post_num}: ")
        
        post_type = input("Do you want to create a carousel post with multiple images? (y/n): ").lower()
        
        if post_type == 'y':
            print("Please select multiple image files from the dialog box...")
            image_paths = select_images(multiple=True)
            
            if not image_paths or len(image_paths) < 2:
                print("Not enough images selected for a carousel. Minimum 2 images required.")
                retry_post = input("Would you like to retry this post? (y/n): ").lower()
                if retry_post == 'y':
                    post_num -= 1
                continue
            
            post_data = manager.create_post(
                caption=caption,
                carousel_images=image_paths
            )
        else:
            print("Please select an image file from the dialog box...")
            image_path = select_images()
            
            if not image_path:
                print("No image selected. Cannot create post without an image.")
                retry_post = input("Would you like to retry this post? (y/n): ").lower()
                if retry_post == 'y':
                    post_num -= 1
                continue
            
            post_data = manager.create_post(
                caption=caption,
                image_path=image_path
            )
        
        if post_data:
            created_posts.append(post_data)
            print(f"✓ Post #{post_num} created successfully!")
            if 'permalink' in post_data:
                print(f"Post URL: {post_data['permalink']}")
        else:
            print(f"✗ Failed to create post #{post_num}")
            retry_post = input("Would you like to retry this post? (y/n): ").lower()
            if retry_post == 'y':
                post_num -= 1
    
    # Display summary
    print("\n=== Post Creation Summary ===")
    if created_posts:
        print(f"Successfully created {len(created_posts)} posts:")
        for i, post in enumerate(created_posts, 1):
            print(f"{i}. Post ID: {post.get('id')}")
            if 'permalink' in post:
                print(f"   URL: {post['permalink']}")
    else:
        print("No posts were created successfully.")
    
    # Log results
    with open("instagram_operations_log.txt", "a") as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"\n{timestamp} - Created {len(created_posts)} posts")
        for post in created_posts:
            f.write(f"\n{timestamp} - Created post: {post.get('id')}")

def read_all_posts(manager):
    """
    Function to handle reading all posts from the user
    """
    limit = 10
    try:
        user_limit = input("How many posts would you like to retrieve? (default: 10): ")
        if user_limit:
            limit = int(user_limit)
    except ValueError:
        print("Invalid input. Using default limit of 10 posts.")
    
    posts = manager.get_user_posts(limit=limit)
    
    if posts:
        print(f"\n=== Latest {len(posts)} Posts ===")
        for i, post in enumerate(posts, 1):
            print(f"{i}. Posted: {post['created_time']}")
            caption_preview = post['caption'][:50] + "..." if len(post['caption']) > 50 else post['caption']
            print(f"   Caption: {caption_preview}")
            print(f"   Media Type: {post['media_type']}")
            print(f"   Likes: {post['likes']} | Comments: {post['comments']}")
            print(f"   URL: {post['permalink']}")
            print()
        
        while True:
            view_post = input("Enter the number of a post to view in detail (or 0 to return to main menu): ")
            try:
                post_num = int(view_post)
                if post_num == 0:
                    break
                elif 1 <= post_num <= len(posts):
                    post_detail = manager.read_post(posts[post_num-1]["id"])
                    if post_detail:
                        print("\n=== Post Details ===")
                        print(f"Posted: {post_detail['created_time']}")
                        print(f"Media Type: {post_detail['media_type']}")
                        print(f"Likes: {post_detail['likes']}")
                        print(f"Comments: {post_detail['comments']}")
                        print(f"URL: {post_detail['permalink']}")
                        print("\nCaption:")
                        print(post_detail['caption'])
                        
                        if post_detail['image_url']:
                            print(f"\nImage URL: {post_detail['image_url']}")
                    else:
                        print("Failed to retrieve detailed post information.")
                else:
                    print("Invalid post number.")
            except ValueError:
                print("Please enter a valid number.")
    else:
        print("No posts found or failed to retrieve posts.")

def delete_post(manager):
    """
    Function to handle deleting a post
    """
    print("Retrieving recent posts...")
    posts = manager.get_user_posts(limit=10)
    
    if not posts:
        print("No posts found or failed to retrieve posts.")
        return
    
    print("\n=== Recent Posts ===")
    for i, post in enumerate(posts, 1):
        print(f"{i}. Posted: {post['created_time']}")
        caption_preview = post['caption'][:50] + "..." if len(post['caption']) > 50 else post['caption']
        print(f"   Caption: {caption_preview}")
        print(f"   URL: {post['permalink']}")
        print()
    
    while True:
        try:
            post_num = int(input("Enter the number of the post you want to delete (or 0 to return to main menu): "))
            if post_num == 0:
                return
            elif 1 <= post_num <= len(posts):
                selected_post = posts[post_num-1]
                break
            else:
                print("Invalid post number.")
        except ValueError:
            print("Please enter a valid number.")
    
    confirm = input(f"Are you sure you want to delete this post? (y/n): ").lower()
    if confirm != 'y':
        print("Deletion cancelled.")
        return
    
    success = manager.delete_post(selected_post["id"])
    
    if success:
        print(f"Successfully deleted post: {selected_post['permalink']}")
        with open("instagram_operations_log.txt", "a") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"\n{timestamp} - Deleted post: {selected_post['permalink']}")
    else:
        print("Failed to delete post.")

def display_menu():
    print("\n==== Instagram Manager ====")
    print("1. Create Post(s)")
    print("2. Read All Posts")
    print("3. Delete Post")
    print("0. Exit Program")
    print("===========================")

def main():
    manager = InstagramManager()
    
    if not manager.validate_credentials():
        print("Error: Invalid credentials. Please check your .env file.")
        return
    
    while True:
        display_menu()
        try:
            choice = input("Enter your choice (0-3): ")
            if choice == '1':
                create_posts(manager)
            elif choice == '2':
                read_all_posts(manager)
            elif choice == '3':
                delete_post(manager)
            elif choice == '0':
                print("Exiting program. Goodbye!")
                break
            else:
                print("Invalid choice. Please enter a number between 0 and 3.")
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    if setup_environment():
        main()