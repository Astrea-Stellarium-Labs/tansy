import functools
import inspect
import typing

import attrs
import naff

from ..utils import filter_extras
from ..utils import is_optional


@attrs.define()
class BaseCommandParameter:
    name: str = attrs.field()
    type: typing.Any = attrs.field()
    kind: inspect._ParameterKind = attrs.field()
    default: typing.Any = attrs.field(default=naff.MISSING)
    converter: typing.Optional[typing.Callable] = attrs.field(default=None)


def _get_from_annotated(annotated: typing.Annotated):
    args = typing.get_args(annotated)
    return next((a for a in args if isinstance(a, naff.Converter)), None)


@attrs.define(eq=False, order=False, hash=False, kw_only=True)
class BetterBaseCommand(naff.BaseCommand):
    parameters: dict[str, BaseCommandParameter] = attrs.field(
        repr=False, factory=dict, metadata=naff.utils.no_export_meta
    )
    _uses_arg: bool = attrs.field(
        repr=False, default=False, metadata=naff.utils.no_export_meta
    )

    def __attrs_post_init__(self):
        self.parameters = {}
        self._uses_arg = False

        naff.BaseCommand.__attrs_post_init__(self)

        if self.callback is not None and not self.parameters:
            if "." in self.callback.__qualname__:
                callback = functools.partial(self.callback, None, None)
            else:
                callback = functools.partial(self.callback, None)

            sig_parameters = inspect.signature(callback).parameters

            for param in sig_parameters.values():
                if param.kind == inspect._ParameterKind.VAR_POSITIONAL:
                    self._uses_arg = True
                    continue

                if param.kind == inspect._ParameterKind.VAR_KEYWORD:
                    self._uses_arg = False
                    continue

                our_param = BaseCommandParameter(
                    param.name, param.annotation, param.kind
                )
                our_param.default = (
                    param.default
                    if param.default is not inspect._empty
                    else naff.MISSING
                )

                if param.annotation is not inspect._empty:
                    anno = param.annotation
                    converter = None

                    if is_optional(anno):
                        # base commands support annotations in a different way,
                        # so we don't want to filter them out like how tansy does
                        # however, we do want to get the non-optional stuff out of
                        # this anno, so filter_extras is still useful
                        anno = filter_extras(anno)

                    if isinstance(anno, naff.Converter):
                        converter = anno
                    elif typing.get_origin(anno) == typing.Annotated:
                        converter = _get_from_annotated(anno)

                    if converter:
                        our_param.converter = self._get_converter_function(
                            converter, our_param.name
                        )

                self.parameters[param.name] = our_param

    async def call_callback(self, callback: typing.Callable, ctx: naff.Context) -> None:
        if not self.parameters:
            # to keep compat with normal BaseCommand
            return await self.call_with_binding(callback, ctx)

        kwargs_copy = ctx.kwargs.copy()

        new_args = []
        new_kwargs = {}

        for name in ctx.kwargs.keys():
            value = kwargs_copy.pop(name)
            param = self.parameters[name]

            if converter := param.converter:
                value = await naff.utils.maybe_coroutine(converter, ctx, value)

            if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                new_args.append(value)
            else:
                new_kwargs[name] = value

        if kwargs_copy:
            if self._uses_arg:
                new_args.extend(kwargs_copy.values())
            else:
                new_kwargs |= kwargs_copy

        return await self.call_with_binding(callback, ctx, *new_args, **new_kwargs)


def interaction_cmd_post_init(self: naff.InteractionCommand):
    if self.callback is not None and hasattr(self.callback, "auto_defer"):
        self.auto_defer = self.callback.auto_defer

    BetterBaseCommand.__attrs_post_init__(self)


def patch():
    naff.InteractionCommand.__attrs_post_init__ = interaction_cmd_post_init
    naff.InteractionCommand.call_callback = BetterBaseCommand.call_callback
