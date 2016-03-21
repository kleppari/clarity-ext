import importlib
import os
import shutil
from clarity_ext.driverfile import DriverFileService
import logging

# Defines all classes that are expected to be extended. These are
# also imported to the top-level module

# TODO: use Python 3 and add typing hints

from abc import ABCMeta, abstractmethod
import logging


class ExtensionService:

    RUN_MODE_TEST = "test"
    RUN_MODE_FREEZE = "freeze"

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)

    def _test_path_for_test(self, test, module, mode):
        module_parts = module.split(".")[1:]
        path = os.path.sep.join(module_parts)
        return os.path.join(path, test.step, "run-" + mode)

    """TODO: MOVE TO extensions.py"""
    def execute(self, module, mode, artifacts_to_stdout=False):
        """
        Given a module, finds the extension in it and runs all of its integration tests
        :param module:
        :param mode: One of exec, test-run, freeze, validate
        :return:
        """
        module_obj = importlib.import_module(module)
        extension = getattr(module_obj, "Extension")
        instance = extension(None)
        integration_tests = list(instance.integration_tests())

        if mode == self.RUN_MODE_TEST:
            for test in integration_tests:
                path = self._test_path_for_test(test, module, mode)
                # Remove everything but the cache file

                # We might need to clean up the directory:
                if os.path.exists(path):
                    to_remove = (os.path.join(path, file_or_dir)
                                 for file_or_dir in os.listdir(path)
                                 if file_or_dir != 'cache')
                    for item in to_remove:
                        if os.path.isdir(item):
                            shutil.rmtree(item)
                        else:
                            os.remove(item)
                else:
                    os.makedirs(path)

                os.chdir(path)

                if issubclass(extension, DriverFileExt):
                    driver_file_svc = DriverFileService(test.step, module, ".", test.out_file)
                    driver_file_svc.execute(artifacts_to_stdout=True)
                else:
                    raise NotImplementedError("Unknown extension")
        elif mode == self.RUN_MODE_FREEZE:
            for test in integration_tests:
                frozen_path = self._test_path_for_test(test, module, self.RUN_MODE_FREEZE)
                test_path = self._test_path_for_test(test, module, self.RUN_MODE_TEST)
                print frozen_path, "=>", test_path
                if os.path.exists(frozen_path):
                    self.logger.info("Removing old frozen directory '{}'".format(frozen_path))
                    shutil.rmtree(frozen_path)

                shutil.copytree(test_path, frozen_path)
        else:
            # TODO: Execute using the step/out_file provided via the command line
            raise NotImplementedError("coming soon")


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
        report = [repr(result) for result in results]
        if len(results) > 0:
            raise ValueError("Validation errors: ".format(os.path.sep.join(report)))


class DriverFileTest:
    """Represents data needed to test a driver file against a running LIMS server"""
    def __init__(self, step, out_file):
        self.step = step
        self.out_file = out_file

