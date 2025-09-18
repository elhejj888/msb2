import os
from datetime import datetime
import tkinter as tk
from tkinter import filedialog
from dotenv import load_dotenv
from facebook.controller import FacebookManager



def select_image():
    """Open file dialog to select an image"""
    root = tk.Tk()
    root.withdraw()
    
    file_path = filedialog.askopenfilename(
        title="Select Image",
        filetypes=[
            ("Image files", "*.jpg *.jpeg *.png *.gif"),
            ("All files", "*.*")
        ]
    )
    
    root.destroy()
    return file_path if file_path else None

def create_posts(facebook_manager):
    """Function to handle post creation process"""
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
        message = input(f"Enter message for post #{post_num}: ")
        
        link = None
        include_link = input("Do you want to include a link with this post? (y/n): ").lower()
        if include_link == 'y':
            link = input("Enter the URL to include: ")
        
        image_path = None
        include_image = input("Do you want to upload an image with this post? (y/n): ").lower()
        if include_image == 'y':
            print("Please select an image file from the dialog box...")
            image_path = select_image()
            if not image_path:
                print("No image selected. Creating post without image.")
        
        scheduled_time = None
        schedule = input("Do you want to schedule this post? (y/n): ").lower()
        if schedule == 'y':
            while True:
                try:
                    schedule_time = input("Enter schedule time (YYYY-MM-DD HH:MM, 24-hour format): ")
                    scheduled_time = datetime.strptime(schedule_time, "%Y-%m-%d %H:%M").timestamp()
                    break
                except ValueError:
                    print("Invalid date format. Please use YYYY-MM-DD HH:MM format.")
        
        post_data = facebook_manager.create_post(
            message=message,
            link=link,
            image_path=image_path,
            scheduled_time=scheduled_time
        )
        
        if post_data:
            created_posts.append(post_data)
            print(f"Post #{post_num} created successfully!")
            if 'permalink' in post_data:
                print(f"Post URL: {post_data['permalink']}")
            elif 'id' in post_data:
                print(f"Post ID: {post_data['id']}")
        else:
            print(f"Failed to create post #{post_num}")
            retry_post = input("Would you like to retry this post? (y/n): ").lower()
            if retry_post == 'y':
                post_num -= 1
    
    print("\n=== Post Creation Summary ===")
    if created_posts:
        print(f"Successfully created {len(created_posts)} posts:")
        for i, post in enumerate(created_posts, 1):
            print(f"{i}. Post ID: {post.get('id')}")
            if 'permalink' in post:
                print(f"   URL: {post['permalink']}")
            print(f"   Message: {post.get('message', '[No message]')[:50]}...")
    else:
        print("No posts were created successfully.")
    
    with open("facebook_operations_log.txt", "a") as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"\n{timestamp} - Created {len(created_posts)} posts")
        for post in created_posts:
            f.write(f"\n{timestamp} - Created post: {post.get('id')}")

def read_all_posts(facebook_manager):
    """Function to handle reading all posts from the page"""
    limit = 10
    try:
        user_limit = input("How many posts would you like to retrieve? (default: 10): ")
        if user_limit:
            limit = int(user_limit)
    except ValueError:
        print("Invalid input. Using default limit of 10 posts.")
    
    posts = facebook_manager.get_page_posts(limit=limit)
    
    if posts:
        print(f"\n=== Latest {len(posts)} Posts ===")
        for i, post in enumerate(posts, 1):
            print(f"{i}. Posted: {post['created_time']}")
            print(f"   Message: {post['message'][:50]}..." if len(post['message']) > 50 else post['message'])
            print(f"   Likes: {post['likes']} | Comments: {post['comments']} | Shares: {post['shares']}")
            print(f"   URL: {post['permalink']}")
            print()
            
        while True:
            view_post = input("Enter the number of a post to view in detail (or 0 to return to main menu): ")
            try:
                post_num = int(view_post)
                if post_num == 0:
                    break
                elif 1 <= post_num <= len(posts):
                    post_detail = facebook_manager.read_post(posts[post_num-1]["id"])
                    if post_detail:
                        print("\n=== Post Details ===")
                        print(f"Posted: {post_detail['created_time']}")
                        print(f"Likes: {post_detail['likes']}")
                        print(f"Comments: {post_detail['comments']}")
                        print(f"Shares: {post_detail['shares']}")
                        print(f"Reactions: {post_detail['reactions']}")
                        print(f"URL: {post_detail['permalink']}")
                        print("\nMessage:")
                        print(post_detail['message'])
                        
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

