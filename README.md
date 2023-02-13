# tansy

[![PyPI](https://img.shields.io/pypi/v/tansy)](https://pypi.org/project/tansy/)
[![Downloads](https://static.pepy.tech/personalized-badge/tansy?period=total&units=abbreviation&left_color=grey&right_color=green&left_text=pip%20installs)](https://pepy.tech/project/tansy)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Unstable experiments with interactions.py.

# Commands

`tansy` provides a unique way to define options for slash commands - a way that appears often in other Discord Python libraries.

Instead of needing a decorator per option or to define the option in one huge list, `tansy` allows you to define each option in the function itself.
By using a special metadata function, you can specify what each argument/parameter in a function should be like as an option, with tansy smartly handling the rest for you.

```python
import interactions as ipy
import tansy

@tansy.slash_command(name="test", description="Nice test command, huh?")
async def test_cmd(
    ctx: ipy.InteractionContext,
    the_user: ipy.User = tansy.Option(name="user", description="The user to ping."),
):
    await ctx.send(the_user.mention)
```

## Class Slash Command

In case you want to try something very unique, or just want to leverage classes, `tansy` allows you to leverage its toolset to make class slash commands.

```python
import interactions as ipy
import tansy

@tansy.class_slash_command(name="test", description="Nice test command, huh?")
class Test:
    the_user: ipy.User = tansy.Option(name="user", description="The user to ping.")

    async def callback(self, ctx: ipy.InteractionContext):
        await ctx.send(self.the_user.mention)
```

Note that the class is being read and adjusted to be more like a typical functional declaration, and so isn't a fully true class-based approach.
Subclasses are not going to become subcommands (though `class_subcommand` exists), and while the class *does* get initialized on every run
(meaning you can use custom `__init__`s, as long as they have no parameters that need to be filled in), the class is largely untouched outside
of declaration and using `callback`.