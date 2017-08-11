#!/usr/bin/env python3

import re
import sys
from setuptools import setup


def get_version():
    with open('instaloader.py') as f:
        for line in f:
            m = re.match("__version__ = '(.*)'", line)
            if m:
                return m.group(1)
    raise SystemExit("Could not find version string.")


if sys.version_info < (3, 5):
    sys.exit('Instaloader requires Python >= 3.5.')

setup(
    name='instaloader',
    version=get_version(),
    py_modules=['instaloader'],
    url='https://github.com/Thammus/instaloader',
    license='MIT',
    author='Alexander Graf, André Koch-Kramer',
    author_email='mail@agraf.me, koch-kramer@web.de',
    description='Download pictures (or videos) along with their captions and other metadata '
                'from Instagram.',
    long_description=open('README.rst').read(),
    install_requires=['requests>=2.4'],
    python_requires='>=3.5',
    entry_points={'console_scripts': ['instaloader=instaloader:main']},
    zip_safe=True,
    keywords='instagram downloader',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Internet',
        'Topic :: Multimedia :: Graphics'
    ]
)
