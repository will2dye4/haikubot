from haikubot import app, config


DEFAULT_PORT = 5555


def main():
    ssl_context = None
    if (cert_path := config.get('ssl.cert_path')) and (key_path := config.get('ssl.key_path')):
        ssl_context = (cert_path, key_path)
    app.run(port=config.get('server.port', DEFAULT_PORT),
            debug=config.get('server.debug', False),
            ssl_context=ssl_context)


if __name__ == '__main__':
    main()
