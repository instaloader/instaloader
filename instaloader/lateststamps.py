import configparser
from datetime import datetime, timezone
from typing import Optional


class LatestStamps:
    PROFILE_ID = 'profile-id'
    PROFILE_PIC = 'profile-pic'
    POST_TIMESTAMP = 'post-timestamp'
    TAGGED_TIMESTAMP = 'tagged-timestamp'
    IGTV_TIMESTAMP = 'igtv-timestamp'
    STORY_TIMESTAMP = 'story-timestamp'
    ISO_FORMAT = '%Y-%m-%dT%H:%M:%S.%f%z'

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
            return self.data.getint(profile_name, self.PROFILE_ID)
        except (configparser.Error, ValueError):
            return None

    def save_profile_id(self, profile_name: str, profile_id: int):
        self.ensure_section(profile_name)
        self.data.set(profile_name, self.PROFILE_ID, str(profile_id))
        self.save()

    def rename_profile(self, old_profile: str, new_profile: str):
        self.ensure_section(new_profile)
        for option in [self.PROFILE_ID, self.PROFILE_PIC, self.POST_TIMESTAMP,
                       self.TAGGED_TIMESTAMP, self.IGTV_TIMESTAMP, self.STORY_TIMESTAMP]:
            if self.data.has_option(old_profile, option):
                value = self.data.get(old_profile, option)
                self.data.set(new_profile, option, value)
        self.data.remove_section(old_profile)
        self.save()

    def get_timestamp(self, section: str, key: str) -> datetime:
        try:
            return datetime.strptime(self.data.get(section, key), self.ISO_FORMAT)
        except (configparser.Error, ValueError):
            return datetime.fromtimestamp(0, timezone.utc)

    def set_timestamp(self, section: str, key: str, timestamp: datetime):
        self.ensure_section(section)
        self.data.set(section, key, timestamp.strftime(self.ISO_FORMAT))
        self.save()

    def get_last_post_timestamp(self, profile_name: str) -> datetime:
        return self.get_timestamp(profile_name, self.POST_TIMESTAMP)

    def set_last_post_timestamp(self, profile_name: str, timestamp: datetime):
        self.set_timestamp(profile_name, self.POST_TIMESTAMP, timestamp)

    def get_last_tagged_timestamp(self, profile_name: str) -> datetime:
        return self.get_timestamp(profile_name, self.TAGGED_TIMESTAMP)

    def set_last_tagged_timestamp(self, profile_name: str, timestamp: datetime):
        self.set_timestamp(profile_name, self.TAGGED_TIMESTAMP, timestamp)

    def get_last_igtv_timestamp(self, profile_name: str) -> datetime:
        return self.get_timestamp(profile_name, self.IGTV_TIMESTAMP)

    def set_last_igtv_timestamp(self, profile_name: str, timestamp: datetime):
        self.set_timestamp(profile_name, self.IGTV_TIMESTAMP, timestamp)

    def get_last_story_timestamp(self, profile_name: str) -> datetime:
        return self.get_timestamp(profile_name, self.STORY_TIMESTAMP)

    def set_last_story_timestamp(self, profile_name: str, timestamp: datetime):
        self.set_timestamp(profile_name, self.STORY_TIMESTAMP, timestamp)

    def get_profile_pic(self, profile_name: str) -> str:
        try:
            return self.data.get(profile_name, self.PROFILE_PIC)
        except configparser.Error:
            return ""

    def set_profile_pic(self, profile_name: str, profile_pic: str):
        self.ensure_section(profile_name)
        self.data.set(profile_name, self.PROFILE_PIC, profile_pic)
        self.save()
