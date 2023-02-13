import inspect
import typing

import interactions as ipy

from .slash_commands import TansySlashCommand
from .slash_param import ParamInfo


__all__ = ("class_slash_command", "class_subcommand")


def _wrap_callback(the_cls: type):
    if "." in the_cls.__qualname__:
        # we need to do the qualname hack again to detect if this is in an extension
        # or not
        # we don't really care about self in this case, but what we're doing is hoping
        # that ipys extension binder/wrapper wraps over self and not ctx, which makes the
        # final result as expected correct
        async def _call_self(self, ctx, **kwargs):
            the_class = the_cls()
            for name, value in kwargs.items():
                the_class.__setattr__(name, value)

            return await the_class.callback(ctx)

        return _call_self
    else:

        async def _call(ctx, **kwargs):
            the_class = the_cls()
            for name, value in kwargs.items():
                the_class.__setattr__(name, value)

            return await the_class.callback(ctx)

        return _call


def class_slash_command(
    name: str | ipy.LocalisedName,
    *,
    description: ipy.Absent[str | ipy.LocalisedDesc] = ipy.MISSING,
    scopes: ipy.Absent[typing.List["ipy.Snowflake_Type"]] = ipy.MISSING,
    default_member_permissions: typing.Optional["ipy.Permissions"] = None,
    dm_permission: bool = True,
    sub_cmd_name: str | ipy.LocalisedName = None,
    group_name: str | ipy.LocalisedName = None,
    sub_cmd_description: str | ipy.LocalisedDesc = "No Description Set",
    group_description: str | ipy.LocalisedDesc = "No Description Set",
    nsfw: bool = False,
):
    """
    A decorator to declare a class as a Tansy slash command.
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

    def process(the_cls: type):
        if not inspect.isclass(the_cls):
            raise TypeError("This is not a class.")

        try:
            the_cls()
        except TypeError:
            raise TypeError(
                "The class's init must not have any required parameters."
            ) from None

        if not hasattr(the_cls, "callback") or not inspect.iscoroutinefunction(
            the_cls.callback
        ):
            raise TypeError(
                'You need an asynchronous callback called "callback" to call.'
            )

        perm = default_member_permissions

        _description = description
        if _description is ipy.MISSING:
            _description = the_cls.__doc__ or "No Description Set"

        parameters: list[inspect.Parameter] = []

        annotations = inspect.get_annotations(the_cls)

        for param_name, default in the_cls.__dict__.items():
            if not isinstance(default, ParamInfo):
                continue

            param = inspect.Parameter(
                name=param_name,
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=default,
                annotation=annotations.get(param_name, inspect._empty),
            )
            parameters.append(param)

        sig = inspect.Signature(parameters=parameters)

        return TansySlashCommand(
            name=name,
            group_name=group_name,
            group_description=group_description,
            sub_cmd_name=sub_cmd_name,
            sub_cmd_description=sub_cmd_description,
            description=_description,
            scopes=scopes or [ipy.const.GLOBAL_SCOPE],
            default_member_permissions=perm,
            dm_permission=dm_permission,
            nsfw=nsfw,
            callback=_wrap_callback(the_cls),
            inspect_signature=sig,  # type: ignore
        )

    return process


def class_subcommand(
    base: str | ipy.LocalisedName,
    *,
    subcommand_group: typing.Optional[str | ipy.LocalisedName] = None,
    name: typing.Optional[str | ipy.LocalisedName] = None,
    description: ipy.Absent[str | ipy.LocalisedDesc] = ipy.MISSING,
    base_description: typing.Optional[str | ipy.LocalisedDesc] = None,
    base_desc: typing.Optional[str | ipy.LocalisedDesc] = None,
    base_default_member_permissions: typing.Optional["ipy.Permissions"] = None,
    base_dm_permission: bool = True,
    subcommand_group_description: typing.Optional[str | ipy.LocalisedDesc] = None,
    sub_group_desc: typing.Optional[str | ipy.LocalisedDesc] = None,
    scopes: typing.List["ipy.Snowflake_Type"] = None,
    nsfw: bool = False,
) -> typing.Callable[[type], TansySlashCommand]:
    """
    A decorator specifically tailored for creating a Tansy subcommand from a class.
    Args:
        base: The name of the base command
        subcommand_group: The name of the subcommand group, if any.
        name: The name of the subcommand, defaults to the name of the coroutine.
        description: The description of the subcommand
        base_description: The description of the base command
        base_desc: An alias of `base_description`
        base_default_member_permissions: What permissions members need to have by default to use this command.
        base_dm_permission: Should this command be available in DMs.
        subcommand_group_description: Description of the subcommand group
        sub_group_desc: An alias for `subcommand_group_description`
        scopes: The scopes of which this command is available, defaults to GLOBAL_SCOPE
        nsfw: This command should only work in NSFW channels
    Returns:
        A TansySlashCommand object
    """

    def wrapper(the_cls: type) -> TansySlashCommand:
        if not inspect.isclass(the_cls):
            raise TypeError("This is not a class.")

        try:
            the_cls()
        except TypeError:
            raise TypeError("The class's init must not have any required parameters.")

        if not hasattr(the_cls, "callback") or not inspect.iscoroutinefunction(
            the_cls.callback
        ):
            raise TypeError(
                'You need an asynchronous callback called "callback" to call.'
            )

        _description = description
        if _description is ipy.MISSING:
            _description = the_cls.__doc__ or "No Description Set"

        parameters: list[inspect.Parameter] = []

        annotations = inspect.get_annotations(the_cls)

        for param_name, default in the_cls.__dict__.items():
            if not isinstance(default, ParamInfo):
                continue

            param = inspect.Parameter(
                name=param_name,
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=default,
                annotation=annotations.get(param_name, inspect._empty),
            )
            parameters.append(param)

        sig = inspect.Signature(parameters=parameters)

        cmd = TansySlashCommand(
            name=base,
            description=(base_description or base_desc) or "No Description Set",
            group_name=subcommand_group,
            group_description=(subcommand_group_description or sub_group_desc)
            or "No Description Set",
            sub_cmd_name=name,
            sub_cmd_description=_description,
            default_member_permissions=base_default_member_permissions,
            dm_permission=base_dm_permission,
            scopes=scopes or [ipy.const.GLOBAL_SCOPE],
            nsfw=nsfw,
            callback=_wrap_callback(the_cls),
            inspect_signature=sig,  # type: ignore
        )
        return cmd

    return wrapper
