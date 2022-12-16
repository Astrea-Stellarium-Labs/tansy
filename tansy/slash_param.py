import inspect
import types
import typing

import attrs
import naff


def get_option(t: naff.OptionTypes | type):
    if typing.get_origin(t) == typing.Annotated:
        t = typing.get_args(t)[1]

    if typing.get_origin(t) in {typing.Union, types.UnionType}:
        args = typing.get_args(t)
        if types.NoneType in args:  # optional type, get type within
            t = next(a for a in args if a is not types.NoneType)

    if isinstance(t, naff.OptionTypes):
        return t

    if issubclass(t, str):
        return naff.OptionTypes.STRING
    if issubclass(t, int):
        return naff.OptionTypes.INTEGER
    if issubclass(t, bool):
        return naff.OptionTypes.BOOLEAN
    if issubclass(t, naff.BaseUser):
        return naff.OptionTypes.USER
    if issubclass(t, naff.BaseChannel):
        return naff.OptionTypes.CHANNEL
    if issubclass(t, naff.Role):
        return naff.OptionTypes.ROLE
    if issubclass(t, float):
        return naff.OptionTypes.NUMBER
    if issubclass(t, naff.Attachment):
        return naff.OptionTypes.ATTACHMENT

    if typing.get_origin(t) in {typing.Union, types.UnionType}:
        args = typing.get_args(t)
        if (
            len(args) in {2, 3}
            and issubclass(args[0], (naff.BaseUser, naff.BaseChannel))
            and issubclass(args[1], (naff.BaseUser, naff.BaseChannel))
        ):
            return naff.OptionTypes.MENTIONABLE

    raise ValueError("Invalid type provided.")


def _converter_converter(value: typing.Any):
    if value is None:
        return None

    if isinstance(value, naff.Converter):
        return value
    else:
        raise ValueError(f"{repr(value)} is not a valid converter.")


@attrs.define(kw_only=True)
class ParamInfo:
    name: naff.LocalisedName | str | None = attrs.field(
        default=None, converter=naff.LocalisedName.converter
    )
    description: naff.LocalisedDesc | str = attrs.field(
        default="No Description Set", converter=naff.LocalisedDesc.converter
    )
    type: "naff.OptionTypes | None" = attrs.field(default=None)
    converter: typing.Optional[naff.Converter] = attrs.field(
        default=None, converter=_converter_converter
    )  # type: ignore
    default: typing.Any = attrs.field(default=naff.MISSING)
    required: bool = attrs.field(default=True)
    autocomplete: bool = attrs.field(default=False)
    choices: list[naff.SlashCommandChoice | dict] = attrs.field(factory=list)
    channel_types: list[naff.ChannelTypes | int] | None = attrs.field(default=None)
    min_value: typing.Optional[float] = attrs.field(default=None)
    max_value: typing.Optional[float] = attrs.field(default=None)
    min_length: typing.Optional[int] = attrs.field(repr=False, default=None)
    max_length: typing.Optional[int] = attrs.field(repr=False, default=None)

    def __attrs_post_init__(self):
        if self.converter and self.type is None:
            self.type = naff.OptionTypes.STRING

        if self.default is not naff.MISSING:
            self.required = False

    @type.validator  # type: ignore
    def _type_validator(self, attribute: str, value: naff.OptionTypes) -> None:
        if value in [
            naff.OptionTypes.SUB_COMMAND,
            naff.OptionTypes.SUB_COMMAND_GROUP,
        ]:
            raise ValueError(
                "Options cannot be SUB_COMMAND or SUB_COMMAND_GROUP. If you want to"
                " use subcommands, see the @sub_command() decorator."
            )

    @channel_types.validator  # type: ignore
    def _channel_types_validator(
        self, attribute: str, value: typing.Optional[list[naff.OptionTypes]]
    ) -> None:
        if value is not None:
            if self.type != naff.OptionTypes.CHANNEL:
                raise ValueError("The option needs to be CHANNEL to use this")

            allowed_int = [channel_type.value for channel_type in naff.ChannelTypes]
            for item in value:
                if (item not in allowed_int) and (item not in naff.ChannelTypes):
                    raise ValueError(f"{value} is not allowed here")

    @min_value.validator  # type: ignore
    def _min_value_validator(
        self, attribute: str, value: typing.Optional[float]
    ) -> None:
        if value is not None:
            if self.type not in [
                naff.OptionTypes.INTEGER,
                naff.OptionTypes.NUMBER,
            ]:
                raise ValueError(
                    "`min_value` can only be supplied with int or float options"
                )

            if self.type == naff.OptionTypes.INTEGER and isinstance(value, float):
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
        if value is not None:
            if self.type not in [
                naff.OptionTypes.INTEGER,
                naff.OptionTypes.NUMBER,
            ]:
                raise ValueError(
                    "`max_value` can only be supplied with int or float options"
                )

            if self.type == naff.OptionTypes.INTEGER and isinstance(value, float):
                raise ValueError("`max_value` needs to be an int in an int option")

            if self.max_value and self.min_value and self.max_value < self.min_value:
                raise ValueError("`min_value` needs to be <= than `max_value`")

    @min_length.validator
    def _min_length_validator(
        self, attribute: str, value: typing.Optional[int]
    ) -> None:
        if value is not None:
            if self.type != naff.OptionTypes.STRING:
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
        if value is not None:
            if self.type != naff.OptionTypes.STRING:
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

    def generate_option(self) -> naff.SlashCommandOption:
        return naff.SlashCommandOption(
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


def Param(
    *,
    name: naff.LocalisedName | str | None = None,
    description: naff.LocalisedDesc | str = "No Description Set",
    type: "typing.Optional[naff.OptionTypes | type]" = None,
    converter: typing.Optional[naff.Converter] = None,
    default: typing.Any = naff.MISSING,
    required: bool = True,
    autocomplete: bool = False,
    choices: list[naff.SlashCommandChoice | dict] | None = None,
    channel_types: list[naff.ChannelTypes | int] | None = None,
    min_value: float | None = None,
    max_value: float | None = None,
    min_length: int | None = None,
    max_length: int | None = None,
) -> typing.Any:
    return ParamInfo(
        name=name,
        type=get_option(type) if type is not None else type,
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


Option = Param
