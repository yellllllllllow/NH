"""Update API key in config files."""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.secure_storage import encrypt_api_key, decrypt_api_key

# New API key provided by user
NEW_API_KEY = "sk-0b78e1c816f94bc1865f94e367eb7064"

# Encrypt the key
encrypted_key = encrypt_api_key(NEW_API_KEY)
print(f"New encrypted key: {encrypted_key}")

# Update main config.json
config_path = 'config.json'
with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)

config['api_key'] = encrypted_key
config['ai_key'] = encrypted_key

with open(config_path, 'w', encoding='utf-8') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)
print(f"Updated {config_path}")

# Update dist/NH/config.json (for bundled exe)
dist_config_path = os.path.join('dist', 'NH', 'config.json')
if os.path.exists(dist_config_path):
    with open(dist_config_path, 'r', encoding='utf-8') as f:
        dist_config = json.load(f)
    
    dist_config['api_key'] = encrypted_key
    dist_config['ai_key'] = encrypted_key
    
    with open(dist_config_path, 'w', encoding='utf-8') as f:
        json.dump(dist_config, f, indent=2, ensure_ascii=False)
    print(f"Updated {dist_config_path}")

print("\n✓ API Key has been encrypted and saved to config files.")
print("The key will be automatically used by the application.")