import functools
import typing

import attrs
import naff


@attrs.define(
    eq=False, order=False, hash=False, kw_only=False, on_setattr=attrs.setters.NO_OP
)
class FasterEmbed(naff.Embed):
    @functools.lru_cache(maxsize=32)
    def __len__(self):
        # admittedly, the base lib's len is already pretty fast -
        # this doesn't speed it up a whole lot
        # the biggest speedups come from walrus operators
        # and the fact that the result of this operation is cached
        total: int = 0

        if title := self.title:
            total += len(title)
        if description := self.description:
            total += len(description)
        if footer := self.footer:
            total += len(footer)
        if author := self.author:
            total += len(author)

        total += sum(map(len, self.fields))
        return total

    @functools.lru_cache(maxsize=32)
    def __bool__(self: naff.Embed) -> bool:
        # not not is faster than any
        return not not (
            self.title
            or self.description
            or self.fields
            or self.author
            or self.thumbnail
            or self.footer
            or self.image
            or self.video
        )

    # the cache will keep invalid len/bool results if we don't clear it
    # on attribute or field change, so we make sure to clear it manually
    # that being said, using fields.append would be a problem... not like
    # there's much that can be done there

    def _invalidate_cache(self):
        self.__len__.cache_clear()
        self.__bool__.cache_clear()

    def add_field(self, name: str, value: typing.Any, inline: bool = False) -> None:
        self._invalidate_cache()
        return super().add_field(name, value, inline)

    def add_fields(self, *fields: naff.EmbedField | str | dict) -> None:
        self._invalidate_cache()
        return super().add_fields(*fields)

    def __setattr__(self, __name: str, __value: typing.Any) -> None:
        self._invalidate_cache()
        return super().__setattr__(__name, __value)


def patch():
    # why correctly monkeypatch when overriding init does the trick?
    naff.Embed.__init__ = FasterEmbed.__init__
