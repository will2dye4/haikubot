#!/usr/bin/env python3

from typing import Optional
import readline  # Not used directly, but required for previous input completion.

import requests

from haikubot import config
from haikubot.app import slack_mention

DEFAULT_CHANNEL_ID = 'Cgeneral'
DEFAULT_TEAM_ID = 'Tsppp'
DEFAULT_USER_ID = 'Uwill2dye4'

BASE_URL = f'http://localhost:{config.get("server.port", 5555)}/api'


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


def main() -> None:
    print('Chat with the haikubot! (Ctrl+C to quit)')
    while True:
        try:
            message = input('> ')
            if message.startswith('/haiku'):
                invoke_haiku_command(message[len('/haiku'):])
            else:
                print(f'< {message}')
        except (EOFError, KeyboardInterrupt):
            break


if __name__ == '__main__':
    main()
