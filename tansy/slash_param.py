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

    if t == str:
        return naff.OptionTypes.STRING
    if t == int:
        return naff.OptionTypes.INTEGER
    if t == bool:
        return naff.OptionTypes.BOOLEAN
    if issubclass(t, naff.BaseUser):
        return naff.OptionTypes.USER
    if issubclass(t, naff.BaseChannel):
        return naff.OptionTypes.CHANNEL
    if t == naff.Role:
        return naff.OptionTypes.ROLE
    if t == float:
        return naff.OptionTypes.NUMBER
    if t == naff.Attachment:
        return naff.OptionTypes.ATTACHMENT

    if typing.get_origin(t) in {typing.Union, types.UnionType}:
        args = typing.get_args(t)
        if (
            len(args) in {2, 3}
            and issubclass(args[0], (naff.BaseUser, naff.BaseChannel))
            and issubclass(args[1], (naff.BaseUser, naff.BaseChannel))
            and args[0] != args[1]
        ):
            return naff.OptionTypes.MENTIONABLE

    raise ValueError("Invalid type provided.")


@attrs.define(kw_only=True)
class ParamInfo(naff.SlashCommandOption):
    name: naff.LocalisedName | str | None = attrs.field(
        default=None, converter=naff.LocalisedName.converter
    )
    type: "naff.OptionTypes | None" = attrs.field(default=None)
    converter: typing.Optional[naff.Converter | typing.Callable] = attrs.field(
        default=None,
    )
    default: typing.Any = attrs.field(default=naff.MISSING)

    def __attrs_post_init__(self):
        if self.converter and self.type is None:
            self.type = naff.OptionTypes.STRING

        if self.default is not naff.MISSING:
            self.required = False

        if not self.required and self.default is naff.MISSING:
            raise ValueError(
                f"{self.name} is not required, but no default has been set!"
            )

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
    description: naff.LocalisedDesc | str = "No Description Set",
    *,
    name: naff.LocalisedName | str | None = None,
    type: "typing.Optional[naff.OptionTypes | type]" = None,
    converter: typing.Optional[naff.Converter | typing.Callable] = None,
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
