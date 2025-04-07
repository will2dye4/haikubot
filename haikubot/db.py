from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import random
import re

from bson import ObjectId
from pymongo import DESCENDING, MongoClient
from pymongo.cursor import Cursor

from haikubot import config


DEFAULT_DB_HOST = 'localhost'
DEFAULT_DB_PORT = 27017
DEFAULT_DB_NAME = 'haiku'


client = MongoClient(host=config.get('db.host', DEFAULT_DB_HOST),
                     port=config.get('db.port', DEFAULT_DB_PORT))
db = client[config.get('db.name', DEFAULT_DB_NAME)]


@dataclass(frozen=True)
class SlackContext:
    user_id: str
    channel_id: str
    team_id: str

    @classmethod
    def from_bson(cls, bson: dict[str, Any]) -> 'SlackContext':
        return cls(user_id=bson['user_id'], channel_id=bson['channel_id'], team_id=bson['team_id'])


@dataclass(frozen=True)
class HaikuLine:
    text: str
    syllables: int
    context: SlackContext
    created: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    id: Optional[ObjectId] = None

    @classmethod
    def from_bson(cls, bson: dict[str, Any]) -> 'HaikuLine':
        return cls(text=bson['text'], syllables=bson['syllables'], context=SlackContext.from_bson(bson),
                   created=bson['created'], id=bson['_id'])

    def to_bson(self) -> dict[str, Any]:
        obj: dict[str, Any] = {
            'text': self.text,
            'syllables': self.syllables,
            'user_id': self.context.user_id,
            'channel_id': self.context.channel_id,
            'team_id': self.context.team_id,
            'created': self.created,
        }
        if self.id:
            obj['_id'] = self.id
        return obj


@dataclass(frozen=True)
class Haiku:
    lines: list[HaikuLine]
    context: SlackContext
    created: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    id: Optional[ObjectId] = None

    @classmethod
    def from_lines(cls, lines: list[HaikuLine], context: SlackContext) -> 'Haiku':
        return cls(lines=lines, context=context)

    @classmethod
    def from_bson(cls, bson: dict[str, Any]) -> 'Haiku':
        bson['user_id'] = None  # Haikus don't have a single user_id (they have multiple).
        lines = [
            HaikuLine(
                text=line['text'],
                syllables=5 if i % 2 == 0 else 7,
                context=SlackContext(user_id=line['user_id'], channel_id=bson['channel_id'], team_id=bson['team_id']),
                created=bson['created'],
                id=bson['_id']
            )
            for i, line in enumerate(bson['lines'])
        ]
        return cls(lines=lines, context=SlackContext.from_bson(bson))

    @property
    def text(self) -> str:
        return '\n'.join(line.text for line in self.lines)

    @property
    def user_ids(self) -> list[str]:
        return [line.context.user_id for line in self.lines]

    def to_bson(self) -> dict[str, Any]:
        obj: dict[str, Any] = {
            'lines': [
                {'text': line.text, 'user_id': line.context.user_id, '_id': line.id}
                for line in self.lines
            ],
            'channel_id': self.context.channel_id,
            'team_id': self.context.team_id,
            'created': self.created,
        }
        if self.id:
            obj['_id'] = self.id
        return obj


@dataclass(frozen=True)
class HaikuStats:
    five_syllable_lines: int
    seven_syllable_lines: int
    total_poems: int
    unique_users: int

    @classmethod
    def from_cursor(cls, cursor: Cursor, total_poems: int) -> 'HaikuStats':
        syllables = defaultdict(int)
        user_ids = set()
        for row in cursor:
            syllables[row['syllables']] += 1
            user_ids.add(row['user_id'])
        return cls(five_syllable_lines=syllables[5], seven_syllable_lines=syllables[7],
                   total_poems=total_poems, unique_users=len(user_ids))

    @property
    def total_lines(self) -> int:
        return self.five_syllable_lines + self.seven_syllable_lines


def get_random_lines(syllables: int, context: SlackContext, user_id: Optional[str] = None,
                     search_term: Optional[str] = None, exclude_ids: Optional[list[ObjectId]] = None,
                     sample_size: int = 1) -> list[HaikuLine]:
    match: dict[str, Any] = {'syllables': syllables, 'team_id': context.team_id}
    if user_id:
        match['user_id'] = user_id
    if search_term:
        try:
            match['text'] = re.compile(search_term, re.IGNORECASE)
        except re.error:
            match['text'] = re.compile(re.escape(search_term), re.IGNORECASE)
    if exclude_ids:
        match['_id'] = {'$nin': exclude_ids}
    rows = db.lines.aggregate([{'$match': match}, {'$sample': {'size': sample_size}}]).to_list()
    lines = list(set(HaikuLine.from_bson(row) for row in rows))  # $sample may return duplicate rows
    random.shuffle(lines)
    return lines


def generate_random_haiku(context: SlackContext, user_id: Optional[str] = None,
                          search_term: Optional[str] = None) -> Optional[Haiku]:
    found_search_term = search_term is None
    fives = get_random_lines(syllables=5, context=context, user_id=user_id, search_term=search_term, sample_size=4)
    if fives:
        found_search_term = True
    if len(fives) < 2:
        if search_term:
            fives.extend(get_random_lines(syllables=5, context=context, user_id=user_id,
                                          exclude_ids=[line.id for line in fives], sample_size=4))
            if len(fives) < 2:
                return None
        else:
            return None

    sevens = get_random_lines(syllables=7, context=context, user_id=user_id, search_term=search_term)
    if sevens:
        found_search_term = True
    elif search_term:
        if not (extra_sevens := get_random_lines(syllables=7, context=context, user_id=user_id)):
            return None
        sevens = extra_sevens
    else:
        return None

    if not found_search_term:
        return None

    haiku = Haiku.from_lines(lines=[fives[0], sevens[0], fives[1]], context=context)
    result = db.poems.insert_one(haiku.to_bson())
    if not result.inserted_id:
        print(f'Failed to insert haiku into DB! (team: {context.team_id}, channel: {context.channel_id})')
    return haiku


def add_haiku_line(text: str, syllables: int, context: SlackContext) -> bool:
    if db.lines.count_documents({'text': text, 'syllables': syllables, 'team_id': context.team_id}) > 0:
        return True
    line = HaikuLine(text=text, syllables=syllables, context=context)
    result = db.lines.insert_one(line.to_bson())
    return bool(result.inserted_id)


def remove_haiku_line(text: str, syllables: int, context: SlackContext) -> bool:
    result = db.lines.delete_many({'text': text, 'syllables': syllables, 'team_id': context.team_id})
    return result.deleted_count > 0


def get_haiku_blame(context: SlackContext) -> Optional[list[str]]:
    latest_haiku = db.poems.find_one({'channel_id': context.channel_id, 'team_id': context.team_id},
                                     sort=[('created', DESCENDING)])
    if not latest_haiku:
        return None
    return Haiku.from_bson(latest_haiku).user_ids


def get_haiku_stats(context: SlackContext) -> HaikuStats:
    return HaikuStats.from_cursor(cursor=db.lines.find({'team_id': context.team_id}),
                                  total_poems=db.poems.count_documents({'team_id': context.team_id}))
