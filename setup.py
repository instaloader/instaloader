#!/usr/bin/env python3

from setuptools import setup

setup(
    name='instaloader',
    version='1.1',
    py_modules=['instaloader'],
    url='https://github.com/Thammus/instaloader',
    license='MIT',
    author='Alexander Graf, André Koch-Kramer',
    author_email='mail@agraf.me, koch-kramer@web.de',
    description='Tool to download pictures (or videos) and captions from Instagram, from a given '
                'set of profiles, from your feed or from all followees of a given profile.',
    install_requires=['requests>=2.4'],
    python_requires='>=3.3',
    entry_points={'console_scripts': ['instaloader=instaloader:main']},
    zip_safe=True,
    keywords='instagram downloader',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6'
        'Topic :: Internet'
    ]
)
