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
    def duration_seconds(self):
        # Livestreams and some entries have no/zero duration.
        return self.info.get("duration") or 0

    @property
    def duration(self):
        minutes, seconds = divmod(int(self.duration_seconds), 60)
        return "{}:{:02}".format(minutes, seconds)

    @property
    def progress(self):
        minutes, seconds = divmod(self.current_seconds, 60)

        return "{}:{:02}".format(minutes, seconds)

    @property
    def views(self):
        view_count = self.info.get("view_count", 0)
        return "{:,}".format(view_count) if view_count is not None else "N/A"

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
    def like_count(self):
        like_count = self.info.get("like_count", 0)
        return "{:,}".format(like_count) if like_count is not None else "N/A"

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

    def to_embed(self, queue, shuffle=False, loop=False):
        embed = discord.Embed(title=self.title, color=0x3498DB, url=self.url)
        details = f"{self.time_since_upload}\n{self.views} views\nRequested by <@{self.message.author.id}>"
        progress = self.get_progress_bar()
        thumbnail = self.thumbnail_url

        # Thumbnail
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)

        # Details
        embed.add_field(name=self.uploader, value=details, inline=False)

        # Loop
        if loop:
            embed.add_field(name="", value="*Loop* is **ON**", inline=False)
        # Shuffle
        elif shuffle:
            embed.add_field(name="", value="*Shuffle* is **ON**", inline=False)
        # Next
        elif queue:
            embed.add_field(name="Next:", value=f"**{queue[0].title}**", inline=False)

        # Lyrics
        if self.lyrics:
            embed.set_footer(text="Lyrics are available! (beta)")

        # Progress bar
        embed.add_field(name="", value=progress, inline=False)

        return embed

    def get_progress_bar(self, bar_length=30):
        duration_seconds = self.duration_seconds
        # Livestreams/unknown durations have no meaningful progress bar.
        if not duration_seconds:
            return f"**{self.progress}**          \n"
        # yt-dlp reports duration as a float for many extractors - clamping
        # current_seconds to a float would make `progress`'s divmod (and thus
        # the rendered "M:SS" string) float-valued too for the rest of the
        # song, e.g. "3.0:37.36" instead of "3:37".
        duration_seconds = int(duration_seconds)

        if self.current_seconds > duration_seconds:
            self.current_seconds = duration_seconds

        filled_length = int(bar_length * self.current_seconds // duration_seconds)
        bar = "█" * filled_length + "▒" * (bar_length - filled_length)
        return f"{bar} **{self.progress}/{self.duration}**          \n"
