from dataclasses import dataclass

from haikubot.haiku import handle_haiku_command
from haikubot.slack import post_slack_message, slack_mention, JSON, SlackContext


@dataclass(frozen=True)
class SlackEvent:
    event_type: str
    authorized_user_id: str  # This will be the user ID of the bot.
    context: SlackContext
    payload: JSON

    @classmethod
    def from_json(cls, json: JSON) -> 'SlackEvent':
        """Create a SlackEvent from a JSON object."""
        context = SlackContext.from_slack_event(json)
        try:
            event = json['event']
            authed_user_id = json['authorizations'][0]['user_id']
            return cls(event_type=event['type'].lower(), authorized_user_id=authed_user_id,
                       context=context, payload=event)
        except (IndexError, KeyError, TypeError) as e:
            raise ValueError(f'Received malformed Slack event: {e}')


def handle_slack_event(payload: JSON) -> None:
    try:
        event = SlackEvent.from_json(payload)
    except ValueError as e:
        print(f'Failed to parse Slack event: {e}')
        return

    if event.event_type == 'app_mention':
        handle_app_mention(event)
    else:
        print(f'Received Slack event with unsupported type: {event.event_type}')


def handle_app_mention(event: SlackEvent) -> None:
    args = event.payload.get('text', '').strip().split()
    if args and args[0] == slack_mention(event.authorized_user_id):
        # Only respond if the message starts with mentioning the bot (otherwise ignore).
        response = handle_haiku_command(command=args[0], text=' '.join(args[1:]), context=event.context)
        post_slack_message(response.text, context=event.context, thread_ts=event.payload.get('thread_ts'))
