from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("business-use-core")
except PackageNotFoundError:
    __version__ = "dev"
