import argparse
import subprocess

def start_app(command): 
    try: 
        subprocess.Popen(command) 
    except FileNotFoundError: 
        print(f"Could not find the application: {command}")
        
def main():
    parser = argparse.ArgumentParser(description="A simple CLI application that starts specific apps based on your plan.")
    parser.add_argument('--startup', action='store_true', help='Run this application at startup.')
    args = parser.parse_args()

    if args.startup:
        print("Running application at startup...")

    categories = {
        "default": [
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe", "pycharm"],
        "gaming": [
            r"C:\Program Files (x86)\Steam\Steam.exe", "epicgames"],  # Placeholders for now
        "programming": [
            "code", "pycharm"]  # Placeholders for now
    }

    default_category = "default" # Set default category 
    # Prompt for category 
    print("What do you plan to do today?") 
    for category in categories: 
        print(f"- {category.capitalize()}") 
        
    chosen_category = input("Choose a category: ").strip().lower() 
    
    if chosen_category not in categories: 
        print(f"No valid category chosen, defaulting to {default_category.capitalize()}.") 
        chosen_category = default_category 
    
    print(f"Starting applications for {chosen_category}...") 
    for app in categories[chosen_category]: 
        start_app([app])

if __name__ == "__main__":
    main()