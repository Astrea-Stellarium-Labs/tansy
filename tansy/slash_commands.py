import asyncio
import copy
import inspect
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
        if hasattr(anno, "__code__"):
            num_params: int = anno.__code__.co_argcount
        else:
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
                    " positional arguments, which is unsupported."
                )
            case _:
                raise ValueError(
                    f"{naff.utils.get_object_name(anno)} for {name} has more than 2"
                    " positional arguments, which is unsupported."
                )
    else:
        return None


_C = typing.TypeVar("_C", bound=typing.Callable)


def _overwrite_defaults(
    func: _C, defaults: dict[str, typing.Any], parameters: dict[str, inspect.Parameter]
) -> _C:
    """
    A cursed piece of code that overrides the defaults in a function with the defaults
    provided, and returns the result of that. The defaults provided are assumed to be
    in the order that appear in the function. To be somewhat safe, the edited function
    is a shallow copy of the old function.

    The code here isn't very complex, and you can likely understand most of this from
    a glance, but this is a BAD idea, and you shouldn't do or use this as a beginner.
    Editing the raw defaults and kwdefaults can lead to unintended behavior,
    and touching magic properties like these are a big no-no in Python.
    Use `functools.partial` if you want to set your own defaults for a function
    programmatically most of the time.

    So why did I do it anyway?
    - Speed. Using `functools.partial` adds a pretty decent amount of overhead, especially
      if it has to combine two kwargs together. In Tansy, doing this instead of adding
      extra code in `call_callable` to insert defaults if they are missing adds an even
      greater speed benefit, as calculations for what is missing do not need to be done.

    - Compatibility and ease-of-use. If you're using the raw callback of commands for something,
      like how I do sometimes, you don't want to be tripped up by putting an argument as
      a positional argument instead of a keyword argument and suddenly getting an error,
      even if that would fine in the raw function itself.

    For example, this would occur:
    ```python
    async def original_func(arg: str):
        print(arg)

    defaults = {"arg": "hi!"}
    new_func = partial(original_func, **defaults)

    # would work fine in original_func, but python thinks that two values are being passed
    # for "arg" because kwarg vs. positional, causing an error that would be hard to understand
    # as an end-user
    await new_func("hey!")
    ```

    Technically, it is possible to make a wrapper around a function that would handle those
    cases just fine, but that adds a lot of overhead, more than just using `partial` or doing this.
    """
    func_copy = copy.copy(func)
    old_kwarg_defaults = func.__kwdefaults__ or {}

    new_defaults = []
    new_kwarg_defaults = {}

    for name, default in defaults.items():
        if (
            old_kwarg_defaults.get(name)
            or parameters[name].kind == inspect._ParameterKind.KEYWORD_ONLY
        ):
            new_kwarg_defaults[name] = default
        else:
            new_defaults.append(default)

    func_copy.__defaults__ = tuple(new_defaults) if new_defaults else None
    func_copy.__kwdefaults__ = new_kwarg_defaults or None

    return func_copy


@attrs.define(slots=True)
class TansySlashCommandParameter:
    """An object representing parameters in a command."""

    name: str = attrs.field(default=None)
    argument_name: str = attrs.field(default=None)
    default: typing.Any = attrs.field(default=naff.MISSING)
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
            signature_parameters = tuple(
                inspect.signature(self.callback).parameters.items()
            )

            self.options = []

            # qualname hack, oh how i've not missed you
            # in case you forgot - qualname contains the full name of a function,
            # including the class it's in
            # it just so happens that functions in a class with be like Class.func,
            # and functions outside of one will be like func
            # simply put, checking if there's a dot in the qualname basically
            # also checks if it's in a class (or module, but shh) -
            # if it's in a class, we're assuming there's a self in there (not always
            # true, but naff relies on that assumption anyways),
            # which we want to ignore
            # we also want to ignore ctx too
            starting_index = 2 if "." in self.callback.__qualname__ else 1

            for name, param in signature_parameters[starting_index:]:
                if param.kind == param.VAR_KEYWORD:
                    # something like **kwargs, that's fine so let it pass
                    continue

                if param.kind not in {
                    param.POSITIONAL_OR_KEYWORD,
                    param.KEYWORD_ONLY,
                }:
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
                    option.required = False
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

            # make sure the options arent in an invalid order -
            # both to safeguard against invalid slash commands and because
            # we rely on optional arguments being after required arguments right after this
            attrs.validate(self)  # type: ignore

            if self.parameters:
                # i wont lie to you - what we're about to do is probably the
                # most disgusting, hacky thing ive done in python, but there's a good
                # reason for it
                #
                # you know how Option() exists in this lib? you know how you have to
                # do arg: type = Option() in order to define an option usually when
                # using tansy commands?
                # well, now Option() is the default of arg in the command, which
                # means if no value is provided for arg while using the raw callback,
                # instead of erroring out or receiving the value specified in default=X
                # (or None, if you used Optional and didn't explictly set a default value),
                # the function will instead just pass in the ParamInfo generated by Option(),
                # which is unintuitive and would result in a lot of bugs
                #
                # to prevent this, we overwrite the defaults in the function with ones
                # that make more sense considering tansy's features
                # explainations about the cursed _overwrite_defaults can be found
                # in the function itself

                defaults = {
                    p.argument_name: p.default
                    for p in self.parameters.values()
                    if p.optional
                }
                self.callback = _overwrite_defaults(
                    self.callback, defaults, dict(signature_parameters)
                )

            # since we're overriding __attrs_post_init__, we need to make sure
            # we do this
            if hasattr(self.callback, "auto_defer"):
                self.auto_defer = self.callback.auto_defer

        # make sure checks and the like go through
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
        if not self.parameters:
            return await callback(ctx)

        new_kwargs = {}

        for key, value in ctx.kwargs.items():
            param = self.parameters.get(key)
            if not param:
                # hopefully you have **kwargs
                new_kwargs[key] = value
                continue

            if param.converter:
                converted = await naff.utils.maybe_coroutine(
                    param.converter, ctx, value
                )
            else:
                converted = value
            new_kwargs[param.argument_name] = converted

        return await self.call_with_binding(callback, ctx, **new_kwargs)

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


def tansy_slash_command(
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
    A decorator to declare a coroutine as a Tansy slash command.
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


SlashCommand = TansySlashCommand
slash_command = tansy_slash_command
