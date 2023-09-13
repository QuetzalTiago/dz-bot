class BaseCommand:
    def __init__(self, client, message):
        self.client = client
        self.message = message

    @staticmethod
    def __str__():
        return "Command description"

    async def execute(self):
        pass
