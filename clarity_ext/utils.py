import requests_cache

# http://stackoverflow.com/a/3013910/282024
def lazyprop(fn):
    attr_name = '_lazy_' + fn.__name__
    @property
    def _lazyprop(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, fn(self))
        return getattr(self, attr_name)
    return _lazyprop


# Clone of request_cache's sqlite cache. Will replace this with FileCache:
from requests_cache.backends import BaseCache
from requests_cache.backends.storage.dbdict import DbDict, DbPickleDict

class RequestsFileCache(BaseCache):
    def __init__(self, location='cache',
                 fast_save=False, extension='.sqlite', **options):
        """
        :param location: database filename prefix (default: ``'cache'``)
        :param fast_save: Speedup cache saving up to 50 times but with possibility of data loss.
                          See :ref:`backends.DbDict <backends_dbdict>` for more info
        :param extension: extension for filename (default: ``'.sqlite'``)
        """
        super(RequestsFileCache, self).__init__(**options)
        self.responses = DbPickleDict(location + extension, 'responses', fast_save=fast_save)
        self.keys_map = DbDict(location + extension, 'urls')

def use_requests_cache(cache):
    # We need to inject our
    if "file" not in requests_cache.backends.registry:
        requests_cache.backends.registry['file'] = RequestsFileCache

    requests_cache.install_cache(cache, allowable_methods=('GET', 'POST', 'DELETE', 'PUT'), backend="file")

