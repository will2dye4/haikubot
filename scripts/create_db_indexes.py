#!/usr/bin/env python3

from haikubot.db import db


def create_line_indexes() -> None:
    print('Creating indexes on haiku.lines table...')

    # Unique constraint for all rows in the table.
    print('  Creating unique index (text, syllables, team_id)...')
    db.lines.create_index(['text', 'syllables', 'team_id'], name='unique_index', unique=True)

    # Most common use case: querying by syllable count within a team.
    print('  Creating index (syllables, team_id)...')
    db.lines.create_index(['syllables', 'team_id'], name='syllable_index')

    # For querying lines by a specific user.
    print('  Creating index (user_id)...')
    db.lines.create_index(['user_id'], name='user_index')

    print('  ✅ Done.')


def create_poem_indexes() -> None:
    print('Creating indexes on haiku.poem table...')

    # For querying blame for the latest haiku in a specific channel.
    print('  Creating index (channel_id, team_id)...')
    db.poems.create_index(['channel_id', 'team_id'], name='channel_index')

    print('  ✅ Done.')


def create_indexes() -> None:
    create_line_indexes()
    create_poem_indexes()


if __name__ == '__main__':
    create_indexes()
