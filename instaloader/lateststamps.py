import configparser
from datetime import datetime, timezone
from typing import Optional
from os.path import dirname
from os import makedirs


class LatestStamps:
    """LatestStamps class.

    Convenience class for retrieving and storing data from the :option:`--latest-stamps` file.

    :param latest_stamps_file: path to file.

    .. versionadded:: 4.8"""
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

    def _save(self):
        makedirs(dirname(self.file), exist_ok=True)
        with open(self.file, 'w') as f:
            self.data.write(f)

    def _ensure_section(self, section: str):
        if not self.data.has_section(section):
            self.data.add_section(section)

    def get_profile_id(self, profile_name: str) -> Optional[int]:
        """Returns stored ID of profile."""
        try:
            return self.data.getint(profile_name, self.PROFILE_ID)
        except (configparser.Error, ValueError):
            return None

    def save_profile_id(self, profile_name: str, profile_id: int):
        """Stores ID of profile."""
        self._ensure_section(profile_name)
        self.data.set(profile_name, self.PROFILE_ID, str(profile_id))
        self._save()

    def rename_profile(self, old_profile: str, new_profile: str):
        """Renames a profile."""
        self._ensure_section(new_profile)
        for option in [self.PROFILE_ID, self.PROFILE_PIC, self.POST_TIMESTAMP,
                       self.TAGGED_TIMESTAMP, self.IGTV_TIMESTAMP, self.STORY_TIMESTAMP]:
            if self.data.has_option(old_profile, option):
                value = self.data.get(old_profile, option)
                self.data.set(new_profile, option, value)
        self.data.remove_section(old_profile)
        self._save()

    def _get_timestamp(self, section: str, key: str) -> datetime:
        try:
            return datetime.strptime(self.data.get(section, key), self.ISO_FORMAT)
        except (configparser.Error, ValueError):
            return datetime.fromtimestamp(0, timezone.utc)

    def _set_timestamp(self, section: str, key: str, timestamp: datetime):
        self._ensure_section(section)
        self.data.set(section, key, timestamp.strftime(self.ISO_FORMAT))
        self._save()

    def get_last_post_timestamp(self, profile_name: str) -> datetime:
        """Returns timestamp of last download of a profile's posts."""
        return self._get_timestamp(profile_name, self.POST_TIMESTAMP)

    def set_last_post_timestamp(self, profile_name: str, timestamp: datetime):
        """Sets timestamp of last download of a profile's posts."""
        self._set_timestamp(profile_name, self.POST_TIMESTAMP, timestamp)

    def get_last_tagged_timestamp(self, profile_name: str) -> datetime:
        """Returns timestamp of last download of a profile's tagged posts."""
        return self._get_timestamp(profile_name, self.TAGGED_TIMESTAMP)

    def set_last_tagged_timestamp(self, profile_name: str, timestamp: datetime):
        """Sets timestamp of last download of a profile's tagged posts."""
        self._set_timestamp(profile_name, self.TAGGED_TIMESTAMP, timestamp)

    def get_last_igtv_timestamp(self, profile_name: str) -> datetime:
        """Returns timestamp of last download of a profile's igtv posts."""
        return self._get_timestamp(profile_name, self.IGTV_TIMESTAMP)

    def set_last_igtv_timestamp(self, profile_name: str, timestamp: datetime):
        """Sets timestamp of last download of a profile's igtv posts."""
        self._set_timestamp(profile_name, self.IGTV_TIMESTAMP, timestamp)

    def get_last_story_timestamp(self, profile_name: str) -> datetime:
        """Returns timestamp of last download of a profile's stories."""
        return self._get_timestamp(profile_name, self.STORY_TIMESTAMP)

    def set_last_story_timestamp(self, profile_name: str, timestamp: datetime):
        """Sets timestamp of last download of a profile's stories."""
        self._set_timestamp(profile_name, self.STORY_TIMESTAMP, timestamp)

    def get_profile_pic(self, profile_name: str) -> str:
        """Returns filename of profile's last downloaded profile pic."""
        try:
            return self.data.get(profile_name, self.PROFILE_PIC)
        except configparser.Error:
            return ""

    def set_profile_pic(self, profile_name: str, profile_pic: str):
        """Sets filename of profile's last downloaded profile pic."""
        self._ensure_section(profile_name)
        self.data.set(profile_name, self.PROFILE_PIC, profile_pic)
        self._save()
