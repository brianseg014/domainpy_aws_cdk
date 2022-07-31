import re
import math
import typing
import hashlib

HIDDEN_FROM_HUMAN_ID = "Resource"

HIDDEN_ID = "Default"

PATH_SEP = "/"

MAX_LEN = 256
HASH_LEN = 8


def make_unique_resource_name(
    components: typing.Sequence[str],
    separator: str,
    allowed_special_characters: str,
) -> str:
    components = [c for c in components if c != HIDDEN_ID]

    if len(components) == 0:
        raise Exception(
            "Unable to calculate a unique id for an empty set of components"
        )

    if len(components) == 1:
        candidate = remove_non_allowd_special_characters(
            components[0], allowed_special_characters
        )

        if len(candidate) <= MAX_LEN:
            return candidate

    hash = path_hash(components)
    human = separator.join(
        [
            remove_non_allowd_special_characters(c, allowed_special_characters)
            for c in components
            if c != HIDDEN_FROM_HUMAN_ID and len(c) > 0
        ]
    )

    max_human_len = MAX_LEN - HASH_LEN
    return (
        f"{split_in_middle(human, max_human_len)}{hash}"
        if len(human) > max_human_len
        else f"{human}{hash}"
    )


def path_hash(path: typing.Sequence[str]) -> str:
    md5 = hashlib.md5(PATH_SEP.join(path).encode("utf-8")).hexdigest()
    return md5[:HASH_LEN].upper()


def remove_non_allowd_special_characters(
    s: str, allowed_special_characters: str
) -> str:
    return re.sub(f"[^A-Za-z0-9{allowed_special_characters}]", "", s)


def split_in_middle(s, max_len: int = MAX_LEN - HASH_LEN) -> str:
    half = math.floor(max_len / 2)
    return s[:half] + s[-half:]


def remove_dupes(path: typing.Sequence[str]) -> typing.Sequence[str]:
    ret: typing.List[str] = []

    for component in path:
        if len(ret) == 0 or not ret[len(ret) - 1].endswith(component):
            ret.append(component)

    return ret
