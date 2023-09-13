class CommandService:
    def __init__(self, client):
        self.client = client
        self.commands = {}

    def register_command(self, trigger: str, command_class, params=False, service=None):
        self.commands[trigger] = (command_class, service, params)

    async def handle_command(self, message):
        lowerCaseMessage = message.content.lower()

        for trigger, (command_class, service, params) in self.commands.items():
            if (params and lowerCaseMessage.startswith(trigger)) or (
                lowerCaseMessage == trigger
            ):
                await message.add_reaction("👍")
                if service:
                    command = command_class(self.client, message, service)
                else:
                    command = command_class(self.client, message)
                await command.execute()
                break

    def getCommandsInfo(self):
        info = []
        for trigger, (command_class, _, _) in self.commands.items():
            info.append(f"**{trigger}**: {command_class.__str__()}")
        return "\n".join(info)

    async def purgeMessages(self, message):
        await message.channel.purge(
            limit=100,
            check=lambda m: m.author == self.client.user
            or any(
                (params and m.content.lower().startswith(trigger))
                or (m.content.lower() == trigger)
                for trigger, (_, _, params) in self.commands.items()
            ),
        )
