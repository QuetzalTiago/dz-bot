import datetime


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
