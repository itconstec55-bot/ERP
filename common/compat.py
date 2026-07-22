import sys

if sys.version_info >= (3, 13):
    from django.template.context import BaseContext

    def _basecontext_copy(self):
        duplicate = self.__class__.__new__(self.__class__)
        duplicate.__dict__.update(self.__dict__)
        return duplicate

    BaseContext.__copy__ = _basecontext_copy
