"""
Tansy
Unstable experiments with interactions.py.
:copyright: (c) 2022-present AstreaTSS
:license: MIT, see LICENSE for more details.
"""

__version__ = "0.6.1"


from .class_slash import *
from .slash_commands import *
from .slash_param import *

__all__ = (
    "TansySlashCommandParameter",
    "TansySlashCommand",
    "SlashCommand",
    "tansy_slash_command",
    "slash_command",
    "tansy_subcommand",
    "subcommand",
    "ParamInfo",
    "Param",
    "Option",
    "ClassSlashCommand",
    "class_slash_command",
    "class_subcommand",
    "describe",
)
