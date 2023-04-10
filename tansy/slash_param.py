import typing
from builtins import hasattr

import attrs
import interactions as ipy

from . import utils

if typing.TYPE_CHECKING:
    from .slash_commands import TansySlashCommand

    SlashCommandT = typing.TypeVar(
        "SlashCommandT", "TansySlashCommand", ipy.const.AsyncCallable
    )

__all__ = ("ParamInfo", "Option", "Param", "describe")


@attrs.define(kw_only=True)
class ParamInfo:
    name: ipy.LocalisedName | str | None = attrs.field(
        default=None, converter=ipy.LocalisedName.converter
    )
    description: ipy.LocalisedDesc | str = attrs.field(
        default="No Description Set", converter=ipy.LocalisedDesc.converter
    )
    type: "ipy.OptionType | None" = attrs.field(default=None)
    converter: typing.Optional[ipy.Converter | typing.Callable] = attrs.field(
        default=None,
    )
    default: typing.Any = attrs.field(default=ipy.MISSING)
    required: bool = attrs.field(default=True)
    autocomplete: bool = attrs.field(default=False)
    choices: list[ipy.SlashCommandChoice | dict] = attrs.field(factory=list)
    channel_types: list[ipy.ChannelType | int] | None = attrs.field(default=None)
    min_value: typing.Optional[float] = attrs.field(default=None)
    max_value: typing.Optional[float] = attrs.field(default=None)
    min_length: typing.Optional[int] = attrs.field(repr=False, default=None)
    max_length: typing.Optional[int] = attrs.field(repr=False, default=None)

    _user_provided_type: typing.Any = attrs.field(repr=False, default=None)

    def __attrs_post_init__(self):
        if self.default is not ipy.MISSING:
            self.required = False

        if self.required and utils.is_optional(self._user_provided_type):
            self.required = False
            self.default = None

        if not self.required and self.default is ipy.MISSING:
            raise ValueError(
                f"{self.name} is not required, but no default has been set!"
            )

        if self.type == ipy.OptionType.CHANNEL and not self.channel_types:
            self.channel_types = utils.resolve_channel_types(self._user_provided_type)  # type: ignore

    @channel_types.validator  # type: ignore
    def _channel_types_validator(
        self, attribute: str, value: typing.Optional[list[ipy.OptionType]]
    ) -> None:
        if value is not None and self.type is not None:
            if self.type != ipy.OptionType.CHANNEL:
                raise ValueError("The option needs to be CHANNEL to use this")

            allowed_int = {channel_type.value for channel_type in ipy.ChannelType}
            for item in value:
                if (item not in allowed_int) and (item not in ipy.ChannelType):
                    raise ValueError(f"{value} is not allowed here")

    @min_value.validator  # type: ignore
    def _min_value_validator(
        self, attribute: str, value: typing.Optional[float]
    ) -> None:
        if value is not None and self.type is not None:
            if self.type not in [
                ipy.OptionType.INTEGER,
                ipy.OptionType.NUMBER,
            ]:
                raise ValueError(
                    "`min_value` can only be supplied with int or float options"
                )

            if self.type == ipy.OptionType.INTEGER and isinstance(value, float):
                raise ValueError("`min_value` needs to be an int in an int option")

            if (
                self.max_value is not None
                and self.min_value is not None
                and self.max_value < self.min_value
            ):
                raise ValueError("`min_value` needs to be <= than `max_value`")

    @max_value.validator  # type: ignore
    def _max_value_validator(
        self, attribute: str, value: typing.Optional[float]
    ) -> None:
        if value is not None and self.type is not None:
            if self.type not in [
                ipy.OptionType.INTEGER,
                ipy.OptionType.NUMBER,
            ]:
                raise ValueError(
                    "`max_value` can only be supplied with int or float options"
                )

            if self.type == ipy.OptionType.INTEGER and isinstance(value, float):
                raise ValueError("`max_value` needs to be an int in an int option")

            if self.max_value and self.min_value and self.max_value < self.min_value:
                raise ValueError("`min_value` needs to be <= than `max_value`")

    @min_length.validator
    def _min_length_validator(
        self, attribute: str, value: typing.Optional[int]
    ) -> None:
        if value is not None and self.type is not None:
            if self.type != ipy.OptionType.STRING:
                raise ValueError(
                    "`min_length` can only be supplied with string options"
                )

            if (
                self.max_length is not None
                and self.min_length is not None
                and self.max_length < self.min_length
            ):
                raise ValueError("`min_length` needs to be <= than `max_length`")

            if self.min_length < 0:
                raise ValueError("`min_length` needs to be >= 0")

    @max_length.validator
    def _max_length_validator(
        self, attribute: str, value: typing.Optional[int]
    ) -> None:
        if value is not None and self.type is not None:
            if self.type != ipy.OptionType.STRING:
                raise ValueError(
                    "`max_length` can only be supplied with string options"
                )

            if (
                self.min_length is not None
                and self.max_length is not None
                and self.max_length < self.min_length
            ):
                raise ValueError("`min_length` needs to be <= than `max_length`")

            if self.max_length < 1:
                raise ValueError("`max_length` needs to be >= 1")

    def generate_option(self) -> ipy.SlashCommandOption:
        with attrs.validators.disabled():
            return ipy.SlashCommandOption(
                name=self.name,
                type=self.type,
                description=self.description,
                required=self.required,
                autocomplete=self.autocomplete,
                choices=self.choices or [],
                channel_types=self.channel_types,
                min_value=self.min_value,
                max_value=self.max_value,
                min_length=self.min_length,
                max_length=self.max_length,
            )


def Option(
    description: ipy.LocalisedDesc | str = "No Description Set",
    *,
    name: ipy.LocalisedName | str | None = None,
    type: typing.Any = None,
    converter: typing.Optional[ipy.Converter | typing.Callable] = None,
    default: typing.Any = ipy.MISSING,
    required: bool = True,
    autocomplete: bool = False,
    choices: list[ipy.SlashCommandChoice | dict] | None = None,
    channel_types: list[ipy.ChannelType | int] | None = None,
    min_value: float | None = None,
    max_value: float | None = None,
    min_length: int | None = None,
    max_length: int | None = None,
) -> typing.Any:
    return ParamInfo(
        name=name,
        type=utils.get_option(type) if type is not None else None,
        user_provided_type=type,  # type: ignore
        converter=converter,
        default=default,
        description=description,
        required=required,
        autocomplete=autocomplete,
        choices=choices or [],
        channel_types=channel_types,
        min_value=min_value,
        max_value=max_value,
        min_length=min_length,
        max_length=max_length,
    )


Param = Option


def describe(
    name: str, description: ipy.LocalisedDesc | str
) -> typing.Callable[["SlashCommandT"], "SlashCommandT"]:
    """
    A decorator to add a description to a slash command.

    Args:
        name (str): The name of the description.
        description (str): The description to add.

    Returns:
        Either the callback or slash command.
    """

    def decorator(func: "SlashCommandT") -> "SlashCommandT":
        if hasattr(func, "callback"):
            func = func.callback
        if not hasattr(func, "__tansy_describe__"):
            func.__tansy_describe__ = {}
        func.__tansy_describe__[name] = ipy.LocalisedDesc.converter(description)
        return func

    return decorator
