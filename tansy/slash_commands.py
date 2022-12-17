import asyncio
import functools
import inspect
import types
import typing

import attrs
import naff

from . import slash_param
from . import utils


def _get_converter(anno: type, name: str):
    if typing.get_origin(anno) == typing.Annotated:
        anno = utils.get_from_anno_type(anno)

    if isinstance(anno, naff.Converter):
        return naff.BaseCommand._get_converter_function(anno, name)
    elif inspect.isroutine(anno):
        num_params = len(inspect.signature(anno).parameters.values())
        match num_params:
            case 2:
                return anno
            case 1:

                async def _one_arg_convert(_, arg) -> typing.Any:
                    return await naff.utils.maybe_coroutine(anno, arg)

                return _one_arg_convert
            case 0:
                raise ValueError(
                    f"{naff.utils.get_object_name(anno)} for {name} has 0"
                    " arguments, which is unsupported."
                )
            case _:
                raise ValueError(
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
                        option_type = utils.get_option(param.annotation)
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
                        option.type = utils.get_option(param.annotation)
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

                # what we're checking here is:
                # - if we don't already have a default
                # - if the user didn't already specify a type in
                #   param_info that would indicate if its optional or not
                # - if the annotation is marked as optional
                # if so, we want to make the option not required, and the default be None
                if (
                    cmd_param.default is naff.MISSING
                    and (not param_info or not param_info._user_provided_type)
                    and utils.is_optional(param.annotation)
                ):
                    option.required = False
                    cmd_param.default = None

                if (
                    param_info
                    and option.type == naff.OptionTypes.CHANNEL
                    and not option.channel_types
                ):
                    option.channel_types = utils.resolve_channel_types(param.annotation)  # type: ignore

                if param_info and param_info.converter:
                    if convert_func := _get_converter(param_info.converter, param.name):
                        cmd_param.converter = convert_func
                    else:
                        raise ValueError(
                            f"The converter for {param.name} is invalid. Please make"
                            " sure it is either a Converter-like class or a function."
                        )
                elif converter := _get_converter(param.annotation, param.name):
                    cmd_param.converter = converter

                # we bypassed validation earlier, so let's make sure everything's okay
                # since we got the final option stuff now
                attrs.validate(option)  # type: ignore
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

    def group(
        self, name: str = None, description: str = "No Description Set"
    ) -> "TansySlashCommand":
        return TansySlashCommand(
            name=self.name,
            description=self.description,
            group_name=name,
            group_description=description,
            scopes=self.scopes,
        )

    def subcommand(
        self,
        sub_cmd_name: naff.LocalisedName | str,
        group_name: naff.LocalisedName | str = None,
        sub_cmd_description: naff.Absent[naff.LocalisedDesc | str] = naff.MISSING,
        group_description: naff.Absent[naff.LocalisedDesc | str] = naff.MISSING,
        nsfw: bool = False,
    ) -> typing.Callable[..., "TansySlashCommand"]:
        def wrapper(
            call: typing.Callable[..., typing.Coroutine]
        ) -> "TansySlashCommand":
            nonlocal sub_cmd_description

            if not asyncio.iscoroutinefunction(call):
                raise TypeError("Subcommand must be coroutine")

            if sub_cmd_description is naff.MISSING:
                sub_cmd_description = call.__doc__ or "No Description Set"

            return TansySlashCommand(
                name=self.name,
                description=self.description,
                group_name=group_name or self.group_name,
                group_description=group_description or self.group_description,
                sub_cmd_name=sub_cmd_name,
                sub_cmd_description=sub_cmd_description,
                default_member_permissions=self.default_member_permissions,
                dm_permission=self.dm_permission,
                callback=call,
                scopes=self.scopes,
                nsfw=nsfw,
            )

        return wrapper


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
