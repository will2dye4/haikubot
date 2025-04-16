from importlib.metadata import version as package_version
from typing import Optional
import re
import textwrap

from haikubot.db import (
    add_haiku_line,
    get_haiku_blame,
    get_haiku_stats,
    generate_random_haiku,
    LinePosition,
    remove_haiku_line,
)
from haikubot.slack import (
    get_user_id,
    SlackContext,
    slack_escape,
    slack_mention,
    SlackResponse,
)


SYLLABLE_PATTERN = re.compile(r'^(?P<count>5|7|five|seven)s?(\[(?P<position>\^|\$|1st|first|last)])?$', re.IGNORECASE)

SYLLABLE_COUNTS = {
    '5': 5,
    'five': 5,
    '7': 7,
    'seven': 7,
}

LINE_POSITIONS = {
    '^': LinePosition.FIRST,
    '1st': LinePosition.FIRST,
    'first': LinePosition.FIRST,
    '$': LinePosition.LAST,
    'last': LinePosition.LAST,
}


VERSION = package_version('haikubot')


def handle_haiku_command(command: str, text: str, context: SlackContext) -> SlackResponse:
    if not text:
        return generate_haiku(context=context)

    args = text.strip().split()
    subcommand = args.pop(0).lower()
    if subcommand in {'add', 'remove'}:
        return handle_add_remove_command(command, subcommand, args, context)
    elif subcommand in {'blame', 'praise'}:
        if args:
            return SlackResponse(f'Usage: {command} {subcommand}', ephemeral=True)
        return get_blame(context=context)
    elif subcommand == 'about':
        return handle_about_command(command, args, context)
    elif subcommand == 'by':
        return handle_by_command(command, args, context)
    elif subcommand == 'stats':
        if args:
            return SlackResponse(f'Usage: {command} stats', ephemeral=True)
        return get_stats(context=context)
    elif subcommand == 'version':
        if args:
            return SlackResponse(f'Usage: {command} version', ephemeral=True)
        return SlackResponse(f'🤖 haikubot version {VERSION}', ephemeral=True)
    else:
        return help_message(command)


def help_message(command: str) -> SlackResponse:
    return SlackResponse(textwrap.dedent(f'''
        Usage:
        *{command}* => generate a random haiku from remembered lines
        *{command} about <topic>* => generate a random haiku about a specific topic or keyword
        *{command} by <user>* => generate a random haiku by a specific user
        *{command} add 5|7 <line>* => remember a line of 5 or 7 syllables
        *{command} remove 5|7 <line>* => remove a line of 5 or 7 syllables
        *{command} blame* => show the users who wrote the last haiku in this channel
    ''').strip(), ephemeral=True)


def handle_add_remove_command(command: str, subcommand: str, args: list[str], context: SlackContext) -> SlackResponse:
    if len(args) < 2 or not (match := SYLLABLE_PATTERN.match(args[0])):
        if subcommand == 'add':
            return SlackResponse(textwrap.dedent(f'''
                Usage:
                *{command} add 5|7 <line>* => remember a line of 5 or 7 syllables
                *{command} add 5[first] <line>* => remember 5 syllables to appear as the first line in a haiku
                *{command} add 5[last] <line>* => remember 5 syllables to appear as the last line in a haiku
            ''').strip(), ephemeral=True)
        return SlackResponse(f'Usage: {command} remove 5|7 <line>', ephemeral=True)
    syllables = SYLLABLE_COUNTS[match.group('count').lower()]
    line = slack_escape(args[1:])
    if subcommand == 'add':
        position = LINE_POSITIONS[pos.lower()] if (pos := match.group('position')) else None
        if syllables == 7 and position:
            return SlackResponse(f'Position ({pos}) may only be included for 5-syllable lines!', ephemeral=True)
        return add_line(line, syllables=syllables, context=context, position=position)
    else:
        return remove_line(line, syllables=syllables, context=context)


def handle_about_command(command: str, args: list[str], context: SlackContext) -> SlackResponse:
    if not args:
        return SlackResponse(f'Usage: {command} about <topic>', ephemeral=True)
    search_term = slack_escape(args)
    if search_term in {'.', '.*', '.+'}:
        return generate_haiku(context=context)
    return generate_haiku(context=context, search_term=search_term)


def handle_by_command(command: str, args: list[str], context: SlackContext) -> SlackResponse:
    if len(args) != 1:
        return SlackResponse(f'Usage: {command} by <user>', ephemeral=True)
    if args[0].lower() == 'me':
        user_id = context.user_id
    elif not (user_id := get_user_id(args[0])):
        return SlackResponse(
            f'You need to tag a user by name! Example: {command} by {slack_mention(context.user_id)}',
            ephemeral=True
        )
    return generate_haiku(context=context, user_id=user_id)


def generate_haiku(context: SlackContext, user_id: Optional[str] = None,
                   search_term: Optional[str] = None) -> SlackResponse:
    if poem := generate_random_haiku(context=context, user_id=user_id, search_term=search_term):
        return SlackResponse(poem.text)
    error = '⚠️ Failed to generate a haiku'
    if user_id:
        error += f' by {slack_mention(user_id)}'
    if search_term:
        error += f' about "{search_term}"'
    return SlackResponse(error + '!')  # NOT an ephemeral message since this can also happen when adding lines.


def add_line(line: str, syllables: int, context: SlackContext,
             position: Optional[LinePosition] = None) -> SlackResponse:
    if add_haiku_line(line, syllables=syllables, context=context, position=position):
        print(f'User {context.user_id} added line: {line}'
              f' (team: {context.team_id}, channel: {context.channel_id})')
        return generate_haiku(context=context, search_term=f'^{re.escape(line)}$')
    return SlackResponse(f'⚠️ Failed to add line: {line}', ephemeral=True)


def remove_line(line: str, syllables: int, context: SlackContext) -> SlackResponse:
    if remove_haiku_line(line, syllables=syllables, context=context):
        print(f'User {context.user_id} removed line: {line}'
              f' (team: {context.team_id}, channel: {context.channel_id})')
        return SlackResponse(f'✅ Removed: {line}')
    return SlackResponse(f'⚠️ Failed to remove line: {line}', ephemeral=True)


def get_blame(context: SlackContext) -> SlackResponse:
    if blame := get_haiku_blame(context=context):
        response = f'The last haiku was brought to you by: {", ".join(slack_mention(user_id) for user_id in blame)}'
        if len(set(blame)) == 1:
            response += ' 🎰'
        return SlackResponse(response)
    return SlackResponse('⚠️ Failed to find the latest haiku for this channel!', ephemeral=True)


def get_stats(context: SlackContext) -> SlackResponse:
    stats = get_haiku_stats(context=context)
    return SlackResponse(textwrap.dedent(f'''
        *Total lines:* {stats.total_lines:,}
          *5 syllables:* {stats.five_syllable_lines:,}
          *7 syllables:* {stats.seven_syllable_lines:,}
        *Total poems:* {stats.total_poems:,}
        *Total unique contributors:* {stats.unique_users:,}
    ''').strip())
