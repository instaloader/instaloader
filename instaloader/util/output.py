import os
import sys
from typing import Optional
from pathlib import Path


class OutputWriter:
    def write(self, msg: str):
        raise NotImplemented

    def error(self, msg: str):
        raise NotImplemented


class StandardWriter(OutputWriter):
    def write(self, msg: str):
        print(msg)

    def error(self, msg: str):
        print(msg, file=sys.stderr)


class FileWriter(OutputWriter):
    """Class that handles the output that the program generates."""
    def __init__(self, filepath: Optional[Path] = None):
        """
        :param filepath: Optional[Path], if set, all output will be written to said file.
        """
        if filepath:
            self.output_file = filepath
            # print to stdout
            print(f'Writing output to file "{filepath}"')
            if os.path.exists(filepath):
                print('File exists, overwriting file')

    def write(self, msg: str):
        """
        Writes normal output.
        :param msg: Message
        """
        self._write_to_file(msg)

    def error(self, msg: str):
        """
        Writes error output.
        Prefixes ``ERROR:`` to message if writing to file, else writes to ``stderr``.
        :param msg: Message
        """
        self._write_to_file(f'ERROR: {msg}')

    def _write_to_file(self, msg: str):
        open(self.output_file, encoding='UTF-8', mode='a').write(f'{msg}\n')


class QuietWriter(OutputWriter):
    """Does nothing"""
    def write(self, msg: str):
        pass

    def error(self, msg: str):
        pass
