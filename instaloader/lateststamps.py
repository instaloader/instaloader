import configparser
from datetime import datetime
from typing import Optional


class LatestStamps:
    ID_SECTION = 'profile-ids'
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

    def get_profile_id(self, profile_name: str) -> Optional[int]:
        try:
            return self.data.getint(self.ID_SECTION, profile_name)
        except (configparser.Error, ValueError):
            return None

    def save_profile_id(self, profile_name: str, profile_id: int):
        self.ensure_section(self.ID_SECTION)
        self.data.set(self.ID_SECTION, profile_name, str(profile_id))
        self.save()

    def rename_profile(self, old_profile: str, new_profile: str):
        for section in [self.ID_SECTION, self.POST_SECTION, self.STORY_SECTION, self.PROFILE_PIC_SECTION]:
            if self.data.has_option(section, old_profile):
                value = self.data.get(section, old_profile)
                self.data.set(section, new_profile, value)
                self.data.remove_option(section, old_profile)
        self.save()

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
