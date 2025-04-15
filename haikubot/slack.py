from dataclasses import dataclass
from typing import Optional
import re


SLACK_ESCAPE_PATTERN = re.compile(r'^<.*?>$')
SLACK_USER_ID_PATTERN = re.compile(r'^<@(?P<user_id>U\w+)(\|.*?)?>$', re.IGNORECASE)


@dataclass(frozen=True)
class SlackResponse:
    text: str
    ephemeral: bool = False

    def to_json(self) -> dict[str, str]:
        return {
            'text': self.text,
            'response_type': 'ephemeral' if self.ephemeral else 'in_channel',
        }


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


def get_user_id(slack_user_id: str) -> Optional[str]:
    if match := SLACK_USER_ID_PATTERN.match(slack_user_id):
        return match.group('user_id')
    return None
