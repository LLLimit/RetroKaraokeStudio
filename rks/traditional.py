"""Offline Simplified Chinese to Hong Kong Traditional conversion."""
from __future__ import annotations

from opencc import OpenCC
from .model import Word

_converter = OpenCC('s2hk')


def to_hong_kong_traditional(text: str, words: list[Word]) -> tuple[str, list[Word]]:
    converted = _converter.convert(text)
    if not words:
        return converted, []
    original_length = sum(len(word.text) for word in words)
    if len(converted) == original_length:
        cursor = 0
        updated = []
        for word in words:
            length = len(word.text)
            updated.append(Word(converted[cursor:cursor+length], word.start, word.end,
                                word.estimated, word.tag))
            cursor += length
        return converted, updated

    if not converted or not original_length:
        return converted, []
    original_chars = []
    for word in words:
        length = max(1, len(word.text))
        for index in range(len(word.text)):
            start = word.start + (word.end-word.start) * index / length
            end = word.start + (word.end-word.start) * (index+1) / length
            original_chars.append((start, end, word.estimated, word.tag))

    def time_at(position: float) -> float:
        index = min(len(original_chars)-1, int(position))
        if position >= len(original_chars):
            return original_chars[-1][1]
        start, end, _, _ = original_chars[index]
        return start + (end-start) * (position-index)

    updated = []
    for index, char in enumerate(converted):
        source_index = min(len(original_chars)-1, int(index*len(original_chars)/len(converted)))
        _, _, estimated, tag = original_chars[source_index]
        start = time_at(index*len(original_chars)/len(converted))
        end = time_at((index+1)*len(original_chars)/len(converted))
        updated.append(Word(char, start, end, estimated, tag))
    return converted, updated
