from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("bbterm")
except PackageNotFoundError:  # running from a source tree, not installed
    __version__ = "0.0.0+source"
