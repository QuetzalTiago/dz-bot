import datetime
import discord


class Song:
    def __init__(self, path, info, message, lyrics=None):
        self.path = path
        self.info = info
        self.message = message
        self.messages_to_delete = []
        self._lyrics = lyrics
        self.lyrics_sent = False
        self.current_seconds = 0
        self.embed_message = None

    @property
    def title(self):
        return self.info["title"]

    @property
    def duration(self):
        total_seconds = self.info["duration"]

        minutes, seconds = divmod(total_seconds, 60)

        return "{}:{:02}".format(minutes, seconds)

    @property
    def progress(self):
        minutes, seconds = divmod(self.current_seconds, 60)

        return "{}:{:02}".format(minutes, seconds)

    @property
    def views(self):
        return "{:,}".format(self.info["view_count"])

    @property
    def url(self):
        return self.info["original_url"]

    @property
    def thumbnail_url(self):
        return self.info.get("thumbnail", None)

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
        comment_count = self.info.get("comment_count", 0)
        return "{:,}".format(comment_count) if comment_count is not None else "N/A"

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

    @property
    def lyrics(self):
        return self._lyrics

    def to_embed(self):
        embed = discord.Embed(title=self.title, color=0x3498DB, url=self.url)
        details = f"{self.time_since_upload}\n{self.views} views\nRequested by <@{self.message.author.id}>"
        progress = self.get_progress_bar()

        if self.lyrics:
            embed.set_footer(text="Click on 📖 for lyrics")
        else:
            embed.set_footer(text="Lyrics are only available for spotify songs")

        embed.add_field(name=self.uploader, value=details, inline=False)
        embed.add_field(name="Playing", value=progress, inline=False)

        thumbnail = self.thumbnail_url
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)

        return embed

    def get_progress_bar(self, bar_length=30):
        duration_seconds = self.info["duration"]
        if self.current_seconds > duration_seconds:
            self.current_seconds = duration_seconds

        filled_length = int(bar_length * self.current_seconds // duration_seconds)
        bar = "█" * filled_length + "▒" * (bar_length - filled_length)
        progress_percentage = (self.current_seconds / duration_seconds) * 100

        return f"{bar} **{self.progress}/{self.duration}** ({progress_percentage:.1f}%)"
