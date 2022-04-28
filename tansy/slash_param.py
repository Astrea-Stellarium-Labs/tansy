import inspect
import types
import typing

import attrs
import dis_snek


def _get_option(t: dis_snek.OptionTypes | type):
    if isinstance(t, dis_snek.OptionTypes):
        return t

    if isinstance(t, str):
        return dis_snek.OptionTypes.STRING
    if isinstance(t, int):
        return dis_snek.OptionTypes.INTEGER
    if isinstance(t, bool):
        return dis_snek.OptionTypes.BOOLEAN
    if isinstance(t, dis_snek.BaseUser):
        return dis_snek.OptionTypes.USER
    if isinstance(t, dis_snek.BaseChannel):
        return dis_snek.OptionTypes.CHANNEL
    if isinstance(t, dis_snek.Role):
        return dis_snek.OptionTypes.ROLE
    if isinstance(t, float):
        return dis_snek.OptionTypes.NUMBER
    if isinstance(t, dis_snek.Attachment):
        return dis_snek.OptionTypes.ATTACHMENT

    if typing.get_origin(t) in {typing.Union, types.UnionType}:
        args = typing.get_args(t)
        if (
            len(args) in {2, 3}
            and isinstance(args[0], (dis_snek.BaseUser, dis_snek.BaseChannel))
            and isinstance(args[1], (dis_snek.BaseUser, dis_snek.BaseChannel))
        ):
            return dis_snek.OptionTypes.MENTIONABLE

    return dis_snek.OptionTypes.STRING


def _converter_converter(value: typing.Any):
    if value is inspect._empty:
        return dis_snek.Missing

    if isinstance(value, dis_snek.Converter):
        return value
    else:
        raise ValueError(f"{repr(value)} is not a valid converter.")


@attrs.define(kw_only=True)
class ParamInfo:
    name: dis_snek.LocalisedName = attrs.field(
        default=None, converter=dis_snek.LocalisedName.converter
    )
    type: "typing.Optional[dis_snek.OptionTypes | type]" = attrs.field(default=None)
    converter: typing.Optional[dis_snek.Converter] = attrs.field(
        default=None, converter=_converter_converter
    )
    default: typing.Any = attrs.field(default=dis_snek.Missing)
    description: dis_snek.LocalisedDesc = attrs.field(
        default="No Description Set", converter=dis_snek.LocalisedDesc.converter
    )
    required: bool = attrs.field(default=True)
    autocomplete: typing.Callable = attrs.field(default=None)
    choices: list[dis_snek.SlashCommandChoice | dict] = attrs.field(factory=list)
    channel_types: list[dis_snek.ChannelTypes | int] | None = attrs.field(default=None)
    min_value: float = attrs.field(default=None)
    max_value: float = attrs.field(default=None)
    autocomplete_function: typing.Callable = attrs.field(default=None)

    _option_type: dis_snek.Absent[dis_snek.OptionTypes] = attrs.field(
        default=dis_snek.Missing
    )

    @type.validator  # type: ignore
    def _type_validator(self, attribute: str, value: dis_snek.OptionTypes) -> None:
        if value in [
            dis_snek.OptionTypes.SUB_COMMAND,
            dis_snek.OptionTypes.SUB_COMMAND_GROUP,
        ]:
            raise ValueError(
                "Options cannot be SUB_COMMAND or SUB_COMMAND_GROUP. If you want to use"
                " subcommands, see the @sub_command() decorator."
            )

    @channel_types.validator  # type: ignore
    def _channel_types_validator(
        self, attribute: str, value: typing.Optional[list[dis_snek.OptionTypes]]
    ) -> None:
        if value is not None:
            if self.type != dis_snek.OptionTypes.CHANNEL:
                raise ValueError("The option needs to be CHANNEL to use this")

            allowed_int = [channel_type.value for channel_type in dis_snek.ChannelTypes]
            for item in value:
                if (item not in allowed_int) and (item not in dis_snek.ChannelTypes):
                    raise ValueError(f"{value} is not allowed here")

    @min_value.validator  # type: ignore
    def _min_value_validator(
        self, attribute: str, value: typing.Optional[float]
    ) -> None:
        if value is not None:
            if self.type not in [
                dis_snek.OptionTypes.INTEGER,
                dis_snek.OptionTypes.NUMBER,
            ]:
                raise ValueError(
                    "`min_value` can only be supplied with int or float options"
                )

            if self.type == dis_snek.OptionTypes.INTEGER and isinstance(value, float):
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
                dis_snek.OptionTypes.INTEGER,
                dis_snek.OptionTypes.NUMBER,
            ]:
                raise ValueError(
                    "`max_value` can only be supplied with int or float options"
                )

            if self.type == dis_snek.OptionTypes.INTEGER and isinstance(value, float):
                raise ValueError("`max_value` needs to be an int in an int option")

            if self.max_value and self.min_value and self.max_value < self.min_value:
                raise ValueError("`min_value` needs to be <= than `max_value`")

    def __attrs_post_init__(self):
        if self.type:
            self._option_type = _get_option(self.type)
        elif self.converter:
            self._option_type = dis_snek.OptionTypes.STRING

        if self.default:
            self.required = False

    def generate_option(self) -> dis_snek.SlashCommandOption:
        return dis_snek.SlashCommandOption(
            name=self.name,
            type=self._option_type,
            description=self.description,
            required=self.required,
            autocomplete=bool(self.autocomplete_function),
            choices=self.choices,
            channel_types=self.channel_types,
            min_value=self.min_value,
            max_value=self.max_value,
        )
