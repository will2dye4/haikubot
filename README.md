# haikubot - Slack app for generating haikus from remembered chat messages

This repository contains the source code for the `haikubot` server which
handles invocations of the `/haiku` slash command in Slack.

## Installation

1.  Clone the repository.
    ```shell
    $ git clone git@github.com:will2dye4/haikubot.git
    $ cd haikubot
    ```

1.  Edit the config file as needed for your environment.
    ```shell
    $ $EDITOR haikubot/config/config.json
    ```

## Running the Server

**NOTE:** `haikubot` depends on [Python](https://www.python.org/downloads/) 3.10
or newer; please ensure that you have a semi-recent version of Python installed
before proceeding.

### Running Locally

To run the server locally, run the following from the root of the repository:

```shell
$ pip install .
$ haikubot
```

### Deploying to gunicorn

To run the server using `gunicorn`, run the following:

```shell
$ pip install .
$ pip install gunicorn
$ gunicorn -w `sysctl -n hw.ncpu` -b 0.0.0.0 'haikubot:app'
```

## Scripts

### haikubot_client.py

The script located at `scripts/haikubot_client.py` can be used to test
a locally running haikubot server (see above). Enter `/haiku` commands
at the prompt to see the resulting response from the bot.

```
$ scripts/haikubot_client.py
Chat with the haikubot! (Ctrl+C to quit)
> /haiku
something with [brackets]
seven syllables right here
test other user
> /haiku blame
The last haiku was brought to you by: <@U12345ABC>, <@U67890DEF>, <@U69420CAB>
```

### create_db_indexes.py

The script located at `scripts/create_db_indexes.py` should be run once
to create database indexes to enable performant queries for the most
common use cases.

```
$ scripts/create_db_indexes.py
Creating indexes on haiku.lines table...
  Creating unique index (text, syllables, team_id)...
  Creating index (syllables, team_id)...
  Creating index (user_id)...
  ✅ Done.
Creating indexes on haiku.poem table...
  Creating index (channel_id, team_id)...
  ✅ Done.
```
