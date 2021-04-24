import configparser
from datetime import datetime


class LatestStamps:
    POST_SECTION = 'post-timestamps'

    def __init__(self, latest_stamps_file):
        self.file = latest_stamps_file
        self.data = configparser.ConfigParser()
        self.data.read(latest_stamps_file)

    def save(self):
        with open(self.file, 'w') as f:
            self.data.write(f)

    def get_last_post_timestamp(self, profile_name: str) -> datetime:
        try:
            return datetime.fromtimestamp(self.data.getint(self.POST_SECTION, profile_name))
        except (configparser.Error, ValueError, OverflowError, OSError):
            return datetime.min

    def set_last_post_timestamp(self, profile_name: str, timestamp: datetime):
        if not self.data.has_section(self.POST_SECTION):
            self.data.add_section(self.POST_SECTION)
        self.data.set(self.POST_SECTION, profile_name, str(int(timestamp.timestamp())))
        self.save()

