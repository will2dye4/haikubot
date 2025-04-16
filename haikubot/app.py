from concurrent.futures import ThreadPoolExecutor

from flask import Flask, request

from haikubot.haiku import handle_haiku_command, VERSION
from haikubot.slack import SlackContext
from haikubot.slack.event import handle_slack_event


event_queue = ThreadPoolExecutor()

def shutdown_event_queue(_ = None) -> None:
    # Note: gunicorn requires this function to accept an argument, but we don't use it.
    print('Shutting down Slack event queue...')
    event_queue.shutdown()


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

    try:
        context = SlackContext.from_slash_command(request.form)
    except ValueError as e:
        print(f'Failed to handle haiku slash command: {e}')
        return '', 400

    command = request.form.get('command', '')
    text = request.form.get('text', '').strip()
    response = handle_haiku_command(command, text, context=context)
    return response.to_json()


@app.route('/api/event/dispatch', methods=['POST'])
def slack_event():
    event_type = request.json.get('type')
    if event_type == 'url_verification':
        return request.json.get('challenge', '')  # Send direct response to Slack challenge requests.

    if event_type == 'event_callback':
        event_queue.submit(handle_slack_event, payload=request.json)
    else:
        print(f'Received unknown Slack event type: {event_type}')

    return ''  # Send empty response immediately (event queue will post messages asynchronously).
