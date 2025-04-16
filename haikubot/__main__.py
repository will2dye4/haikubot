from haikubot import app, config, shutdown_event_queue
from haikubot.constants import DEFAULT_SERVER_PORT


def main():
    ssl_context = None
    if (cert_path := config.get('ssl.cert_path')) and (key_path := config.get('ssl.key_path')):
        ssl_context = (cert_path, key_path)
    try:
        app.run(port=config.get('server.port', DEFAULT_SERVER_PORT),
                debug=config.get('server.debug', False),
                ssl_context=ssl_context)
    except KeyboardInterrupt:
        shutdown_event_queue()


if __name__ == '__main__':
    main()
