from . import embed

__all__ = ("install_naff_speedups",)


def install_naff_speedups(embeds: bool = True):
    """
    Monkeypatches/installs various speedups for NAFF.

    These usually are unstable, and some may change the behavior of NAFF in unexpected way -
    while common use-case scenarios are expected to act mostly normally, Tansy has no qualms
    about rewriting internals for speed gains.

    If any of these patches are installed, report behavior related to them to Tansy, not NAFF.

    Args:
        embeds (bool): Speeds up length getting and validating checking in embeds,
        possibly by a significant margin if those operations are run repeatedly.
        Note: directing appending to the `fields` attribute in Embeds will cause unexpected
        behavior - it is suggested you use the `add_field(s)` functions instead while using this.
    """
    if embeds:
        embed.patch()
