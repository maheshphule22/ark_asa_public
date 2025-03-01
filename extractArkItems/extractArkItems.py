import os
import argparse
import re

# Argument parser
parser = argparse.ArgumentParser(description="Script to extract items form mod files")
parser.add_argument("-directory",       nargs="?", default=".",                 help="Path to the directory (default: current directory)")
parser.add_argument("-FileNamePart",    nargs="?", default="Manifest_UFSFiles", help="File name to look for (default: Manifest_UFSFiles)")
parser.add_argument("-FileExtension",   nargs="?", default=".txt",              help="File extension to search for (default: .txt)")
parser.add_argument("-display",         nargs="?", default="uniq",              help="Choose display option from: all, uniq", choices=["all", "uniq"])
parser.add_argument("-LineSearchStart", nargs="?", default="ShooterGame/Mods",  help="prefix to look for in lines for re match  (default: ShooterGame/Mods)")
parser.add_argument("-LineSearchExt",   nargs="?", default=".uasset",           help="suffix/extention to look for in lines for re match (default: .uasset)")
parser.add_argument("-LineSearch",      nargs="?", default="(.+)",              help="search pattern to look for in lines for re match (default: (.+))")

# Parse arguments
args = parser.parse_args()

def list_files_by_extension(directory, filename, extension):
    matching_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            lfile = file.lower()
            if lfile.endswith(extension.lower()) and filename.lower() in lfile:
                matching_files.append(os.path.join(root, file))
    return matching_files

# pattern = r"/([^/]+)\.uasset"
# pattern = r"ShooterGame/Mods/ShinyAscended/Content/Data/.*_([^/]+)\.uasset"
# pattern = r"ShooterGame/Mods/(.+)\.uasset"
# pattern = rf"{re.escape(args.LineSearchStart)}(.+){re.escape(args.LineSearchExt)}"
pattern = rf"{re.escape(args.LineSearchStart)}{re.escape(args.LineSearch)}{re.escape(args.LineSearchExt)}".replace("\\","")
print(pattern)

def process_line(line):
    """Extract the item name from the given line."""
    match = re.search(pattern, line)
    if match:
        extracted_path = match.group(1)  # Extract everything between
        return extracted_path.replace("/", ",")  # Replace '/' with ','
    return None  # Return None if no match

def process_files(files, display_mode):
    """Process each file, extract relevant parts, and handle uniqueness."""
    processed_lines = set() if display_mode == "uniq" else []  # Set for uniqueness

    for file in files:
        # print(f"\nProcessing file: {file}")
        try:
            with open(file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()  # Remove whitespace
                    extracted = process_line(line)  # Extract relevant part
                    
                    if extracted:  # Ignore lines where nothing is extracted
                        if display_mode == "uniq":
                            processed_lines.add(extracted)  # Store unique items
                        else:
                            processed_lines.append(extracted)  # Store all items

        except Exception as e:
            print(f"Error reading {file}: {e}")

    # Print the extracted results
    print("\nExtracted Items:")
    for item in processed_lines:
        print(item)
        
# Get list of matching files
files = list_files_by_extension(args.directory, args.FileNamePart, args.FileExtension)

if files:
    process_files(files, args.display)
else:
    print("\nNo matching files found.")