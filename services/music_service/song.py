import datetime
import discord


class Song:
    def __init__(self, path, info, message):
        self.path = path
        self.info = info
        self.message = message
        self.message_to_delete = None

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
    def comment_count(self):
        return "{:,}".format(self.info.get("comment_count", 0))

    @property
    def upload_date(self):
        raw_date = self.info.get("upload_date", None)
        if raw_date:
            return datetime.datetime.strptime(raw_date, "%Y%m%d").date()
        return None

    @property
    def time_since_upload(self):
        if self.upload_date:
            delta = datetime.date.today() - self.upload_date

            if delta.days >= 365:
                years = delta.days // 365
                return f"{years} year{'s' if years > 1 else ''} ago"
            elif delta.days >= 30:
                months = delta.days // 30
                return f"{months} month{'s' if months > 1 else ''} ago"
            elif delta.days > 0:
                return f"{delta.days} day{'s' if delta.days > 1 else ''} ago"
            else:
                # if the song was uploaded today
                return "today"

        return "N/A"

    def to_embed(self):
        embed = discord.Embed(
            title=f"Now Playing: {self.title}",
            description=f"**{self.duration}**",
            color=0x3498DB,
        )
        details = (
            f"{self.uploader}\n"
            f"{self.time_since_upload}\n"
            f"{self.views} views\n"
            f"{self.like_count} likes\n"
            f"{self.comment_count} comments\n"
            f"Requested by <@{self.message.author.id}>"
        )
        embed.add_field(name="Details", value=details, inline=False)

        return embed
