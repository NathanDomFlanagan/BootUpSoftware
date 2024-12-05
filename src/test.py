import argparse
import subprocess
import json
import os

def start_app(command): 
    try: 
        subprocess.Popen(command, shell=True) 
    except FileNotFoundError: 
        print(f"Could not find the application: {command}")
        
def load_config(config_path):
    if os.path.exists(config_path):
        print(f"Configuration file not found: {config_path}")
        return {}
    with open(config_path, "r") as file:
        return json.load(file)
        
def main():
    parser = argparse.ArgumentParser(description="A simple CLI application that starts specific apps based on your plan.")
    parser.add_argument('--startup', action='store_true', help='Run this application at startup.')
    args = parser.parse_args()

    if args.startup:
        print("Running application at startup...")

    config_path = 'config.json'
    categories = load_config(config_path)

    if not categories:
        print("No categories found in the configuration file.")
        return
    
    default_category = "default" # Set default category 
    # Prompt for category 
    print("What do you plan to do today?") 
    for category in categories: 
        print(f"- {category.capitalize()}") 
        
    chosen_categories = input("Choose categories (e.g., gaming, programming): ").strip().lower().split(',')    
    chosen_categories = [category.strip() for category in chosen_categories]
    
    # Ensure default category is always included
    if default_category not in chosen_categories:
        chosen_categories.append(default_category)
    
    # Filer out invalid categories
    valid_categories = [category for category in chosen_categories if category in categories]   
    
    if not valid_categories:
        print(f"No valid category chosen, defaulting to {default_category.capitalize()}.") 
        valid_categories = [default_category]
    
    print(f"Starting applications for: {', '.join(valid_categories)}") 
    
    # Start applications for each category
    for chosen_category in valid_categories: 
        for app in categories[chosen_category]:
            start_app(app)
    
    # Last prompt to keep terminal running
    input("Press Enter to exit...")

if __name__ == "__main__":
    main()