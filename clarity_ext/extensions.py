import importlib
import os
import shutil
from clarity_ext.driverfile import DriverFileService
import logging

# Defines all classes that are expected to be extended. These are
# also imported to the top-level module

# TODO: use Python 3 and add typing hints

from abc import ABCMeta, abstractmethod


class ExtensionService:
    """TODO: MOVE TO extensions.py"""
    def execute(self, module, artifacts_to_stdout=False):
        """
        Given a module, finds the extension in it and runs all of its integration tests
        :param module:
        :return:
        """
        def files_to_remove(path):
            if os.path.exists(path):
                for item in os.listdir(path):
                    if item != "cache.sqlite":
                        yield os.path.join(path, item)

        module_obj = importlib.import_module(module)
        extension = getattr(module_obj, "Extension")
        instance = extension(None)
        integration_tests = list(instance.integration_tests())
        if issubclass(extension, DriverFileExt):
            for test in integration_tests:
                parts = module.split(".")
                parts = parts[1:]
                path = os.path.sep.join(parts)
                # Remove everything but the cache file

                for item in files_to_remove(path):
                    if os.path.isdir(item):
                        shutil.rmtree(item)
                    else:
                        os.remove(item)

                if not os.path.exists(path):
                    os.makedirs(path)

                os.chdir(path)
                driver_file_svc = DriverFileService(test.step, module, ".", test.out_file)
                driver_file_svc.execute(artifacts_to_stdout=artifacts_to_stdout)
        else:
            raise NotImplementedError("Unknown extension")

class DriverFileExt:
    __metaclass__ = ABCMeta

    def __init__(self, context):
        """
        @type context: clarity_ext.driverfile.DriverFileContext

        :param context: The context the extension is running in. Can be used to access
                        the plate etc.
        :return: None
        """
        self.context = context
        # TODO: Use full namespace of the implementing extension class instead
        self.logger = logging.getLogger(self.__class__.__module__)

    @abstractmethod
    def content(self):
        """Yields the output lines of the file"""
        pass

    @abstractmethod
    def filename(self):
        """Returns the name of the file"""
        pass

    @abstractmethod
    def integration_tests(self):
        """Returns `DriverFileTest`s that should be run to validate the code"""
        pass

    def handle_validation(self, validation_results):
        # TODO: Move this code to a validation service
        # TODO: Communicate this to the LIMS rather than throwing an exception
        results = list(validation_results)
        #warnings = [result for result in results if result.type == ValidationType.WARNING]
        #errors = [result for result in results if result.type == ValidationType.ERROR]
        report = [repr(result) for result in results]
        if len(results) > 0:
            raise ValueError("Validation errors: ".format(os.path.sep.join(report)))


class DriverFileTest:
    """Represents data needed to test a driver file against a running LIMS server"""
    def __init__(self, step, out_file):
        self.step = step
        self.out_file = out_file

