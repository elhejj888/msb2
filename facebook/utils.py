import tkinter as tk
from tkinter import filedialog

def select_image():
    """Open file dialog to select an image file"""
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