"""Update the config.json in dist/NH with the correct API key."""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.secure_storage import encrypt_api_key

# New API key
NEW_API_KEY = "sk-0b78e1c816f94bc1865f94e367eb7064"

# Encrypt it using the same mechanism
encrypted_key = encrypt_api_key(NEW_API_KEY)
print(f"Encrypted key: {encrypted_key}")

# Update dist/NH/config.json
dist_config_path = os.path.join('dist', 'NH', 'config.json')
if os.path.exists(dist_config_path):
    with open(dist_config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    config['api_key'] = encrypted_key
    config['ai_key'] = encrypted_key
    config['ai_provider'] = 'DeepSeek'
    config['ai_base_url'] = 'https://api.deepseek.com'
    config['ai_model'] = 'deepseek-v4-flash'
    config['query'] = 'Artificial Intelligence'
    config['page_size'] = 10
    
    with open(dist_config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f"Updated {dist_config_path}")
else:
    print(f"File not found: {dist_config_path}")