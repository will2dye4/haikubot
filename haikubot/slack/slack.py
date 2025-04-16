from dataclasses import dataclass
from typing import Any, Optional
import functools
import os
import re

import requests

from haikubot import config
from haikubot.constants import MOCK_SLACK_API_SERVER_PORT


JSON = dict[str, Any]


SLACK_API_BASE = (
    f'http://localhost:{MOCK_SLACK_API_SERVER_PORT}/slack'
    if config.get('server.use_mock_slack_api')
    else 'https://slack.com/api'
)
SLACK_POST_MESSAGE_ENDPOINT = f'{SLACK_API_BASE}/chat.postMessage'
SLACK_REQUEST_TIMEOUT = 5


SLACK_ESCAPE_PATTERN = re.compile(r'^<.*?>$')
SLACK_USER_ID_PATTERN = re.compile(r'^<@(?P<user_id>U\w+)(\|.*?)?>$', re.IGNORECASE)


@dataclass(frozen=True)
class SlackContext:
    user_id: str
    channel_id: str
    team_id: str

    @classmethod
    def from_bson(cls, bson: dict[str, Any]) -> 'SlackContext':
        """Create a SlackContext from a BSON (MongoDB) object."""
        return cls(user_id=bson['user_id'], channel_id=bson['channel_id'], team_id=bson['team_id'])

    @classmethod
    def from_slack_event(cls, event_json: JSON) -> 'SlackContext':
        """Create a SlackContext from a Slack event payload."""
        try:
            event = event_json['event']
            return cls(user_id=event['user'], channel_id=event['channel'], team_id=event_json['team_id'])
        except (KeyError, TypeError) as e:
            raise ValueError(f'Received malformed Slack event context: {e}')

    @classmethod
    def from_slash_command(cls, form_data: dict[str, str]) -> 'SlackContext':
        """Create a SlackContext from a Slack slash command payload."""
        try:
            return cls(user_id=form_data['user_id'], channel_id=form_data['channel_id'], team_id=form_data['team_id'])
        except (KeyError, TypeError) as e:
            raise ValueError(f'Received malformed Slack slash command context: {e}')


@dataclass(frozen=True)
class SlackResponse:
    text: str
    ephemeral: bool = False

    def to_json(self) -> JSON:
        """Convert a SlackResponse to JSON."""
        return {
            'text': self.text,
            'response_type': 'ephemeral' if self.ephemeral else 'in_channel',
        }


def get_user_id(slack_user_id: str) -> Optional[str]:
    if match := SLACK_USER_ID_PATTERN.match(slack_user_id):
        return match.group('user_id')
    return None


def slack_mention(user_id: str) -> str:
    return f'<@{user_id}>'


def slack_escape(tokens: list[str]) -> str:
    escaped_tokens = []
    for token in tokens:
        if SLACK_ESCAPE_PATTERN.match(token):
            # Don't re-escape already escaped channel/user mentions and links.
            escaped_tokens.append(token)
        else:
            escaped_tokens.append(
                token.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            )
    return ' '.join(escaped_tokens)


def post_slack_message(text: str, context: SlackContext, thread_ts: Optional[str] = None) -> None:
    if not (token := get_slack_token(context)):
        print(f'Failed to find Slack API token (team: {context.team_id})')
        return

    payload = {'channel': context.channel_id, 'text': text}
    if thread_ts:
        payload['thread_ts'] = thread_ts

    try:
        response = requests.post(SLACK_POST_MESSAGE_ENDPOINT, headers={'Authorization': f'Bearer {token}'},
                                 json=payload, timeout=SLACK_REQUEST_TIMEOUT)
    except requests.exceptions.RequestException as e:
        print(f'Failed to post message to Slack: {e}')
    else:
        if response.ok:
            status = response.json()
            if not status.get('ok'):
                print(f'Failed to post message to Slack: Received error: {status.get("error", "unknown")}')
        else:
            print(f'Failed to post message to Slack: Received HTTP {response.status_code}')


@functools.lru_cache
def get_slack_token(context: SlackContext) -> Optional[str]:
    return os.getenv(f'SLACK_API_TOKEN_{context.team_id}', None)
