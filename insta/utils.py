import tkinter as tk
from tkinter import filedialog
from PIL import Image
import tempfile
import os

def select_images(multiple=False):
    root = tk.Tk()
    root.withdraw()
    
    filetypes = [
        ("Image files", "*.jpg *.jpeg *.png"),
        ("All files", "*.*")
    ]
    
    if multiple:
        file_paths = filedialog.askopenfilenames(title="Select Images", filetypes=filetypes)
        root.destroy()
        return list(file_paths) if file_paths else None
    else:
        file_path = filedialog.askopenfilename(title="Select Image", filetypes=filetypes)
        root.destroy()
        return file_path if file_path else None

def convert_to_jpeg(image_path):
    try:
        file_ext = os.path.splitext(image_path)[1].lower()
        if file_ext in ['.jpg', '.jpeg']:
            return image_path
            
        with Image.open(image_path) as img:
            base_name = os.path.splitext(os.path.basename(image_path))[0]
            temp_jpeg = os.path.join(tempfile.gettempdir(), f"{base_name}_temp.jpg")
            img.save(temp_jpeg, 'JPEG', quality=95, optimize=True)
            return temp_jpeg
    except Exception as e:
        print(f"Error converting image: {e}")
        return None