# Instaloader Documentation

This directory contains sources for the Instaloader documentation.

The documentation is hosted at:
https://instaloader.github.io/

## Build

The documentation is created with [Sphinx](http://www.sphinx-doc.org/). To build it, use (in the top-level directory
of the Instaloader source tree):

```
pipenv sync --dev
make -C docs html
```
