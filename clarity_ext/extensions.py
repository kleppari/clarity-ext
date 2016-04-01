from __future__ import print_function
import importlib
import os
import shutil
from clarity_ext.driverfile import DriverFileService

# Defines all classes that are expected to be extended. These are
# also imported to the top-level module

# TODO: use Python 3 and add typing hints

from abc import ABCMeta, abstractmethod
import logging


class ExtensionService:

    RUN_MODE_TEST = "test"
    RUN_MODE_FREEZE = "freeze"
    RUN_MODE_EXEC = "exec"
    CACHE_NAME = "http_cache"

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)

    def _run_path(self, args, module, mode):
        if mode == self.RUN_MODE_EXEC:
            return "."
        else:
            module_parts = module.split(".")[1:]
            path = os.path.sep.join(module_parts)
            return os.path.join(path, args["pid"], "run-" + mode)

    def _parse_run_argument(self, in_argument):
        if isinstance(in_argument, str):
            return {"pid": in_argument}
        elif isinstance(in_argument, dict):
            return in_argument
        else:
            return in_argument.__dict__

    def execute(self, module, mode, run_arguments_list=None):
        """
        Given a module, finds the extension in it and runs all of its integration tests
        :param module:
        :param mode: One of: exec, test, freeze, validate
        :param run_arguments: A dictionary with arguments. If not provided, the
            extensions integration_tests will be used. A list of dicts can be provided for
            multiple runs.
            A string of key value pairs can also be sent.
        :return:
        """
        from clarity_ext.utils import use_requests_cache
        if mode == self.RUN_MODE_TEST:
            self.logger.info("Using cache {}".format(self.CACHE_NAME))
            use_requests_cache(self.CACHE_NAME)

        if isinstance(run_arguments_list, str) or isinstance(run_arguments_list, unicode):
            arguments = run_arguments_list.split(" ")
            key_values = (argument.split("=") for argument in arguments)
            run_arguments_list = {key: value for key, value in key_values}

        module_obj = importlib.import_module(module)
        extension = getattr(module_obj, "Extension")
        instance = extension(None)

        if not run_arguments_list and mode == self.RUN_MODE_TEST:
            run_arguments_list = map(self._parse_run_argument, instance.integration_tests())
            if len(run_arguments_list) == 0:
                print("WARNING: No integration tests defined. Not able to test.")
                return
        elif type(run_arguments_list) is not list:
            run_arguments_list = [run_arguments_list]

        if mode in [self.RUN_MODE_TEST, self.RUN_MODE_EXEC]:
            for run_arguments in run_arguments_list:
                path = self._run_path(run_arguments, module, mode)

                if mode == self.RUN_MODE_TEST:
                    print("Rerun with:")
                    run_arguments_str = " ".join(
                        ["=".join(tuple) for tuple in run_arguments.iteritems()])
                    print("  Test: clarity-ext --cache cache extension --args '{}' {} {}".format(
                        run_arguments_str,
                        module, self.RUN_MODE_TEST))
                    # TODO: Get the index from the test
                    print("  Exec: clarity-ext extension --args '{}' {} {}".format(
                        "pid={processLuid}",
                        module, self.RUN_MODE_EXEC))

                    # Remove everything but the cache files
                    if os.path.exists(path):
                        to_remove = (os.path.join(path, file_or_dir)
                                     for file_or_dir in os.listdir(path)
                                     if file_or_dir != 'http_cache.sqlite')
                        for item in to_remove:
                            if os.path.isdir(item):
                                shutil.rmtree(item)
                            else:
                                os.remove(item)
                    else:
                        os.makedirs(path)

                    os.chdir(path)

                print("Executing at {}".format(path))

                from extension_context import ExtensionContext
                if issubclass(extension, DriverFileExtension):
                    context = ExtensionContext(run_arguments["pid"])
                    instance = extension(context)
                    driver_file_svc = DriverFileService(instance, ".")
                    commit = mode == self.RUN_MODE_EXEC
                    driver_file_svc.execute(commit=commit, artifacts_to_stdout=True)
                elif issubclass(extension, GeneralExtension):
                    # TODO: Generating the instance twice (for metadata above)
                    context = ExtensionContext(run_arguments["pid"])
                    instance = extension(context)
                    instance.execute()
                    context.cleanup()
                else:
                    raise NotImplementedError("Unknown extension")
        elif mode == self.RUN_MODE_FREEZE:
            for test in run_arguments_list:
                frozen_path = self._test_path_for_test(test, module, self.RUN_MODE_FREEZE)
                test_path = self._test_path_for_test(test, module, self.RUN_MODE_TEST)
                print(frozen_path, "=>", test_path)
                if os.path.exists(frozen_path):
                    self.logger.info("Removing old frozen directory '{}'".format(frozen_path))
                    shutil.rmtree(frozen_path)

                shutil.copytree(test_path, frozen_path)
        else:
            # TODO: Execute using the pid/shared_file provided via the command line
            raise NotImplementedError("coming soon")


class GeneralExtension:
    """
    An extension that must implement the `execute` method
    """
    __metaclass__ = ABCMeta

    def __init__(self, context):
        self.context = context
        self.logger = logging.getLogger(self.__class__.__module__)

    def log(self, msg):
        self.logger.info(msg)

    @abstractmethod
    def execute(self):
        pass

    def integration_tests(self):
        return []

    def test(self, pid):
        """Creates a test instance suitable for this extension"""
        return ResultFilesTest(pid=pid)


class DriverFileExtension:
    __metaclass__ = ABCMeta

    def __init__(self, context):
        """
        @type context: clarity_ext.driverfile.DriverFileContext

        :param context: The context the extension is running in. Can be used to access
                        the plate etc.
        :return: None
        """
        self.context = context
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

    @abstractmethod
    def shared_file(self):
        """Returns the name of the shared file that should include the newly generated file"""
        return "Sample List"

    def handle_validation(self, validation_results):
        # TODO: Move this code to a validation service
        # TODO: Communicate this to the LIMS rather than throwing an exception
        results = list(validation_results)
        report = [repr(result) for result in results]
        if len(results) > 0:
            raise ValueError("Validation errors: ".format(os.path.sep.join(report)))


class ExtensionTest:
    def __init__(self, pid):
        self.pid = pid


class DriverFileTest:
    """Represents data needed to test a driver file against a running LIMS server"""
    def __init__(self, pid, shared_file):
        self.pid = pid
        self.shared_file = shared_file


class ResultFilesTest:
    """Defines tests metadata for ResultFiles extensions"""
    def __init__(self, pid):
        self.pid = pid

