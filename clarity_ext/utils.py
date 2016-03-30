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


def use_requests_cache(cache):
    requests_cache.install_cache(cache, allowable_methods=('GET', 'POST', 'DELETE', 'PUT'))

