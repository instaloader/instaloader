import configparser
from datetime import datetime


class LatestStamps:
    POST_SECTION = 'post-timestamps'
    STORY_SECTION = 'story-timestamps'
    PROFILE_PIC_SECTION = 'profile-pics'

    def __init__(self, latest_stamps_file):
        self.file = latest_stamps_file
        self.data = configparser.ConfigParser()
        self.data.read(latest_stamps_file)

    def save(self):
        with open(self.file, 'w') as f:
            self.data.write(f)

    def ensure_section(self, section: str):
        if not self.data.has_section(section):
            self.data.add_section(section)

    def get_timestamp(self, section: str, key: str) -> datetime:
        try:
            return datetime.fromtimestamp(self.data.getint(section, key))
        except (configparser.Error, ValueError, OverflowError, OSError):
            return datetime.min

    def set_timestamp(self, section: str, key: str, timestamp: datetime):
        self.ensure_section(section)
        self.data.set(section, key, str(int(timestamp.timestamp())))
        self.save()

    def get_last_post_timestamp(self, profile_name: str) -> datetime:
        return self.get_timestamp(self.POST_SECTION, profile_name)

    def set_last_post_timestamp(self, profile_name: str, timestamp: datetime):
        self.set_timestamp(self.POST_SECTION, profile_name, timestamp)

    def get_last_story_timestamp(self, profile_name: str) -> datetime:
        return self.get_timestamp(self.STORY_SECTION, profile_name)

    def set_last_story_timestamp(self, profile_name: str, timestamp: datetime):
        self.set_timestamp(self.STORY_SECTION, profile_name, timestamp)

    def get_profile_pic(self, profile_name: str) -> str:
        try:
            return self.data.get(self.PROFILE_PIC_SECTION, profile_name)
        except configparser.Error:
            return ""

    def set_profile_pic(self, profile_name: str, profile_pic: str):
        self.ensure_section(self.PROFILE_PIC_SECTION)
        self.data.set(self.PROFILE_PIC_SECTION, profile_name, profile_pic)
        self.save()
