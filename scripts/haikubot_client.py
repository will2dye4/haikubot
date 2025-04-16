#!/usr/bin/env python3

from threading import Thread
from typing import Optional
import logging
import readline  # Not used directly, but required for previous input completion.
import time

from flask import Flask, request
from werkzeug.serving import make_server
import requests

from haikubot import config
from haikubot.constants import DEFAULT_SERVER_PORT, MOCK_SLACK_API_SERVER_PORT
from haikubot.slack import slack_mention

DEFAULT_CHANNEL_ID = 'Cgeneral'
DEFAULT_TEAM_ID = 'Tsppp'
DEFAULT_USER_ID = 'Uwill2dye4'

APP_USER_ID = 'Uhaikubot'

BASE_URL = f'http://localhost:{config.get("server.port", DEFAULT_SERVER_PORT)}/api'


def health() -> None:
    response = requests.get(f'{BASE_URL}/status/health')
    print('✅ Server is healthy' if response.ok else '⚠️ Server is not healthy')


def version() -> None:
    response = requests.get(f'{BASE_URL}/status/version')
    response.raise_for_status()
    print(f'Version {response.json()["version"]}')


def generate_haiku(author_user_id: Optional[str] = None, search_term: Optional[str] = None,
                   user_id: str = DEFAULT_USER_ID, channel_id: str = DEFAULT_CHANNEL_ID,
                   team_id: str = DEFAULT_TEAM_ID) -> None:
    if author_user_id and search_term:
        raise ValueError('Cannot specify both author_user_id and search_term!')
    command = ''
    if author_user_id:
        command = f'by {slack_mention(author_user_id)}'
    elif search_term:
        command = f'about {search_term}'
    invoke_haiku_command(command, user_id=user_id, channel_id=channel_id, team_id=team_id)


def get_blame(user_id: str = DEFAULT_USER_ID, channel_id: str = DEFAULT_CHANNEL_ID,
              team_id: str = DEFAULT_TEAM_ID) -> None:
    invoke_haiku_command('blame', user_id=user_id, channel_id=channel_id, team_id=team_id)


def add_line(line: str, syllables: int, user_id: str = DEFAULT_USER_ID, channel_id: str = DEFAULT_CHANNEL_ID,
             team_id: str = DEFAULT_TEAM_ID) -> None:
    if syllables not in {5, 7}:
        raise ValueError('Invalid syllable count!')
    invoke_haiku_command(f'add {syllables} {line}', user_id=user_id, channel_id=channel_id, team_id=team_id)


def remove_line(line: str, syllables: int, user_id: str = DEFAULT_USER_ID, channel_id: str = DEFAULT_CHANNEL_ID,
                team_id: str = DEFAULT_TEAM_ID) -> None:
    if syllables not in {5, 7}:
        raise ValueError('Invalid syllable count!')
    invoke_haiku_command(f'remove {syllables} {line}', user_id=user_id, channel_id=channel_id, team_id=team_id)


def invoke_haiku_command(text: str, user_id: str = DEFAULT_USER_ID, channel_id: str = DEFAULT_CHANNEL_ID,
                         team_id: str = DEFAULT_TEAM_ID) -> None:
    response = requests.post(f'{BASE_URL}/command/haiku',
                             data={'command': '/haiku', 'text': text, 'user_id': user_id,
                                   'channel_id': channel_id, 'team_id': team_id})
    response.raise_for_status()
    print(response.json()['text'])


def invoke_app_mention(text: str, user_id: str = DEFAULT_USER_ID, channel_id: str = DEFAULT_CHANNEL_ID,
                       team_id: str = DEFAULT_TEAM_ID) -> None:
    payload = {
        'type': 'event_callback',
        'team_id': team_id,
        'event': {'type': 'app_mention', 'text': text, 'channel': channel_id, 'user': user_id},
        'authorizations': [{'user_id': APP_USER_ID}],
    }
    response = requests.post(f'{BASE_URL}/event/dispatch', json=payload)
    response.raise_for_status()
    # Response does not contain the reply from the bot; it will be sent asynchronously.


app = Flask(__name__)

@app.route('/slack/chat.postMessage', methods=['POST'])
def slack_api_post_message():
    print(request.json['text'])
    return ''


class ServerThread(Thread):

    def __init__(self):
        super().__init__()
        self.server = make_server('127.0.0.1', MOCK_SLACK_API_SERVER_PORT, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()


def haikubot_repl() -> None:
    print('Chat with the haikubot! (Ctrl+C to quit)')
    while True:
        try:
            message = input('> ')
            if message.startswith('/haiku'):
                invoke_haiku_command(message[len('/haiku'):])
            elif message.startswith(slack_mention(APP_USER_ID)):
                invoke_app_mention(message)
                time.sleep(0.2)  # Wait for async response.
            else:
                print(f'< {message}')
        except (EOFError, KeyboardInterrupt):
            break


def main() -> None:
    # Suppress request logging for mock server.
    logging.getLogger('werkzeug').setLevel(logging.ERROR)

    server_thread = ServerThread()
    server_thread.start()
    print(f'Started mock Slack API server on port {MOCK_SLACK_API_SERVER_PORT}\n')

    haikubot_repl()

    print('\nShutting down mock Slack API server...')
    server_thread.shutdown()
    server_thread.join()


if __name__ == '__main__':
    main()
