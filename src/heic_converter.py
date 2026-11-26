import sys
import os
import argparse
from pathlib import Path
from PIL import Image
from pillow_heif import register_heif_opener

# Register HEIC opener with Pillow
register_heif_opener()

def convert_heic_to_jpeg(input_path, output_path=None, quality=90):
    """
    Converts a single HEIC file to JPEG.
    """
    try:
        input_path = Path(input_path)
        if not input_path.exists():
            print(f"Error: File not found: {input_path}")
            return False

        if output_path is None:
            output_path = input_path.with_suffix('.jpg')

        output_path = Path(output_path)

        # Open and convert
        image = Image.open(input_path)
        # Convert to RGB if necessary (e.g. if it has alpha channel, though JPEG doesn't support it)
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        image.save(output_path, "JPEG", quality=quality)
        print(f"Converted: {input_path} -> {output_path}")
        return True
    except Exception as e:
        print(f"Error converting {input_path}: {e}")
        return False

def process_directory(directory, quality=90):
    """
    Recursively finds and converts heic files in a directory.
    """
    directory = Path(directory)
    if not directory.exists():
        print(f"Error: Directory not found: {directory}")
        return

    heic_files = list(directory.glob("**/*.heic")) + list(directory.glob("**/*.HEIC"))

    if not heic_files:
        print(f"No HEIC files found in {directory}")
        return

    print(f"Found {len(heic_files)} HEIC files. Starting conversion...")

    success_count = 0
    for file_path in heic_files:
        if convert_heic_to_jpeg(file_path, quality=quality):
            success_count += 1

    print(f"\nFinished! Converted {success_count}/{len(heic_files)} files.")

def main():
    parser = argparse.ArgumentParser(description="Convert HEIC images to JPEG.")
    parser.add_argument("path", help="Path to a .heic file or a directory containing .heic files")
    parser.add_argument("--quality", type=int, default=90, help="JPEG quality (default: 90)")

    args = parser.parse_args()
    
    path = Path(args.path)

    if path.is_file():
        if path.suffix.lower() == '.heic':
            convert_heic_to_jpeg(path, quality=args.quality)
        else:
            print("Error: The provided file is not a .heic file.")
    elif path.is_dir():
        process_directory(path, quality=args.quality)
    else:
        print(f"Error: Invalid path: {path}")

if __name__ == "__main__":
    main()
