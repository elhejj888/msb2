from PIL import Image
import tempfile
import os

# Conditional import
try:
    import tkinter as tk
    from tkinter import filedialog
    HAS_GUI = True
except ImportError:
    HAS_GUI = False

def select_images(multiple=False):
    if not HAS_GUI:
        raise RuntimeError("GUI not available in this environment. Use web-based file upload instead.")
    
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

# Keep convert_to_jpeg as is

def convert_to_jpeg(image_path):
    try:
        file_ext = os.path.splitext(image_path)[1].lower()
        if file_ext in ['.jpg', '.jpeg']:
            return image_path
            
        with Image.open(image_path) as img:
            # Convert RGBA to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create a white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            base_name = os.path.splitext(os.path.basename(image_path))[0]
            temp_jpeg = os.path.join(tempfile.gettempdir(), f"{base_name}_temp.jpg")
            img.save(temp_jpeg, 'JPEG', quality=95, optimize=True)
            return temp_jpeg
    except Exception as e:
        print(f"Error converting image: {e}")
        return None