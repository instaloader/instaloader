import os
import sys
from typing import Optional
from pathlib import Path


class OutputWriter:
    """
    Interface that is faithful to the builtin ``print`` function.
    """
    def write(self, *args, sep=' ', end='\n', flush=False):
        raise NotImplemented

    def error(self, *args, sep=' ', end='\n', flush=False):
        raise NotImplemented


class DefaultWriter(OutputWriter):
    def write(self, *args, sep=' ', end='\n', flush=False):
        print(args, sep=sep, end=end, flush=flush)

    def error(self, *args, sep=' ', end='\n', flush=False):
        print(args, sep=sep, end=end, flush=flush, file=sys.stderr)


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

    def write(self, *args, sep=' ', end='\n', flush=False):
        """
        Writes normal output.
        :param sep: seperator
        :param end: end of message
        :param flush: has no effect
        """
        self._write_to_file(list(args), sep, end)

    def error(self, *args, sep=' ', end='\n', flush=False):
        """
        Writes error output.
        Prefixes ``ERROR:`` to message if writing to file, else writes to ``stderr``.
        :param sep: seperator
        :param end: end of message
        :param flush: has no effect
        """
        self._write_to_file(['ERROR: '] + list(args), sep, end)

    def _write_to_file(self, *args, sep: str, end: str):
        args = [str(arg) for arg in args]
        message = sep.join(args)
        message += end

        open(self.output_file, encoding='UTF-8', mode='a').write(message)


class QuietWriter(OutputWriter):
    """Does nothing"""
    def write(self, *args, sep=' ', end='\n', flush=False):
        pass

    def error(self, *args, sep=' ', end='\n', flush=False):
        pass
