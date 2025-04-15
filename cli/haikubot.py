#!/usr/bin/env python3

from enum import Enum
import argparse
import os
import os.path
import re
import subprocess
import sys
import time


HAIKUBOT_GIT_HOME = os.getenv('HAIKUBOT_GIT_HOME', '/Users/jeopardye/dev/git/haikubot')
HAIKUBOT_LOG_FILE = os.getenv('HAIKUBOT_LOG_FILE', '/var/log/haikubot/server.log')
HAIKUBOT_PID_FILE = os.getenv('HAIKUBOT_PID_FILE', '/opt/homebrew/var/run/haikubot.pid')

HAIKUBOT_VIRTUALENV_HOME = os.getenv('HAIKUBOT_VIRTUALENV_HOME', '/Users/jeopardye/.virtualenvs/haikubot')
HAIKUBOT_VIRTUALENV_ACTIVATE = os.path.join(HAIKUBOT_VIRTUALENV_HOME, 'bin', 'activate')


DEPLOY_COMMAND_USAGE = 'deploy'
FETCH_COMMAND_USAGE = 'fetch'
LOGS_COMMAND_USAGE = 'logs'
SERVER_COMMAND_USAGE = 'server start|stop|restart|pid'
VERSION_COMMAND_USAGE = 'version'

COMMAND_HELP = f'''
Command to run: {DEPLOY_COMMAND_USAGE}, {FETCH_COMMAND_USAGE}, {LOGS_COMMAND_USAGE}, {SERVER_COMMAND_USAGE}, 
or {VERSION_COMMAND_USAGE}
'''

PROJECT_VERSION_PATTERN = re.compile(r'version = "(?P<version>[\d.]+)"')


class Command(Enum):
    DEPLOY_SERVER = 'deploy server'
    FETCH = 'fetch'
    LOGS = 'logs'
    SERVER_PID = 'API server PID'
    SERVER_RESTART = 'restart API server'
    SERVER_START = 'start API server'
    SERVER_STOP = 'stop API server'
    VERSION = 'version'


SERVER_COMMAND_TYPES = {
    'pid': Command.SERVER_PID,
    'restart': Command.SERVER_RESTART,
    'start': Command.SERVER_START,
    'stop': Command.SERVER_STOP,
}


class UsageError(ValueError):
    pass


def bold(text: str) -> str:
    return colorize(text, '1')


def cyan(text: str) -> str:
    return colorize(text, '1;36')


def green(text: str) -> str:
    return colorize(text, '1;32')


def red(text: str) -> str:
    return colorize(text, '1;31')


def colorize(text: str, color: str) -> str:
    return f'\033[{color}m{text}\033[0m'


