import os
from datetime import datetime
from reddit.controller import RedditManager
from reddit.utils import select_image
import tkinter as tk
from tkinter import filedialog
import base64
import tempfile

def create_posts(reddit_manager):
    while True:
        try:
            num_posts = int(input("How many posts would you like to create? "))
            if num_posts > 0:
                break
            else:
                print("Please enter a positive number.")
        except ValueError:
            print("Please enter a valid number.")
    
    valid_subreddit = False
    subreddit_name = ""
    
    while not valid_subreddit:
        subreddit_input = input("Enter the subreddit name to post to (without 'r/'): ")
        valid_subreddit, subreddit_name = reddit_manager.validate_subreddit(subreddit_input)
        
        if not valid_subreddit:
            retry = input("Subreddit doesn't exist or is not accessible. Try another? (y/n): ").lower()
            if retry != 'y':
                print("Returning to main menu.")
                return
    
    created_posts = []
    
    for post_num in range(1, num_posts + 1):
        print(f"\n=== Creating Post #{post_num} ===")
        
        title = input(f"Enter title for post #{post_num}: ")
        print(f"Enter content for post #{post_num} (type 'END' on a new line when finished):")
        
        content_lines = []
        while True:
            line = input()
            if line == 'END':
                break
            content_lines.append(line)
        
        content = "\n".join(content_lines)
        
        image_path = None
        while True:
            include_image = input("Do you want to upload an image with this post? (y/n): ").lower()
            if include_image == 'y':
                print("Please select an image file from the dialog box...")
                image_path = select_image()
                if image_path:
                    print(f"Selected image: {image_path}")
                    if not os.path.exists(image_path):
                        print("Warning: Selected image file doesn't exist or can't be accessed.")
                        retry_image = input("Try selecting another image? (y/n): ").lower()
                        if retry_image == 'y':
                            continue
                    break
                else:
                    print("No image selected.")
                    retry = input("Try again? (y/n): ").lower()
                    if retry != 'y':
                        break
            elif include_image == 'n':
                break
            else:
                print("Please enter 'y' or 'n'")
        
        new_post = reddit_manager.create_post(
            subreddit_name=subreddit_name,
            title=title,
            content=content,
            image_path=image_path
        )
        
        if new_post:
            created_posts.append(new_post)
            print(f"Post #{post_num} created successfully: {new_post.url}")
        else:
            print(f"Failed to create post #{post_num}")
            retry_post = input("Would you like to retry this post? (y/n): ").lower()
            if retry_post == 'y':
                post_num -= 1
    
    print("\n=== Post Creation Summary ===")
    if created_posts:
        print(f"Successfully created {len(created_posts)} posts:")
        for i, post in enumerate(created_posts, 1):
            print(f"{i}. '{post.title}' - {post.url}")
    else:
        print("No posts were created successfully.")
    
    with open("reddit_operations_log.txt", "a") as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"\n{timestamp} - Created {len(created_posts)} posts")
        for post in created_posts:
            f.write(f"\n{timestamp} - Created post: {post.url}")

def read_all_posts(reddit_manager):
    valid_subreddit = False
    subreddit_name = ""
    
    while not valid_subreddit:
        subreddit_input = input("Enter the subreddit name to read posts from (without 'r/'): ")
        valid_subreddit, subreddit_name = reddit_manager.validate_subreddit(subreddit_input)
        
        if not valid_subreddit:
            retry = input("Subreddit doesn't exist, is private, or is empty. Try another? (y/n): ").lower()
            if retry != 'y':
                print("Returning to main menu.")
                return
    
    limit = 20
    try:
        user_limit = input("How many posts would you like to retrieve? (default: 20): ")
        if user_limit:
            limit = int(user_limit)
    except ValueError:
        print("Invalid input. Using default limit of 20 posts.")
    
    posts = reddit_manager.get_subreddit_posts(subreddit_name, limit=limit)
    
    if posts:
        print(f"\n=== Latest {len(posts)} Posts from r/{subreddit_name} ===")
        for i, post in enumerate(posts, 1):
            print(f"{i}. '{post['title']}' by {post['author']}")
            print(f"   Score: {post['score']} | Comments: {post['num_comments']} | Posted: {post['created_utc']}")
            print(f"   URL: {post['permalink']}")
            print()
            
        while True:
            view_post = input("Enter the number of a post to view in detail (or 0 to return to main menu): ")
            try:
                post_num = int(view_post)
                if post_num == 0:
                    break
                elif 1 <= post_num <= len(posts):
                    post_detail = reddit_manager.read_post(post_id=posts[post_num-1]["id"])
                    if post_detail:
                        print("\n=== Post Details ===")
                        print(f"Title: {post_detail['title']}")
                        print(f"Author: {post_detail['author']}")
                        print(f"Posted: {post_detail['created_utc']}")
                        print(f"Score: {post_detail['score']} ({post_detail['upvote_ratio'] * 100:.0f}% upvoted)")
                        print(f"Comments: {post_detail['num_comments']}")
                        print(f"URL: {post_detail['permalink']}")
                        print("\nContent:")
                        print(post_detail['content'] if post_detail['content'] else "[No text content]")
                        
                        if post_detail['comments']:
                            print("\n=== Top Comments ===")
                            for j, comment in enumerate(post_detail['comments'], 1):
                                print(f"{j}. {comment['author']} ({comment['score']} points): {comment['body'][:100]}..." if len(comment['body']) > 100 else comment['body'])
                    else:
                        print("Failed to retrieve detailed post information.")
                else:
                    print("Invalid post number.")
            except ValueError:
                print("Please enter a valid number.")
    else:
        print(f"No posts found in r/{subreddit_name} or failed to retrieve posts.")

