import json
import multiprocessing
import os.path


with open(os.path.join(os.path.dirname(__file__), 'config.json')) as f:
    CONFIG = json.load(f)


bind = f'0.0.0.0:{CONFIG.get("server", {}).get("port", 5555)}'
workers = multiprocessing.cpu_count() * 2

# SSL configuration
certfile = CONFIG.get('ssl', {}).get('cert_path')
keyfile = CONFIG.get('ssl', {}).get('key_path')
