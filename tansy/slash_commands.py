import inspect
import types
import typing

import attrs
import naff

from . import slash_param


def _convert_to_bool(argument: str) -> bool:
    lowered = argument.lower()
    if lowered in {"yes", "y", "true", "t", "1", "enable", "on"}:
        return True
    elif lowered in {"no", "n", "false", "f", "0", "disable", "off"}:
        return False
    else:
        raise naff.errors.BadArgument(f"{argument} is not a recognised boolean option.")


def _get_from_anno_type(anno: typing.Annotated) -> typing.Any:
    """
    Handles dealing with Annotated annotations, getting their (first) type annotation.
    This allows correct type hinting with, say, Converters, for example.
    """
    # this is treated how it usually is during runtime
    # the first argument is ignored and the rest is treated as is

    args = typing.get_args(anno)[1:]
    return args[0]


def _get_converter_function(
    anno: type[naff.Converter] | naff.Converter, name: str
) -> typing.Callable[[naff.InteractionContext, str], typing.Any]:
    num_params = len(inspect.signature(anno.convert).parameters.values())

    # if we have three parameters for the function, it's likely it has a self parameter
    # so we need to get rid of it by initing - typehinting hates this, btw!
    # the below line will error out if we aren't supposed to init it, so that works out
    actual_anno: naff.Converter = anno() if num_params == 3 else anno  # type: ignore
    # we can only get to this point while having three params if we successfully inited
    if num_params == 3:
        num_params -= 1

    if num_params != 2:
        ValueError(
            f"{naff.utils.get_object_name(anno)} for {name} is invalid: converters"
            " must have exactly 2 arguments."
        )

    return actual_anno.convert


def _get_converter(anno: type, name: str) -> typing.Callable[[naff.InteractionContext, str], typing.Any]:  # type: ignore
    if typing.get_origin(anno) == typing.Annotated:
        anno = _get_from_anno_type(anno)

    if isinstance(anno, naff.Converter):
        return _get_converter_function(anno, name)
    elif inspect.isfunction(anno):
        num_params = len(inspect.signature(anno).parameters.values())
        match num_params:
            case 2:
                return lambda ctx, arg: anno(ctx, arg)
            case 1:
                return lambda ctx, arg: anno(arg)
            case 0:
                return lambda ctx, arg: anno()
            case _:
                ValueError(
                    f"{naff.utils.get_object_name(anno)} for {name} has more than 2"
                    " arguments, which is unsupported."
                )
    elif anno == bool:
        return lambda ctx, arg: _convert_to_bool(arg)
    elif anno == inspect._empty:
        return lambda ctx, arg: str(arg)
    else:
        return lambda ctx, arg: anno(arg)


async def _convert(
    param: "TansySlashCommandParameter",
    ctx: naff.InteractionContext,
    arg: typing.Any,
) -> typing.Any:
    converted = naff.MISSING
    for converter in param.converters:
        try:
            converted = await naff.utils.maybe_coroutine(converter, ctx, arg)
            break
        except Exception as e:
            if not param.union and not param.optional:
                if isinstance(e, naff.errors.BadArgument):
                    raise
                raise naff.errors.BadArgument(str(e)) from e

    if converted == naff.MISSING:
        if param.optional:
            converted = param.default
        else:
            union_types = typing.get_args(param.type)
            union_names = tuple(naff.utils.get_object_name(t) for t in union_types)
            union_types_str = ", ".join(union_names[:-1]) + f", or {union_names[-1]}"
            raise naff.errors.BadArgument(
                f'Could not convert "{arg}" into {union_types_str}.'
            )

    return converted


@attrs.define(slots=True)
class TansySlashCommandParameter:
    """An object representing parameters in a command."""

    name: str = attrs.field(default=None)
    default: typing.Optional[typing.Any] = attrs.field(default=None)
    type: typing.Type = attrs.field(default=None)
    converters: list[
        typing.Callable[[naff.InteractionContext, typing.Any], typing.Any]
    ] = attrs.field(factory=list)
    union: bool = attrs.field(default=False)

    @property
    def optional(self) -> bool:
        return self.default != naff.MISSING


