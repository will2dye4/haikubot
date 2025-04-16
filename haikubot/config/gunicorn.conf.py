import json
import multiprocessing
import os.path

from haikubot import shutdown_event_queue


with open(os.path.join(os.path.dirname(__file__), 'config.json')) as f:
    CONFIG = json.load(f)


bind = f'0.0.0.0:{CONFIG.get("server", {}).get("port", 5555)}'
workers = multiprocessing.cpu_count() * 2
pidfile = CONFIG.get('server', {}).get('pid_file_path')

# SSL configuration
certfile = CONFIG.get('ssl', {}).get('cert_path')
keyfile = CONFIG.get('ssl', {}).get('key_path')

# Server hooks
on_exit = shutdown_event_queue
