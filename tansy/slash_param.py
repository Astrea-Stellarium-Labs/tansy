import inspect
import types
import typing

import attrs
import naff


def get_option(t: naff.OptionTypes | type):
    if typing.get_origin(t) == typing.Annotated:
        t = typing.get_args(t)[1]

    if isinstance(t, naff.OptionTypes):
        return t

    if isinstance(t, str):
        return naff.OptionTypes.STRING
    if isinstance(t, int):
        return naff.OptionTypes.INTEGER
    if isinstance(t, bool):
        return naff.OptionTypes.BOOLEAN
    if isinstance(t, naff.BaseUser):
        return naff.OptionTypes.USER
    if isinstance(t, naff.BaseChannel):
        return naff.OptionTypes.CHANNEL
    if isinstance(t, naff.Role):
        return naff.OptionTypes.ROLE
    if isinstance(t, float):
        return naff.OptionTypes.NUMBER
    if isinstance(t, naff.Attachment):
        return naff.OptionTypes.ATTACHMENT

    if typing.get_origin(t) in {typing.Union, types.UnionType}:
        args = typing.get_args(t)
        if (
            len(args) in {2, 3}
            and isinstance(args[0], (naff.BaseUser, naff.BaseChannel))
            and isinstance(args[1], (naff.BaseUser, naff.BaseChannel))
        ):
            return naff.OptionTypes.MENTIONABLE

    return naff.OptionTypes.STRING


def _converter_converter(value: typing.Any):
    if value is None:
        return None

    if isinstance(value, naff.Converter):
        return value
    else:
        raise ValueError(f"{repr(value)} is not a valid converter.")


@attrs.define(kw_only=True)
class ParamInfo:
    name: naff.LocalisedName = attrs.field(
        default=None, converter=naff.LocalisedName.converter
    )
    type: "typing.Optional[naff.OptionTypes | type]" = attrs.field(default=None)
    converter: typing.Optional[naff.Converter] = attrs.field(
        default=None, converter=_converter_converter
    )  # type: ignore
    default: typing.Any = attrs.field(default=naff.MISSING)
    description: naff.LocalisedDesc = attrs.field(
        default="No Description Set", converter=naff.LocalisedDesc.converter
    )
    required: bool = attrs.field(default=True)
    autocomplete: typing.Callable = attrs.field(default=None)
    choices: list[naff.SlashCommandChoice | dict] = attrs.field(factory=list)
    channel_types: list[naff.ChannelTypes | int] | None = attrs.field(default=None)
    min_value: float = attrs.field(default=None)
    max_value: float = attrs.field(default=None)

    _option_type: naff.Absent[naff.OptionTypes] = attrs.field(
        default=naff.MISSING
    )  # type: ignore

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

    def __attrs_post_init__(self):
        if self.type:
            self._option_type = get_option(self.type)
        elif self.converter:
            self._option_type = naff.OptionTypes.STRING

        if self.default is not naff.MISSING:
            self.required = False

    def generate_option(self) -> naff.SlashCommandOption:
        return naff.SlashCommandOption(
            name=self.name,
            type=self._option_type,  # type: ignore
            description=self.description,
            required=self.required,
            autocomplete=bool(self.autocomplete),
            choices=self.choices or [],
            channel_types=self.channel_types,
            min_value=self.min_value,
            max_value=self.max_value,
        )


def Param(
    *,
    name: naff.LocalisedName | str = None,
    type: "typing.Optional[naff.OptionTypes | type]" = None,
    converter: typing.Optional[naff.Converter] = None,
    default: typing.Any = naff.MISSING,
    description: naff.LocalisedDesc | str = "No Description Set",
    required: bool = True,
    autocomplete: typing.Callable = None,
    choices: list[naff.SlashCommandChoice | dict,] = None,
    channel_types: list[naff.ChannelTypes | int] = None,
    min_value: float = None,
    max_value: float = None,
) -> typing.Any:
    return ParamInfo(
        name=name,
        type=type,
        converter=converter,
        default=default,
        description=description,
        required=required,
        autocomplete=autocomplete,
        choices=choices,
        channel_types=channel_types,
        min_value=min_value,
        max_value=max_value,
    )
