import os


DEFAULT_VERSION = "17.2.2"
VERSION = (os.getenv("APP_VERSION") or DEFAULT_VERSION).removeprefix("v")
