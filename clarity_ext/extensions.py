# Defines all classes that are expected to be extended. These are
# also imported to the top-level module

# TODO: use Python 3 and add typing hints

from abc import ABCMeta, abstractmethod


class DriverFileExt:
    __metaclass__ = ABCMeta

    def __init__(self, context):
        """
        @type context: clarity_ext.driverfile.DriverFileContext

        :param context:
        :return:
        """
        self.context = context

    @abstractmethod
    def create(self):
        pass