class HaikubotMain:

    def __init__(self) -> None:
        parsed_args = self.parse_args(sys.argv[1:])
        self.command = self.parse_command(parsed_args.command)
        self.skip_version_check = parsed_args.skip_version_check

    @staticmethod
    def parse_args(args: list[str]) -> argparse.Namespace:
        parser = argparse.ArgumentParser(description='CLI for administering the Haikubot API server.')
        parser.add_argument('command', nargs='+', help=COMMAND_HELP)
        parser.add_argument('--skip-version-check', action='store_true',
                            help='Skip checking for a new version before deploying')
        return parser.parse_args(args)

    @staticmethod
    def parse_command(commands: list[str]) -> Command:
        command = commands[0].lower().strip()
        try:
            if command == 'deploy':
                if len(commands) > 1:
                    raise UsageError(DEPLOY_COMMAND_USAGE)
                return Command.DEPLOY_SERVER
            elif command == 'fetch':
                if len(commands) > 1:
                    raise UsageError(FETCH_COMMAND_USAGE)
                return Command.FETCH
            elif command == 'logs':
                if len(commands) > 1:
                    raise UsageError(LOGS_COMMAND_USAGE)
                return Command.LOGS
            elif command == 'server':
                if len(commands) == 2:
                    subcommand = commands[1]
                    if subcommand not in SERVER_COMMAND_TYPES.keys():
                        raise UsageError(SERVER_COMMAND_USAGE)
                else:
                    raise UsageError(SERVER_COMMAND_USAGE)
                return SERVER_COMMAND_TYPES[subcommand]
            elif command == 'version':
                if len(commands) > 1:
                    raise UsageError(VERSION_COMMAND_USAGE)
                return Command.VERSION
            else:
                raise UsageError('deploy|logs|server|version (subcommands)')
        except UsageError as e:
            print(red(f'Usage: {sys.argv[0]} {e.args[0]}'))
            sys.exit(1)

    @staticmethod
    def get_version_number() -> str:
        with open(os.path.join(HAIKUBOT_GIT_HOME, 'pyproject.toml')) as f:
            lines = f.readlines()
        for line in lines:
            if match := PROJECT_VERSION_PATTERN.match(line):
                return match.group('version')
        return ''

    @classmethod
    def fetch_changes(cls) -> tuple[str, str]:
        starting_version = cls.get_version_number()
        subprocess.run(['git', 'pull', 'origin', 'master'], check=True, cwd=HAIKUBOT_GIT_HOME)
        new_version = cls.get_version_number()
        return starting_version, new_version

    @classmethod
    def fetch_and_print(cls) -> None:
        print(cyan('Fetching the latest version of haikubot from GitHub.'))
        starting_version, new_version = cls.fetch_changes()
        print(green(f'\nFetched successfully ({starting_version} --> {new_version}).'))

    def deploy_server(self) -> None:
        print(cyan('Preparing to fetch and deploy the latest version of the haikubot server.'))

        print(bold('\nFetching from GitHub...'))
        starting_version, new_version = self.fetch_changes()
        if new_version == starting_version and not self.skip_version_check:
            print(cyan(f'\nNo new changes to deploy (at version {new_version}).'))
            return
        print(cyan(f'\nDeploying new changes ({starting_version} --> {new_version}).'))

        process = subprocess.Popen(f'. {HAIKUBOT_VIRTUALENV_ACTIVATE} && pip install .',
                                   cwd=HAIKUBOT_GIT_HOME, shell=True)
        process.wait()
        if process.returncode != 0:
            print(red(f'\nFailed to pip install latest changes ({new_version})!'))
            return

        self.restart_server()
        print(green(f'\nSuccessfully deployed version {new_version} of the haikubot server.'))

    @staticmethod
    def print_logs() -> None:
        print(bold(f'Server logs (from {HAIKUBOT_LOG_FILE}):\n'))
        try:
            subprocess.run(['tail', '-f', HAIKUBOT_LOG_FILE])
        except KeyboardInterrupt:
            pass

    @classmethod
    def print_version(cls) -> None:
        print(bold(f'Current version of haikubot: {cls.get_version_number()}'))

    @staticmethod
    def get_server_pid() -> str:
        if not os.path.exists(HAIKUBOT_PID_FILE):
            return ''
        with open(HAIKUBOT_PID_FILE) as f:
            return f.read().strip()

    @classmethod
    def print_server_pid(cls) -> None:
        pid = cls.get_server_pid()
        if pid:
            print(bold(f'haikubot server PID: {pid}'))
        else:
            print(red('The haikubot server is not currently running.'))

    @classmethod
    def start_server(cls) -> None:
        print(cyan('Starting the haikubot server.'))
        pid = cls.get_server_pid()
        if pid:
            print(cyan(f'The haikubot server is already running (PID {pid}).'))
        else:
            subprocess.Popen(
                f'(. {HAIKUBOT_VIRTUALENV_ACTIVATE} &&'
                f' nohup gunicorn -c haikubot/config/gunicorn.conf.py "haikubot:app") >> {HAIKUBOT_LOG_FILE} 2>&1',
                cwd=HAIKUBOT_GIT_HOME, shell=True
            )
            time.sleep(1)
            pid = cls.get_server_pid()
            if pid:
                print(green(f'Started the haikubot server (PID {pid}).'))
            else:
                print(red('Failed to start the haikubot server!'))
                raise RuntimeError()

    @classmethod
    def stop_server(cls) -> None:
        print(cyan('Stopping the haikubot server.'))
        pid = cls.get_server_pid()
        if pid:
            print(bold(f'Stopping the server (PID {pid})...'))
            subprocess.run(['kill', '-9', pid], check=True)
            print(green(f'Successfully stopped the haikubot server.'))
            if os.path.exists(HAIKUBOT_PID_FILE):
                os.remove(HAIKUBOT_PID_FILE)
        else:
            print(cyan('The haikubot server is not currently running.'))

    @classmethod
    def restart_server(cls) -> None:
        cls.stop_server()
        print(bold('Waiting for workers to exit...'))
        time.sleep(10)
        cls.start_server()

    def run(self) -> None:
        if self.command == Command.DEPLOY_SERVER:
            self.deploy_server()
        elif self.command == Command.FETCH:
            self.fetch_and_print()
        elif self.command == Command.LOGS:
            self.print_logs()
        elif self.command == Command.SERVER_PID:
            self.print_server_pid()
        elif self.command == Command.SERVER_RESTART:
            self.restart_server()
        elif self.command == Command.SERVER_START:
            self.start_server()
        elif self.command == Command.SERVER_STOP:
            self.stop_server()
        elif self.command == Command.VERSION:
            self.print_version()
        else:
            raise ValueError(f'Unknown command: {self.command}')


if __name__ == '__main__':
    HaikubotMain().run()
