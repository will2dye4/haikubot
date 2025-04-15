from importlib.metadata import version as package_version
import textwrap

from flask import Flask, request

from haikubot.db import SlackContext
from haikubot.haiku import (
    generate_haiku,
    get_blame,
    get_stats,
    handle_about_command,
    handle_add_remove_command,
    handle_by_command,
)
from haikubot.slack import SlackResponse


VERSION = package_version('haikubot')


app = Flask(__name__)


@app.route('/api/status/health')
def health():
    return ''


@app.route('/api/status/version')
def version():
    return {'version': VERSION}


@app.route('/api/command/haiku', methods=['POST'])
def haiku():
    if request.form.get('ssl_check'):
        return ''  # Send empty response to Slack SSL certificate check.

    command = request.form.get('command', '')
    text = request.form.get('text', '').strip()
    context = SlackContext(user_id=request.form.get('user_id', ''), channel_id=request.form.get('channel_id', ''),
                           team_id=request.form.get('team_id', ''))

    if not text:
        return generate_haiku(context=context).to_json()

    args = text.split()
    subcommand = args.pop(0).lower()
    if subcommand in {'add', 'remove'}:
        response = handle_add_remove_command(command, subcommand, args, context)
    elif subcommand in {'blame', 'praise'}:
        if args:
            response = SlackResponse(f'Usage: {command} {subcommand}', ephemeral=True)
        else:
            response = get_blame(context=context)
    elif subcommand == 'about':
        response = handle_about_command(command, args, context)
    elif subcommand == 'by':
        response = handle_by_command(command, args, context)
    elif subcommand == 'stats':
        if args:
            response = SlackResponse(f'Usage: {command} stats', ephemeral=True)
        else:
            response = get_stats(context=context)
    elif subcommand == 'version':
        if args:
            response = SlackResponse(f'Usage: {command} version', ephemeral=True)
        else:
            response = SlackResponse(f'🤖 haikubot version {VERSION}', ephemeral=True)
    else:
        response = help_message(command)

    return response.to_json()


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