def update_user_post(reddit_manager):
    print("Retrieving your posts...")
    user_posts = reddit_manager.get_user_posts()
    
    if not user_posts:
        print("No posts found or failed to retrieve your posts.")
        return
    
    print("\n=== Your Posts ===")
    for i, post in enumerate(user_posts, 1):
        print(f"{i}. '{post['title']}' in r/{post['subreddit']}")
        print(f"   Score: {post['score']} | Comments: {post['num_comments']} | Posted: {post['created_utc']}")
        print()
    
    while True:
        try:
            post_num = int(input("Enter the number of the post you want to update (or 0 to return to main menu): "))
            if post_num == 0:
                return
            elif 1 <= post_num <= len(user_posts):
                selected_post = user_posts[post_num-1]
                break
            else:
                print("Invalid post number.")
        except ValueError:
            print("Please enter a valid number.")
    
    post_detail = reddit_manager.read_post(post_id=selected_post["id"])
    if not post_detail:
        print("Failed to retrieve post details.")
        return
    
    print("\n=== Current Post Content ===")
    print(f"Title: {post_detail['title']}")
    print("\nContent:")
    print(post_detail['content'] if post_detail['content'] else "[No text content]")
    
    print("\nEnter new content for the post (type 'END' on a new line when finished):")
    content_lines = []
    while True:
        line = input()
        if line == 'END':
            break
        content_lines.append(line)
    
    new_content = "\n".join(content_lines)
    
    mark_nsfw = None
    nsfw_option = input("Mark as NSFW? (y/n/leave unchanged): ").lower()
    if nsfw_option == 'y':
        mark_nsfw = True
    elif nsfw_option == 'n':
        mark_nsfw = False
    
    mark_spoiler = None
    spoiler_option = input("Mark as spoiler? (y/n/leave unchanged): ").lower()
    if spoiler_option == 'y':
        mark_spoiler = True
    elif spoiler_option == 'n':
        mark_spoiler = False
    
    success = reddit_manager.update_post(
        post_id=selected_post["id"],
        new_content=new_content,
        mark_nsfw=mark_nsfw,
        mark_spoiler=mark_spoiler
    )
    
    if success:
        print(f"Successfully updated post: '{post_detail['title']}'")
        with open("reddit_operations_log.txt", "a") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"\n{timestamp} - Updated post: {post_detail['permalink']}")
    else:
        print("Failed to update post.")

def delete_user_post(reddit_manager):
    print("Retrieving your posts...")
    user_posts = reddit_manager.get_user_posts()
    
    if not user_posts:
        print("No posts found or failed to retrieve your posts.")
        return
    
    print("\n=== Your Posts ===")
    for i, post in enumerate(user_posts, 1):
        print(f"{i}. '{post['title']}' in r/{post['subreddit']}")
        print(f"   Score: {post['score']} | Comments: {post['num_comments']} | Posted: {post['created_utc']}")
        print()
    
    while True:
        try:
            post_num = int(input("Enter the number of the post you want to delete (or 0 to return to main menu): "))
            if post_num == 0:
                return
            elif 1 <= post_num <= len(user_posts):
                selected_post = user_posts[post_num-1]
                break
            else:
                print("Invalid post number.")
        except ValueError:
            print("Please enter a valid number.")
    
    confirm = input(f"Are you sure you want to delete the post '{selected_post['title']}'? (y/n): ").lower()
    if confirm != 'y':
        print("Deletion cancelled.")
        return
    
    success = reddit_manager.delete_post(post_id=selected_post["id"])
    
    if success:
        print(f"Successfully deleted post: '{selected_post['title']}'")
        with open("reddit_operations_log.txt", "a") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"\n{timestamp} - Deleted post: '{selected_post['title']}' from r/{selected_post['subreddit']}")
    else:
        print("Failed to delete post.")

def display_menu():
    print("\n==== Reddit Manager ====")
    print("1. Create Post(s)")
    print("2. Read All Posts from a Subreddit")
    print("3. Update Post")
    print("4. Delete Post")
    print("0. Exit Program")
    print("======================")

def main():
    reddit_manager = RedditManager()
    
    while True:
        display_menu()
        
        try:
            choice = input("Enter your choice (0-4): ")
            
            if choice == '1':
                create_posts(reddit_manager)
            elif choice == '2':
                read_all_posts(reddit_manager)
            elif choice == '3':
                update_user_post(reddit_manager)
            elif choice == '4':
                delete_user_post(reddit_manager)
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