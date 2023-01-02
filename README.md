# tansy

[![PyPI](https://img.shields.io/pypi/v/tansy)](https://pypi.org/project/tansy/)
[![Downloads](https://static.pepy.tech/personalized-badge/tansy?period=total&units=abbreviation&left_color=grey&right_color=green&left_text=pip%20installs)](https://pepy.tech/project/tansy)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Unstable experiments with NAFF.

# Commands

`tansy` provides a unique way to define options for slash commands - a way that appears often in other Discord Python libraries.

Instead of needing a decorator per option or to define the option in one huge list, `tansy` allows you to define each option in the function itself.
By using a special metadata function, you can specify what each argument/parameter in a function should be like as an option, with tansy smartly handling the rest for you.

## Example Command
```python
import naff
import tansy

@tansy.slash_command(name="test", description="Nice test command, huh?")
async def test_cmd(
    ctx: naff.InteractionCommand,
    the_user: naff.User = tansy.Option(name="user", description="The user to ping."),
):
    await ctx.send(the_user.mention)
```

# Speedups

`tansy` also includes several patches that can speed up NAFF itself, sometimes by a signficant margin.
However, these patches are unstable, and may break some (usually niche) parts of the things they modify.

To install them, use:
```python
import tansy

# this should be the first line of code you run in your main file if you want
# everything to work correctly
tansy.install_naff_speedups()
```

You can also toggle on or off what patches you want - take a look at the function's docstring for details.