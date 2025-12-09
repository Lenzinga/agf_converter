import os
import zipfile
import glob
from converter import process_agf

def process_zip(zip_path):
    print(f"Processing Zip archive: {zip_path}")
    
    # Create extraction directory
    zip_name = os.path.basename(zip_path).replace('.zip', '')
    extract_dir = os.path.join(os.path.dirname(zip_path), f"extracted_{zip_name}")
    
    if not os.path.exists(extract_dir):
        os.makedirs(extract_dir)
        
    print(f"Extracting to: {extract_dir}")
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(extract_dir)
        
    # Walk through the extracted directory and process .agf files
    count = 0
    for root, dirs, files in os.walk(extract_dir):
        for file in files:
            if file.lower().endswith('.agf'):
                agf_path = os.path.join(root, file)
                try:
                    process_agf(agf_path)
                    count += 1
                except Exception as e:
                    print(f"Error processing {agf_path}: {e}")
                    
    print(f"Finished processing zip. Converted {count} AGF files.")

def main():
    # Find all .zip files in the current directory
    # excluding the one we might be calling this from if it was zipped context, 
    # but here we just look for .zip files.
    zip_files = glob.glob("*.zip")
    
    if not zip_files:
        print("No .zip files found in the current directory.")
        return

    for zip_file in zip_files:
        full_path = os.path.abspath(zip_file)
        process_zip(full_path)

if __name__ == "__main__":
    main()
