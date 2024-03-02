"""
Tansy
Unstable experiments with interactions.py.
:copyright: (c) 2022-present AstreaTSS
:license: MIT, see LICENSE for more details.
"""

__version__ = "0.9.1"


from .class_slash import *
from .slash_commands import *
from .slash_param import *

__all__ = (
    "__version__",
    "TansySlashCommand",
    "TansyHybridSlashCommand",
    "SlashCommand",
    "HybridSlashCommand",
    "tansy_slash_command",
    "tansy_hybrid_slash_command",
    "slash_command",
    "hybrid_slash_command",
    "tansy_subcommand",
    "tansy_hybrid_slash_subcommand",
    "subcommand",
    "hybrid_slash_subcommand",
    "ParamInfo",
    "Param",
    "Option",
    "ClassSlashCommand",
    "class_slash_command",
    "class_subcommand",
    "describe",
    "ClashHybridSlashCommand",
    "class_hybrid_slash_command",
    "class_hybrid_subcommand",
)
