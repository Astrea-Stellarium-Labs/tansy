import inspect
import types
import typing

import attrs
import dis_snek
from dis_snek.client.utils.misc_utils import get_object_name
from dis_snek.client.utils.misc_utils import get_parameters
from dis_snek.client.utils.misc_utils import maybe_coroutine


def _convert_to_bool(argument: str) -> bool:
    lowered = argument.lower()
    if lowered in {"yes", "y", "true", "t", "1", "enable", "on"}:
        return True
    elif lowered in {"no", "n", "false", "f", "0", "disable", "off"}:
        return False
    else:
        raise dis_snek.errors.BadArgument(
            f"{argument} is not a recognised boolean option."
        )


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
    anno: type[dis_snek.Converter] | dis_snek.Converter, name: str
) -> typing.Callable[[dis_snek.InteractionContext, str], typing.Any]:
    num_params = len(inspect.signature(anno.convert).parameters.values())

    # if we have three parameters for the function, it's likely it has a self parameter
    # so we need to get rid of it by initing - typehinting hates this, btw!
    # the below line will error out if we aren't supposed to init it, so that works out
    actual_anno: dis_snek.Converter = anno() if num_params == 3 else anno  # type: ignore
    # we can only get to this point while having three params if we successfully inited
    if num_params == 3:
        num_params -= 1

    if num_params != 2:
        ValueError(
            f"{get_object_name(anno)} for {name} is invalid: converters must have"
            " exactly 2 arguments."
        )

    return actual_anno.convert


def _get_converter(anno: type, name: str) -> typing.Callable[[dis_snek.InteractionContext, str], typing.Any]:  # type: ignore
    if typing.get_origin(anno) == typing.Annotated:
        anno = _get_from_anno_type(anno)

    if isinstance(anno, dis_snek.Converter):
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
                    f"{get_object_name(anno)} for {name} has more than 2 arguments,"
                    " which is unsupported."
                )
    elif anno == bool:
        return lambda ctx, arg: _convert_to_bool(arg)
    elif anno == inspect._empty:
        return lambda ctx, arg: str(arg)
    else:
        return lambda ctx, arg: anno(arg)


async def _convert(
    param: "TansySlashCommandParameter",
    ctx: dis_snek.InteractionContext,
    arg: typing.Any,
) -> tuple[typing.Any, bool]:
    converted = dis_snek.MISSING
    for converter in param.converters:
        try:
            converted = await maybe_coroutine(converter, ctx, arg)
            break
        except Exception as e:
            if not param.union and not param.optional:
                if isinstance(e, dis_snek.errors.BadArgument):
                    raise
                raise dis_snek.errors.BadArgument(str(e)) from e

    used_default = False
    if converted == dis_snek.MISSING:
        if param.optional:
            converted = param.default
            used_default = True
        else:
            union_types = typing.get_args(param.type)
            union_names = tuple(get_object_name(t) for t in union_types)
            union_types_str = ", ".join(union_names[:-1]) + f", or {union_names[-1]}"
            raise dis_snek.errors.BadArgument(
                f'Could not convert "{arg}" into {union_types_str}.'
            )

    return converted, used_default


@attrs.define(slots=True)
class TansySlashCommandParameter:
    """An object representing parameters in a command."""

    name: str = attrs.field(default=None)
    default: typing.Optional[typing.Any] = attrs.field(default=None)
    type: type = attrs.field(default=None)
    converters: list[
        typing.Callable[[dis_snek.InteractionContext, typing.Any], typing.Any]
    ] = attrs.field(factory=list)
    union: bool = attrs.field(default=False)

    @property
    def optional(self) -> bool:
        return self.default != dis_snek.MISSING


class TansySlashCommand(dis_snek.SlashCommand):
    parameters: dict[str, TansySlashCommandParameter] = attrs.field(factory=dict)

    def __attrs_post_init__(self) -> None:
        if self.callback is not None:
            params = get_parameters(self.callback)
            for name, param in params.items():
                cmd_param = TansySlashCommandParameter()
                cmd_param.name = name
                cmd_param.default = (
                    param.default
                    if param.default is not param.empty
                    else dis_snek.MISSING
                )

                cmd_param.type = anno = param.annotation

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

                self.parameters[name] = cmd_param

            if hasattr(self.callback, "options"):
                if not self.options:
                    self.options = []
                self.options += self.callback.options

            if hasattr(self.callback, "permissions"):
                self.permissions = self.callback.permissions
        dis_snek.BaseCommand.__attrs_post_init__(self)

    async def call_callback(
        self, callback: typing.Callable, ctx: dis_snek.InteractionContext
    ) -> None:
        """
        Runs the callback of this command.
        Args:
            callback (Callable: The callback to run. This is provided for compatibility with dis_snek.
            ctx (dis_snek.InteractionContext): The context to use for this command.
        """
        # sourcery skip: remove-empty-nested-block, remove-redundant-if, remove-unnecessary-else
        if len(self.parameters) == 0:
            return await callback(ctx)
        else:
            param_list = list(self.parameters.values())
            param_index = 0
            new_args = []

            for arg in ctx.args:
                while param_index < len(param_list):
                    param = param_list[param_index]

                    converted, used_default = await _convert(param, ctx, arg)
                    new_args.append(converted)
                    param_index += 1

                    if not used_default:
                        break

            if param_index < len(self.parameters):
                new_args.extend(param.default for param in param_list[param_index:])

            return await callback(ctx, *new_args)
