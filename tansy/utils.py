import itertools
import types
import typing

import naff

REVERSE_CHANNEL_MAPPING = {v: k for k, v in naff.TYPE_CHANNEL_MAPPING.items()}

UNION_TYPES = {typing.Union, types.UnionType}

USER_TYPES = (naff.BaseUser, naff.User, naff.Member)
USER_PRODUCT = itertools.product(USER_TYPES, USER_TYPES, USER_TYPES)

MENTIONABLE_UNIONS = frozenset(
    typing.Union[naff.Role, i, j, k] for i, j, k in USER_PRODUCT
)
USER_UNIONS = frozenset(typing.Union[i, j, k] for i, j, k in USER_PRODUCT)


def is_union(anno: typing.Any):
    return typing.get_origin(anno) in UNION_TYPES


def get_from_anno_type(anno: typing.Annotated) -> typing.Any:
    """
    Handles dealing with Annotated annotations, getting their (first) type annotation.
    This allows correct type hinting with, say, Converters, for example.
    """
    # this is treated how it usually is during runtime
    # the first argument is ignored and the rest is treated as is

    return typing.get_args(anno)[1]


def issubclass_failsafe(
    arg: typing.Any, cls: typing.Type | typing.Tuple[typing.Type]
) -> bool:
    try:
        return issubclass(arg, cls)
    except TypeError:
        return False


def is_optional(anno: typing.Any):
    return is_union(anno) and types.NoneType in typing.get_args(anno)


def filter_extras(t: naff.OptionTypes | type):
    if typing.get_origin(t) == typing.Annotated:
        t = get_from_anno_type(t)

    if is_optional(t):
        non_optional_args: tuple[type] = tuple(
            a for a in typing.get_args(t) if a is not types.NoneType
        )
        if len(non_optional_args) == 1:
            return non_optional_args[0]
        return typing.Union[non_optional_args]  # type: ignore

    return t


def get_option(t: naff.OptionTypes | type):
    t = filter_extras(t)

    if isinstance(t, naff.OptionTypes):
        return t

    if t == str:
        return naff.OptionTypes.STRING
    if t == int:
        return naff.OptionTypes.INTEGER
    if t == bool:
        return naff.OptionTypes.BOOLEAN
    if issubclass_failsafe(t, (naff.BaseUser, naff.Member)) or t in USER_UNIONS:
        return naff.OptionTypes.USER
    if issubclass_failsafe(t, naff.BaseChannel):
        return naff.OptionTypes.CHANNEL
    if t == naff.Role:
        return naff.OptionTypes.ROLE
    if t == float:
        return naff.OptionTypes.NUMBER
    if t == naff.Attachment:
        return naff.OptionTypes.ATTACHMENT
    if t in MENTIONABLE_UNIONS:
        return naff.OptionTypes.MENTIONABLE

    if is_union(t):
        args = typing.get_args(t)
        if all(issubclass_failsafe(a, naff.BaseChannel) for a in args):
            return naff.OptionTypes.CHANNEL

    raise ValueError("Invalid type provided.")


def resolve_channel_types(anno: typing.Any):
    channel_types = []

    anno = filter_extras(anno)

    if isinstance(anno, naff.OptionTypes):
        return None

    if issubclass_failsafe(anno, naff.BaseChannel) and (
        chan_type := REVERSE_CHANNEL_MAPPING.get(anno)
    ):
        channel_types = [chan_type]
    elif is_union(anno):
        for arg in typing.get_args(anno):
            if chan_type := REVERSE_CHANNEL_MAPPING.get(arg):
                channel_types.append(chan_type)

    return channel_types or None
