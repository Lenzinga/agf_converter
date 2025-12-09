import os
import glob
from converter import process_agf

def main():
    # Find all .agf files in the current directory
    agf_files = glob.glob("*.agf")
    
    if not agf_files:
        print("No .agf files found in the current directory.")
        return

    for agf_file in agf_files:
        full_path = os.path.abspath(agf_file)
        print(f"Found file: {full_path}")
        try:
            process_agf(full_path)
        except Exception as e:
            print(f"Error processing {agf_file}: {e}")

if __name__ == "__main__":
    main()
