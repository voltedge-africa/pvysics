"""Shared code for every tutorial video: house style, the `Narrated` scene base class, timing helpers.

A video's scenes.py starts with   from common import *
"""
from .style import *      # noqa: F401,F403
from .narrated import *   # noqa: F401,F403
from .shots import *      # noqa: F401,F403
from . import pvdata      # noqa: F401  (the app's own engine: real curves and runs; see pvdata.py)
