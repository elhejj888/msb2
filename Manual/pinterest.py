import os
from datetime import datetime
import tkinter as tk
from tkinter import filedialog
from dotenv import load_dotenv
from pinterest.controller import PinterestManager


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

def create_pin(pinterest_manager):
    """Function to handle pin creation process"""
    boards = pinterest_manager.list_boards()
    if not boards:
        print("No boards found. Please create a board first.")
        return
    
    print("\n=== Available Boards ===")
    for i, board in enumerate(boards, 1):
        print(f"{i}. {board['name']} (ID: {board['id']}, Privacy: {board['privacy']})")
    
    while True:
        try:
            board_num = int(input("Select board number: "))
            if 1 <= board_num <= len(boards):
                board_id = boards[board_num-1]['id']
                break
            else:
                print("Please enter a valid board number.")
        except ValueError:
            print("Please enter a valid number.")
    
    title = input("Enter title for the pin: ")
    description = input("Enter description for the pin: ")
    link = input("Enter link for the pin (optional, press Enter to skip): ") or None
    
    print("Please select an image file from the dialog box...")
    image_path = select_image()
    if not image_path:
        print("No image selected. Pin creation cancelled.")
        return
    
    pin_data = pinterest_manager.create_pin(
        board_id=board_id,
        image_path=image_path,
        title=title,
        description=description,
        link=link
    )
    
    if pin_data:
        print("Pin created successfully!")
        print(f"Pin URL: {pin_data.get('url', 'Not available')}")
        with open("pinterest_operations_log.txt", "a") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"\n{timestamp} - Created pin: {pin_data.get('id')}")
    else:
        print("Failed to create pin.")

def list_boards(pinterest_manager):
    """Function to list all boards"""
    boards = pinterest_manager.list_boards()
    
    if boards:
        print("\n=== Your Boards ===")
        for i, board in enumerate(boards, 1):
            print(f"{i}. {board['name']} (ID: {board['id']})")
            print(f"   Privacy: {board['privacy']}")
            print(f"   Description: {board.get('description', 'No description')}")
            print(f"   Pins: {board.get('pin_count', 'Unknown')}")
            print()
    else:
        print("No boards found.")

def create_board(pinterest_manager):
    """Function to create a new board"""
    name = input("Enter board name: ")
    description = input("Enter board description (optional, press Enter to skip): ") or None
    
    privacy_options = {
        '1': 'PUBLIC',
        '2': 'PROTECTED',
        '3': 'SECRET'
    }
    
    print("\nSelect privacy option:")
    print("1. Public (visible to everyone)")
    print("2. Protected (visible to you and your followers)")
    print("3. Secret (visible only to you)")
    
    while True:
        privacy_choice = input("Enter privacy option (1-3): ")
        if privacy_choice in privacy_options:
            privacy = privacy_options[privacy_choice]
            break
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")
    
    board_data = pinterest_manager.create_board(
        name=name,
        description=description,
        privacy=privacy
    )
    
    if board_data:
        print("Board created successfully!")
        print(f"Board ID: {board_data['id']}")
        print(f"URL: {board_data.get('url', 'Not available')}")
        with open("pinterest_operations_log.txt", "a") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"\n{timestamp} - Created board: {board_data['id']}")
    else:
        print("Failed to create board.")

def get_pin_details(pinterest_manager):
    """Function to get pin details"""
    pin_id = input("Enter Pin ID: ")
    pin_data = pinterest_manager.get_pin(pin_id)
    
    if pin_data:
        print("\n=== Pin Details ===")
        print(f"Title: {pin_data.get('title', 'No title')}")
        print(f"Description: {pin_data.get('description', 'No description')}")
        print(f"Link: {pin_data.get('link', 'No link')}")
        print(f"URL: {pin_data.get('url', 'Not available')}")
        print(f"Board ID: {pin_data.get('board_id')}")
        print(f"Created at: {pin_data.get('created_at')}")
        print(f"Media: {pin_data.get('media', {}).get('url', 'No media')}")
    else:
        print("Failed to get pin details.")

def delete_pin(pinterest_manager):
    """Function to delete a pin"""
    pin_id = input("Enter Pin ID to delete: ")
    confirm = input(f"Are you sure you want to delete pin {pin_id}? (y/n): ").lower()
    
    if confirm == 'y':
        success = pinterest_manager.delete_pin(pin_id)
        if success:
            print("Pin deleted successfully!")
            with open("pinterest_operations_log.txt", "a") as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"\n{timestamp} - Deleted pin: {pin_id}")
        else:
            print("Failed to delete pin.")
    else:
        print("Deletion cancelled.")

def display_menu():
    """Display the main menu"""
    print("\n==== Pinterest Manager ====")
    print("1. List Boards")
    print("2. Create Board")
    print("3. Create Pin")
    print("4. Get Pin Details")
    print("5. Delete Pin")
    print("0. Exit Program")
    print("==========================")

def display_menu():
    """Display the main menu"""
    print("\n==== Pinterest Manager ====")
    print("1. List Boards")
    print("2. Create Board")
    print("3. Create Pin")
    print("4. Get All Pins")
    print("5. Get Pin Details")
    print("6. Delete Pin")
    print("0. Exit Program")
    print("==========================")

def get_all_pins(pinterest_manager):
    """Function to get all pins across all boards"""
    print("\nFetching all pins... This may take a while if you have many boards.")
    all_pins = pinterest_manager.get_all_pins()
    
    if all_pins:
        print("\n=== All Pins ===")
        for i, pin in enumerate(all_pins, 1):
            print(f"\n{i}. {pin.get('title', 'No title')} (ID: {pin['id']})")
            print(f"   Board ID: {pin.get('board_id')}")
            print(f"   Created at: {pin.get('created_at')}")
            print(f"   Description: {pin.get('description', 'No description')}")
            print(f"   URL: {pin.get('url', 'No URL')}")
        
        print(f"\nTotal pins found: {len(all_pins)}")
        with open("pinterest_operations_log.txt", "a") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"\n{timestamp} - Retrieved {len(all_pins)} pins")
    else:
        print("No pins found.")

def main():
    load_dotenv()
    pinterest_manager = PinterestManager()
    
    if not pinterest_manager.validate_credentials():
        print("Error: Failed to validate Pinterest credentials. Please check your access tokens.")
        return
    
    while True:
        display_menu()
        try:
            choice = input("Enter your choice (0-6): ")
            
            if choice == '1':
                list_boards(pinterest_manager)
            elif choice == '2':
                create_board(pinterest_manager)
            elif choice == '3':
                create_pin(pinterest_manager)
            elif choice == '4':
                get_all_pins(pinterest_manager)
            elif choice == '5':
                get_pin_details(pinterest_manager)
            elif choice == '6':
                delete_pin(pinterest_manager)
            elif choice == '0':
                print("Exiting program. Goodbye!")
                break
            else:
                print("Invalid choice. Please enter a number between 0 and 6.")
        except Exception as e:
            print(f"An error occurred: {e}")
            print("Returning to main menu.")

if __name__ == "__main__":
    main()