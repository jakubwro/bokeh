#-----------------------------------------------------------------------------
# Copyright (c) 2012 - 2019, Anaconda, Inc., and Bokeh Contributors.
# All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
#-----------------------------------------------------------------------------
'''

'''

#-----------------------------------------------------------------------------
# Boilerplate
#-----------------------------------------------------------------------------

import logging # isort:skip
log = logging.getLogger(__name__)

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------

# Standard library imports
from abc import ABC, abstractmethod
from typing import Callable, Iterator, List, NamedTuple, Optional, Set, Type, Union
from typing_extensions import Literal

# Bokeh imports
from ..model import Model
from ..settings import settings
from .assets import Bundle, Asset, Script, ScriptLink, StyleLink

# -----------------------------------------------------------------------------
# Globals and constants
# -----------------------------------------------------------------------------

LogLevel = Literal["trace", "debug", "info", "warn", "error", "fatal"]
Kind = Literal["js", "css"]

class Message(NamedTuple):
    type: str
    text: str

class Urls(NamedTuple):
    urls: Callable[[List[str], Kind], List[str]]
    messages: List[Message] = []

__all__ = ()

# -----------------------------------------------------------------------------
# General API
# -----------------------------------------------------------------------------

class Resources(ABC):
    """ The Resources class encapsulates information relating to loading or
    embedding Bokeh Javascript and CSS.

    Args:

        version (str, optional) : what version of Bokeh JS and CSS to load

            Only valid with the ``'cdn'`` mode

        root_dir (str, optional) : root directory for loading Bokeh JS and CSS assets

            Only valid with ``'relative'`` and ``'relative-dev'`` modes

        minified (bool, optional) : whether JavaScript and CSS should be minified or not (default: True)


    Once configured, a Resource object exposes the following public attributes:

    Attributes:
        js_raw : any raw JS that needs to be placed inside ``<script>`` tags
        css_raw : any raw CSS that needs to be places inside ``<style>`` tags
        js_files : URLs of any JS files that need to be loaded by ``<script>`` tags
        css_files : URLs of any CSS files that need to be loaded by ``<link>`` tags

    These attributes are often useful as template parameters when embedding
    Bokeh plots.

    """

    mode: str
    dev: bool = False

    _log_level: Optional[LogLevel]

    def __init__(self, *,
            dev: Optional[bool] = None,
            minified: Optional[bool] = None,
            legacy: Optional[bool] = None,
            log_level: Optional[LogLevel] = None) -> None:
        self.minified = settings.minified(minified)
        self.legacy = settings.legacy(legacy)
        self.log_level = settings.log_level(log_level)

    @abstractmethod
    def __call__(self, *, dev: Optional[bool] = None, minified: Optional[bool] = None, legacy: Optional[bool] = None) -> Resources:
        pass

    @abstractmethod
    def _resolve(self, kind: Kind) -> List[Asset]:
        pass

    def _resolve_external(self) -> List[Asset]:
        """ Collect external resources set on resource_attr attribute of all models."""
        visited: Set[str] = set()

        def resolve_attr(cls: Type[Model], attr: str) -> Iterator[str]:
            external: Union[str, List[str]] = getattr(cls, attr, [])

            if isinstance(external, str):
                url = external
                if url not in visited:
                    visited.add(url)
                    yield url
            else:
                for url in external:
                    if url not in visited:
                        visited.add(url)
                        yield url

        assets: List[Asset] = []

        for cls in sorted(Model.all_models(), key=lambda model: model.__qualified_model__):
            assets.extend([ StyleLink(url) for url in resolve_attr(cls, "__css__") ])
            assets.extend([ ScriptLink(url) for url in resolve_attr(cls, "__javascript__") ])

        return assets

    def resolve(self) -> Bundle:
        assets: List[Asset] = []

        assets.extend(self._resolve_external())
        assets.extend(self._resolve("js"))

        if self.log_level is not None:
            assets.append(Script(f"Bokeh.set_log_level('{self.log_level}');"))
        if self.dev:
            assets.append(Script("Bokeh.settings.dev = true"))

        return Bundle(*assets)

    @property
    def log_level(self) -> Optional[LogLevel]:
        return self._log_level

    @log_level.setter
    def log_level(self, level: Optional[LogLevel]) -> None:
        valid_levels = ["trace", "debug", "info", "warn", "error", "fatal"]
        if not (level is None or level in valid_levels):
            raise ValueError("Unknown log level '{}', valid levels are: {}".format(level, str(valid_levels)))
        self._log_level = level