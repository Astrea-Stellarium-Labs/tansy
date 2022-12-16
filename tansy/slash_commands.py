import functools
import inspect
import typing

import attrs
import naff

from . import slash_param


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


def _get_converter(anno: type, name: str):
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
    else:
        return None


@attrs.define(slots=True)
class TansySlashCommandParameter:
    """An object representing parameters in a command."""

    name: str = attrs.field(default=None)
    argument_name: str = attrs.field(default=None)
    default: naff.Absent[typing.Any] = attrs.field(default=naff.MISSING)
    type: typing.Type = attrs.field(default=None)
    converter: typing.Optional[typing.Callable] = attrs.field(default=None)

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

            # qualname hack, oh how i've not missed you
            if "." in self.callback.__qualname__:
                callback = functools.partial(self.callback, None, None)
            else:
                callback = functools.partial(self.callback, None)

            params = naff.utils.get_parameters(callback)
            for name, param in list(params.items()):
                if param.kind not in [
                    param.POSITIONAL_OR_KEYWORD,
                    param.KEYWORD_ONLY,
                ]:
                    raise ValueError(
                        "All parameters must be able to be used via keyword arguments."
                    )

                cmd_param = TansySlashCommandParameter()
                param_info = (
                    param.default
                    if isinstance(param.default, slash_param.ParamInfo)
                    else None
                )

                if param_info:
                    option = param_info.generate_option()
                else:
                    try:
                        option_type = slash_param.get_option(param.annotation)
                    except ValueError:
                        raise ValueError(
                            f"Invalid/no provided type for {name}"
                        ) from None
                    option = naff.SlashCommandOption(name=name, type=option_type)

                cmd_param.name = str(option.name) if option.name else name
                cmd_param.argument_name = name
                option.name = option.name or naff.LocalisedName.converter(
                    cmd_param.name
                )

                if option.type is None:
                    try:
                        option.type = slash_param.get_option(param.annotation)
                    except ValueError:
                        raise ValueError(
                            f"Invalid/no provided type for {name}"
                        ) from None

                if param_info:
                    cmd_param.default = param_info.default
                elif param.default is not param.empty:
                    cmd_param.default = param.default
                else:
                    cmd_param.default = naff.MISSING

                if param_info and param_info.converter:
                    cmd_param.converter = _get_converter_function(
                        param_info.converter, param.name
                    )
                elif converter := _get_converter(param.annotation, param.name):
                    cmd_param.converter = converter

                self.options.append(option)
                self.parameters[cmd_param.name] = cmd_param

            if hasattr(self.callback, "auto_defer"):
                self.auto_defer = self.callback.auto_defer
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
            if param.converter:
                converted = await naff.utils.maybe_coroutine(
                    param.converter, ctx, value
                )
            else:
                converted = value
            new_kwargs[param.argument_name] = converted

        not_found_param = tuple(
            v for v in self.parameters.values() if v.argument_name not in new_kwargs
        )
        for value in not_found_param:
            new_kwargs[value.argument_name] = value.default

        return await callback(ctx, **new_kwargs)


def slash_command(
    name: str | naff.LocalisedName,
    *,
    description: naff.Absent[str | naff.LocalisedDesc] = naff.MISSING,
    scopes: naff.Absent[typing.List["naff.Snowflake_Type"]] = naff.MISSING,
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
        default_member_permissions: What permissions members need to have by default to use this command.
        dm_permission: Should this command be available in DMs.
        sub_cmd_name: 1-32 character name of the subcommand
        sub_cmd_description: 1-100 character description of the subcommand
        group_name: 1-32 character name of the group
        group_description: 1-100 character description of the group
        nsfw: This command should only work in NSFW channels
    Returns:
        TansySlashCommand Object
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
        )

    return wrapper
