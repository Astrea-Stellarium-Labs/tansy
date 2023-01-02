"""
Tansy
Unstable experiments with NAFF.
:copyright: (c) 2022-present Astrea49
:license: MIT, see LICENSE for more details.
"""

__version__ = "0.5.0"


from .slash_commands import *
from .slash_param import *
from .speedup.install import install_naff_speedups

__all__ = (
    "TansySlashCommandParameter",
    "TansySlashCommand",
    "SlashCommand",
    "tansy_slash_command",
    "slash_command",
    "ParamInfo",
    "Param",
    "Option",
    "install_naff_speedups",
)
