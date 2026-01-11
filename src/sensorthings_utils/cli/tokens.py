"""Token file management functions."""

# standard
import json

# internal
from ..paths import TOKENS_DIR


def _setup_token_file(token_name: str = None):
    """Setup a new token file.
    
    Args:
        token_name: Optional token file name to pre-fill (without .json extension).
    """
    print("\n--- Token Files (Freeform JSON) ---")
    
    if token_name:
        print(f"Setting up token file for: {token_name}")
    else:
        token_name = input("Token file name (without .json extension): ").strip()
        if not token_name:
            return False
    
    print("Enter JSON key-value pairs (press Enter with empty key to finish):")
    token_data = {}
    
    while True:
        key = input("  Key: ").strip()
        if not key:
            break
        value = input(f"  Value for {key}: ").strip()
        token_data[key] = value
    
    if token_data:
        token_file = TOKENS_DIR / f"{token_name}.json"
        with open(token_file, "w") as f:
            json.dump(token_data, f, indent=4)
        print(f"✓ Created/Updated {token_file}")
        return True
    return False


def _manage_tokens(existing_tokens):
    """Manage existing token files."""
    if not existing_tokens:
        print("\nNo existing token files found.")
        return
    
    print("\n--- Manage Token Files ---")
    print("Existing token files:")
    for i, token in enumerate(existing_tokens, 1):
        print(f"  [{i}] {token}.json")
    print(f"  [{len(existing_tokens) + 1}] Back to main menu")
    
    choice = input(f"\nSelect token to overwrite [1-{len(existing_tokens) + 1}]: ").strip()
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(existing_tokens):
            token_name = existing_tokens[idx]
            print(f"\nOverwriting {token_name}.json")
            print("Enter JSON key-value pairs (press Enter with empty key to finish):")
            token_data = {}
            
            while True:
                key = input("  Key: ").strip()
                if not key:
                    break
                value = input(f"  Value for {key}: ").strip()
                token_data[key] = value
            
            if token_data:
                token_file = TOKENS_DIR / f"{token_name}.json"
                with open(token_file, "w") as f:
                    json.dump(token_data, f, indent=4)
                print(f"✓ Updated {token_file}")
        elif idx == len(existing_tokens):
            return  # Back to main menu
        else:
            print("Invalid selection.")
    except ValueError:
        print("Invalid input. Please enter a number.")