def update_post(facebook_manager):
    """Function to handle updating a post"""
    print("Retrieving recent posts...")
    posts = facebook_manager.get_page_posts(limit=10)
    
    if not posts:
        print("No posts found or failed to retrieve posts.")
        return
    
    print("\n=== Recent Posts ===")
    for i, post in enumerate(posts, 1):
        print(f"{i}. Posted: {post['created_time']}")
        print(f"   Message: {post['message'][:50]}..." if len(post['message']) > 50 else post['message'])
        print(f"   URL: {post['permalink']}")
        print()
    
    while True:
        try:
            post_num = int(input("Enter the number of the post you want to update (or 0 to return to main menu): "))
            if post_num == 0:
                return
            elif 1 <= post_num <= len(posts):
                selected_post = posts[post_num-1]
                break
            else:
                print("Invalid post number.")
        except ValueError:
            print("Please enter a valid number.")
    
    post_detail = facebook_manager.read_post(selected_post["id"])
    if not post_detail:
        print("Failed to retrieve post details.")
        return
    
    print("\n=== Current Post Content ===")
    print("\nMessage:")
    print(post_detail['message'])
    
    new_message = input("\nEnter new message for the post (leave empty to keep current): ")
    new_link = input("Enter new link for the post (leave empty to keep current): ")
    
    if new_message or new_link:
        success = facebook_manager.update_post(
            post_id=selected_post["id"],
            new_message=new_message if new_message else None,
            link=new_link if new_link else None
        )
        
        if success:
            print(f"Successfully updated post: {selected_post['permalink']}")
            with open("facebook_operations_log.txt", "a") as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"\n{timestamp} - Updated post: {selected_post['permalink']}")
        else:
            print("Failed to update post.")
    else:
        print("No changes made to the post.")

def delete_post(facebook_manager):
    """Function to handle deleting a post"""
    print("Retrieving recent posts...")
    posts = facebook_manager.get_page_posts(limit=10)
    
    if not posts:
        print("No posts found or failed to retrieve posts.")
        return
    
    print("\n=== Recent Posts ===")
    for i, post in enumerate(posts, 1):
        print(f"{i}. Posted: {post['created_time']}")
        print(f"   Message: {post['message'][:50]}..." if len(post['message']) > 50 else post['message'])
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
    
    success = facebook_manager.delete_post(selected_post["id"])
    
    if success:
        print(f"Successfully deleted post: {selected_post['permalink']}")
        with open("facebook_operations_log.txt", "a") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"\n{timestamp} - Deleted post: {selected_post['permalink']}")
    else:
        print("Failed to delete post.")

def display_menu():
    """Display the main menu"""
    print("\n==== Facebook Page Manager ====")
    print("1. Create Post(s)")
    print("2. Read All Posts")
    print("3. Update Post")
    print("4. Delete Post")
    print("0. Exit Program")
    print("=============================")

def main():
    load_dotenv()
    facebook_manager = FacebookManager()
    
    if not facebook_manager.validate_credentials():
        print("Error: Failed to validate Facebook credentials. Please check your access tokens.")
        return
    
    while True:
        display_menu()
        try:
            choice = input("Enter your choice (0-4): ")
            
            if choice == '1':
                create_posts(facebook_manager)
            elif choice == '2':
                read_all_posts(facebook_manager)
            elif choice == '3':
                update_post(facebook_manager)
            elif choice == '4':
                delete_post(facebook_manager)
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