@naff.utils.define()
class TansySlashCommand(naff.SlashCommand):
    parameters: dict[str, TansySlashCommandParameter] = attrs.field(
        factory=dict, metadata=naff.utils.no_export_meta
    )

    def __attrs_post_init__(self) -> None:
        if self.callback is not None:
            self.options = []

            params = naff.utils.get_parameters(self.callback)
            for name, param in list(params.items())[1:]:
                cmd_param = TansySlashCommandParameter()

                if isinstance(param.default, slash_param.ParamInfo):
                    option = param.default.generate_option()
                else:
                    option_type = slash_param.get_option(param.annotation)
                    option = naff.SlashCommandOption(name=name, type=option_type)

                cmd_param.name = option.name.default or name
                option.name = cmd_param.name

                if option.type == naff.MISSING:
                    option.type = slash_param.get_option(param.annotation)

                if (
                    isinstance(param.default, slash_param.ParamInfo)
                    and param.default.default is not naff.MISSING
                ):
                    cmd_param.default = param.default.default
                elif param.default is not param.empty:
                    cmd_param.default = param.default
                else:
                    cmd_param.default = naff.MISSING

                if option.type == naff.OptionTypes.STRING:
                    if (
                        isinstance(param.default, slash_param.ParamInfo)
                        and param.default.converter
                    ):
                        cmd_param.type = anno = param.default.converter
                    else:
                        cmd_param.type = anno = param.annotation

                    anno: type

                    if typing.get_origin(anno) in {typing.Union, types.UnionType}:
                        cmd_param.union = True
                        for arg in typing.get_args(anno):
                            if arg != types.NoneType:
                                converter = _get_converter(arg, name)
                                cmd_param.converters.append(converter)
                            elif not cmd_param.optional:  # d.py-like behavior
                                cmd_param.default = None
                    else:
                        converter = _get_converter(anno, name)
                        cmd_param.converters.append(converter)
                else:
                    cmd_param.converters = [lambda ctx, arg: arg]

                self.options.append(option)
                self.parameters[name] = cmd_param

            if hasattr(self.callback, "permissions"):
                self.permissions = self.callback.permissions
        naff.BaseCommand.__attrs_post_init__(self)

    async def call_callback(
        self, callback: typing.Callable, ctx: naff.InteractionContext
    ) -> None:
        """
        Runs the callback of this command.
        Args:
            callback (Callable: The callback to run. This is provided for compatibility with naff.
            ctx (naff.InteractionContext): The context to use for this command.
        """
        if len(self.parameters) == 0:
            return await callback(ctx)

        new_kwargs = {}

        for key, value in ctx.kwargs.items():
            param = self.parameters[key]
            converted = await _convert(param, ctx, value)
            new_kwargs[key] = converted

        not_found_param = tuple(
            (k, v) for k, v in self.parameters.items() if k not in new_kwargs
        )
        for key, value in not_found_param:
            new_kwargs[key] = value.default

        return await callback(ctx, *new_kwargs)


def slash_command(
    name: str | naff.LocalisedName,
    *,
    description: naff.Absent[str | naff.LocalisedDesc] = naff.MISSING,
    scopes: naff.Absent[typing.List["naff.Snowflake_Type"]] = naff.MISSING,
    options: typing.Optional[
        typing.List[typing.Union[naff.SlashCommandOption, typing.Dict]]
    ] = None,
    default_member_permissions: typing.Optional["naff.Permissions"] = None,
    dm_permission: bool = True,
    sub_cmd_name: str | naff.LocalisedName = None,
    group_name: str | naff.LocalisedName = None,
    sub_cmd_description: str | naff.LocalisedDesc = "No Description Set",
    group_description: str | naff.LocalisedDesc = "No Description Set",
    nsfw: bool = False,
) -> typing.Callable[[typing.Callable[..., typing.Coroutine]], TansySlashCommand]:
    """
    A decorator to declare a coroutine as a slash command.
    note:
        While the base and group descriptions arent visible in the discord client, currently.
        We strongly advise defining them anyway, if you're using subcommands, as Discord has said they will be visible in
        one of the future ui updates.
    Args:
        name: 1-32 character name of the command
        description: 1-100 character description of the command
        scopes: The scope this command exists within
        options: The parameters for the command, max 25
        default_member_permissions: What permissions members need to have by default to use this command.
        dm_permission: Should this command be available in DMs.
        sub_cmd_name: 1-32 character name of the subcommand
        sub_cmd_description: 1-100 character description of the subcommand
        group_name: 1-32 character name of the group
        group_description: 1-100 character description of the group
    Returns:
        SlashCommand Object
    """

    def wrapper(func: typing.Callable[..., typing.Coroutine]) -> TansySlashCommand:
        if not inspect.iscoroutinefunction(func):
            raise ValueError("Commands must be coroutines")

        perm = default_member_permissions
        if hasattr(func, "default_member_permissions"):
            if perm:
                perm = perm | func.default_member_permissions
            else:
                perm = func.default_member_permissions

        _description = description
        if _description is naff.MISSING:
            _description = func.__doc__ or "No Description Set"

        return TansySlashCommand(
            name=name,
            group_name=group_name,
            group_description=group_description,
            sub_cmd_name=sub_cmd_name,
            sub_cmd_description=sub_cmd_description,
            description=_description,
            scopes=scopes or [naff.const.GLOBAL_SCOPE],
            default_member_permissions=perm,
            dm_permission=dm_permission,
            nsfw=nsfw,
            callback=func,
            options=options,
        )

    return wrapper
