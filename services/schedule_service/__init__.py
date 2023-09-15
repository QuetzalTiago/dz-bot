import random
import asyncio
import schedule


class ScheduleService:

    def __init__(self, client):
        self.client = client
        self.schedule = schedule.Scheduler()
        self.main_channel_id = 378245223853064199
            
    async def initialize(self):
        self.client.loop.create_task(self.background_task())
        print("Schedule service initialized.")

    async def background_task(self):
        await self.client.wait_until_ready()
        self.schedule.every(5).seconds.do(self.test)
        self.schedule.every(3).weeks.do(self.pay_up)
        self.schedule.every().day.at("04:20", "America/Montevideo").do(self.blaze_it)
        self.schedule.every().day.at("16:20", "America/Montevideo").do(self.blaze_it)
        while not self.client.is_closed():
            self.schedule.run_pending()
            await asyncio.sleep(1)

    async def blaze_it(self):
        channel = self.get_channel(self.main_channel_id)
        gifs = [
                    "https://tenor.com/qBaO.gif",
                    "https://tenor.com/bUc6T.gif",
                    "https://tenor.com/bWGTx.gif",
                    "https://tenor.com/7M09.gif",
                    "https://tenor.com/bEZC5.gif",
                    "https://tenor.com/bDYTg.gif",
                ]
        index = random.randrange(len(gifs))
        await channel.send(":four: :two: :zero: ")
        await channel.send(gifs[index])

    async def pay_up(self):
        spotify_role_id = 1134271094006755438
        channel = self.get_channel(self.main_channel_id)
        await channel.send(
                    f"<@&{spotify_role_id}> PAY UP NIGGA \n https://docs.google.com/spreadsheets/d/1TPG7yqK5DoiZ61HoyZXi2GZMBlJ5O8wdsXiZgt9mWj4/edit?usp=sharing"
                )
        await channel.send("https://tenor.com/view/mc-gregor-pay-up-gif-8865194")

    async def test(self):
        channel = self.get_channel(self.main_channel_id)
        await channel.send(f"schedule test 5")
                
