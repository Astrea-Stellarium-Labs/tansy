# tansy
Unstable experiments with NAFF.

Right now, `tansy` provides a unique way to define options for slash commands - a way that appears often in other Discord Python libraries.

Instead of needing a decorator per option or to define the option in one huge list, `tansy` allows you to define each option in the function itself.
By using a special metadata function, you can specify what each argument/parameter in a function should be like as an option, with tansy smartly handling the rest for you.

# Example Command
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