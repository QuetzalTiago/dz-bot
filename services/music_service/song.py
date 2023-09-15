import datetime
import discord


class Song:
    def __init__(self, path, info, message):
        self.path = path
        self.info = info
        self.message = message

    @property
    def title(self):
        return self.info["title"]

    @property
    def duration(self):
        return str(datetime.timedelta(seconds=self.info["duration"]))

    @property
    def views(self):
        return "{:,}".format(self.info["view_count"])

    @property
    def uploader(self):
        return self.info.get("uploader", "N/A")

    @property
    def upload_date(self):
        raw_date = self.info.get("upload_date", None)
        if raw_date:
            return datetime.datetime.strptime(raw_date, "%Y%m%d").strftime("%Y-%m-%d")
        return "N/A"

    @property
    def like_count(self):
        return "{:,}".format(self.info.get("like_count", 0))

    @property
    def dislike_count(self):
        return "{:,}".format(self.info.get("dislike_count", 0))

    @property
    def comment_count(self):
        return "{:,}".format(self.info.get("comment_count", 0))

    def to_embed(self):
        embed = discord.Embed(
            title=self.title,
            description=f"Requested by <@{self.message.author.id}>",
            color=0x3498DB,
        )
        details = (
            f"Uploader: {self.uploader}\n"
            f"Upload Date: {self.upload_date}\n"
            f"Duration: {self.duration}\n"
            f"Views: {self.views}\n"
            f"Likes: {self.like_count}\n"
            f"Dislikes: {self.dislike_count}\n"
            f"Comments: {self.comment_count}"
        )
        embed.add_field(name="Details", value=details, inline=False)

        return embed
