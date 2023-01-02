import contextlib

from . import embed
from . import orjson_serialize

__all__ = ("install_naff_speedups",)

HAS_ORJSON = False

with contextlib.suppress(ImportError):
    import orjson

    HAS_ORJSON = True


def install_naff_speedups(
    embeds: bool = True, use_orjson_for_serialization: bool = HAS_ORJSON
) -> None:
    """
    Monkeypatches/installs various speedups for NAFF.

    These usually are unstable, and some may change the behavior of NAFF in unexpected way -
    while common use-case scenarios are expected to act mostly normally, Tansy has no qualms
    about rewriting internals for speed gains.

    This should be run as soon as possible if you wish to use it. Ideally, it should be
    one of the first things you do in your bot runner file, right after importing everything.
    This allows the monkeypatches to work as expected.

    If any of these patches are installed, report behavior related to them to Tansy, not NAFF.

    Args:
        embeds (bool): Speeds up length getting and validating checking in embeds,
        possibly by a significant margin if those operations are run repeatedly.
        Note: directing appending to the `fields` attribute in Embeds will cause unexpected
        behavior - it is suggested you use the `add_field(s)` functions instead while using this.

        use_orjson_for_serialization (bool): By default, aiohttp, and so NAFF, use json for
        serializing payloads (when they are dicts, which is quite often). orjson is a faster
        alternative to the built-in json module, and is already used for deserialization if
        it is detected to be installed, but not for serialization. Tansy makes it so orjson
        is also used for serialization, though the speed difference is likely to be
        negligible for most operations.
        By default, this is only enabled if orjson is installed.
    """

    if embeds:
        embed.patch()
    if use_orjson_for_serialization:
        orjson_serialize.patch()
