from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import random
import re

from bson import ObjectId
from pymongo import DESCENDING, MongoClient
from pymongo.cursor import Cursor

from haikubot import config
from haikubot.constants import DEFAULT_DB_NAME, DEFAULT_DB_PORT, DEFAULT_DB_HOST
from haikubot.slack import SlackContext


BSON = dict[str, Any]


client = MongoClient(host=config.get('db.host', DEFAULT_DB_HOST),
                     port=config.get('db.port', DEFAULT_DB_PORT))
db = client[config.get('db.name', DEFAULT_DB_NAME)]


class LinePosition(Enum):
    FIRST = 'first'
    LAST = 'last'

    @classmethod
    def value_of(cls, string: str) -> Optional['LinePosition']:
        return next((f for f in cls if f.value == string), None)


@dataclass(frozen=True)
class HaikuLine:
    text: str
    syllables: int
    context: SlackContext
    created: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    position: Optional[LinePosition] = None
    id: Optional[ObjectId] = None

    @classmethod
    def from_bson(cls, bson: BSON) -> 'HaikuLine':
        position = LinePosition.value_of(bson.get('position', ''))
        return cls(text=bson['text'], syllables=bson['syllables'], context=SlackContext.from_bson(bson),
                   created=bson['created'], position=position, id=bson['_id'])

    def to_bson(self) -> BSON:
        obj: BSON = {
            'text': self.text,
            'syllables': self.syllables,
            'user_id': self.context.user_id,
            'channel_id': self.context.channel_id,
            'team_id': self.context.team_id,
            'created': self.created,
        }
        if self.id:
            obj['_id'] = self.id
        if self.position:
            obj['position'] = self.position.value
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
    def from_bson(cls, bson: BSON) -> 'Haiku':
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

    def to_bson(self) -> BSON:
        obj: BSON = {
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

    @property
    def possible_combinations(self) -> int:
        return self.five_syllable_lines * self.seven_syllable_lines * (self.five_syllable_lines - 1)


def get_random_lines(syllables: int, context: SlackContext, user_id: Optional[str] = None,
                     search_term: Optional[str] = None, exclude_ids: Optional[list[ObjectId]] = None,
                     exclude_position: Optional[LinePosition] = None, sample_size: int = 1) -> list[HaikuLine]:
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
    if exclude_position:
        match['position'] = {'$ne': exclude_position.value}
    rows = db.lines.aggregate([{'$match': match}, {'$sample': {'size': sample_size}}]).to_list()
    lines = list(set(HaikuLine.from_bson(row) for row in rows))  # $sample may return duplicate rows
    random.shuffle(lines)
    return lines


def get_random_fives(context: SlackContext, user_id: Optional[str] = None,
                     search_term: Optional[str] = None) -> tuple[bool, list[HaikuLine]]:
    syllables = 5
    found_search_term = search_term is None
    lines = get_random_lines(syllables=syllables, context=context, user_id=user_id,
                             search_term=search_term, sample_size=4)
    matching_lines = []
    if lines:
        found_search_term = True
        matching_lines = lines.copy()
    if len(lines) < 2:
        if search_term:
            lines.extend(get_random_lines(syllables=syllables, context=context, user_id=user_id,
                                          exclude_ids=[line.id for line in lines], sample_size=4))
            if len(lines) < 2:
                return False, []
        else:
            return False, []

    first_line = next((line for line in matching_lines if line.position != LinePosition.LAST),
        next((line for line in lines if line.position != LinePosition.LAST), None))
    if not first_line:
        if not (extra_lines := get_random_lines(syllables=syllables, context=context, user_id=user_id,
                                                exclude_position=LinePosition.LAST)):
            return False, []
        first_line = extra_lines[0]

    if first_line in matching_lines:
        matching_lines.remove(first_line)
    lines.remove(first_line)

    last_line = next((line for line in matching_lines if line.position != LinePosition.FIRST),
        next((line for line in lines if line.position != LinePosition.FIRST), None))
    if not last_line:
        if not (extra_lines := get_random_lines(syllables=syllables, context=context, user_id=user_id,
                                                exclude_position=LinePosition.FIRST)):
            return False, []
        last_line = extra_lines[0]

    return found_search_term, [first_line, last_line]


def get_random_seven(context: SlackContext, user_id: Optional[str] = None,
                     search_term: Optional[str] = None) -> tuple[bool, Optional[HaikuLine]]:
    syllables = 7
    lines = get_random_lines(syllables=syllables, context=context, user_id=user_id, search_term=search_term)
    if lines:
        return True, lines[0]
    if search_term:
        if lines := get_random_lines(syllables=syllables, context=context, user_id=user_id):
            return False, lines[0]
    return False, None


def generate_random_haiku(context: SlackContext, user_id: Optional[str] = None,
                          search_term: Optional[str] = None) -> Optional[Haiku]:
    found_search_term_fives, fives = get_random_fives(context, user_id=user_id, search_term=search_term)
    found_search_term_seven, seven = get_random_seven(context, user_id=user_id, search_term=search_term)

    if not fives or not seven or (not found_search_term_fives and not found_search_term_seven):
        return None

    haiku = Haiku.from_lines(lines=[fives[0], seven, fives[1]], context=context)
    result = db.poems.insert_one(haiku.to_bson())
    if not result.inserted_id:
        print(f'Failed to insert haiku into DB! (team: {context.team_id}, channel: {context.channel_id})')
    return haiku


def add_haiku_line(text: str, syllables: int, context: SlackContext, position: Optional[LinePosition] = None) -> bool:
    if db.lines.count_documents(get_line_key(text, syllables, context)) > 0:
        return True
    line = HaikuLine(text=text, syllables=syllables, context=context, position=position)
    result = db.lines.insert_one(line.to_bson())
    return bool(result.inserted_id)


def remove_haiku_line(text: str, syllables: int, context: SlackContext) -> bool:
    result = db.lines.delete_many(get_line_key(text, syllables, context))
    return result.deleted_count > 0


def claim_haiku_line(text: str, syllables: int, context: SlackContext) -> bool:
    if not (line := get_haiku_line(text, syllables, context)):
        return False
    result = db.lines.update_one(filter={'_id': line.id}, update={'$set': {'user_id': context.user_id}})
    if result.modified_count == 0:
        return False
    # Try to update the poems, but don't fail if there are none for some reason.
    db.poems.update_many(filter={'team_id': context.team_id},
                         update={'$set': {'lines.$[line].user_id': context.user_id}},
                         array_filters=[{'line._id': line.id}])
    return True


def get_haiku_line(text: str, syllables: int, context: SlackContext) -> Optional[HaikuLine]:
    if line := db.lines.find_one(get_line_key(text, syllables, context)):
        return HaikuLine.from_bson(line)
    return None


def get_line_key(text: str, syllables: int, context: SlackContext) -> BSON:
    return {'text': text, 'syllables': syllables, 'team_id': context.team_id}


def get_haiku_blame(context: SlackContext) -> Optional[list[str]]:
    latest_haiku = db.poems.find_one({'channel_id': context.channel_id, 'team_id': context.team_id},
                                     sort=[('created', DESCENDING)])
    if not latest_haiku:
        return None
    return Haiku.from_bson(latest_haiku).user_ids


def get_haiku_stats(context: SlackContext, user_id: Optional[str] = None) -> HaikuStats:
    line_filter: dict[str, Any] = {'team_id': context.team_id}
    poem_filter: dict[str, Any] = {'team_id': context.team_id}
    if user_id:
        line_filter['user_id'] = user_id
        poem_filter['lines'] = {'$elemMatch': {'user_id': user_id}}
    return HaikuStats.from_cursor(cursor=db.lines.find(line_filter), total_poems=db.poems.count_documents(poem_filter))
