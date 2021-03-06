from __future__ import print_function
import importlib
import os
import sys
import codecs
import shutil
from clarity_ext.driverfile import DriverFileService, ResponseFileService
from clarity_ext.driverfile import OSService
from context import ExtensionContext
import clarity_ext.utils as utils
from abc import ABCMeta, abstractmethod
import logging
import difflib
from clarity_ext.utils import lazyprop
from clarity_ext import ClaritySession
from clarity_ext.repository import StepRepository
from clarity_ext.service import ArtifactService
from test.integration.integration_test_service import IntegrationTest
from clarity_ext.repository.step_repository import DEFAULT_UDF_MAP
from clarity_ext.service.validation_service import ValidationService
from jinja2 import Template


# Defines all classes that are expected to be extended. These are
# also imported to the top-level module

# TODO: use Python 3 and add typing hints


class ExtensionService(object):

    RUN_MODE_TEST = "test"
    RUN_MODE_FREEZE = "freeze"
    RUN_MODE_EXEC = "exec"

    # TODO: It would be preferable to have all cached data in a subdirectory, needs a patch in requests-cache
    CACHE_NAME = ".http_cache"
    CACHE_ARTIFACTS_DIR = ".cache"

    PRODUCTION_LOGS_DIR = "/opt/clarity-ext/logs"
    PRODUCTION_LOG_NAME = "extensions.log"

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    @classmethod
    def initialize_logging(cls, level):
        """
        Initializes logging for the application. Should be called once in the entry point.

        Everything is logged to a console handler. By convention, if the directory "/opt/clarity-ext/logs" exists,
        the logger will also log to that.
        """
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger = logging.getLogger('')
        root_logger.addHandler(console_handler)
        root_logger.setLevel(level)

        if os.path.exists(cls.PRODUCTION_LOGS_DIR):
            file_name = os.path.join(cls.PRODUCTION_LOGS_DIR, cls.PRODUCTION_LOG_NAME)
            rotating_handler = logging.handlers.RotatingFileHandler(file_name, maxBytes=10 * (2**20), backupCount=5)
            rotating_handler.setFormatter(formatter)
            root_logger.addHandler(rotating_handler)

    def _run_path(self, args, module, mode, config):
        if mode == self.RUN_MODE_EXEC:
            return config["exec_root_path"]
        elif mode == self.RUN_MODE_TEST or mode == self.RUN_MODE_FREEZE:
            root = config["test_root_path"] if mode == self.RUN_MODE_TEST else config["frozen_root_path"]
            # When testing or freezing, we need subdirectories based on the modules path
            # so they don't get mixed up:
            module_parts = module.split(".")[1:]
            path = os.path.sep.join(module_parts)
            return os.path.join(root, path, args["pid"], "run-" + mode)
        else:
            raise ValueError("Unexpected mode")

    def _parse_run_argument(self, in_argument):
        if isinstance(in_argument, IntegrationTest):
            return in_argument.run_argument_dict
        if isinstance(in_argument, str):
            return {"pid": in_argument}
        elif isinstance(in_argument, dict):
            return in_argument
        else:
            return in_argument.__dict__

    def _artifact_service(self, pid):
        session = ClaritySession.create(pid)
        step_repo = StepRepository(session, DEFAULT_UDF_MAP)
        return ArtifactService(step_repo)

    def execute(self, module, mode, run_arguments_list=None, config=None, artifacts_to_stdout=True,
                print_help=True, use_cache=None):
        """
        Given a module, finds the extension in it and runs all of its integration tests
        :param module:
        :param mode: One of: exec, test, freeze, validate
        :param run_arguments: A dictionary with arguments. If not provided, the
            extensions integration_tests will be used. A list of dicts can be provided for
            multiple runs.
            A string of key value pairs can also be sent.
        :param config: A configuration directory with additional parameters, such as location of directories
        :param artifacts_to_stdout: Set to true if all artifacts created should be echoed to stdout
        :param use_cache: True if the cache should be used. Defaults to true if running in test mode.
        :return:
        """
        if config is None:
            config = {
                "test_root_path": "./clarity_ext_scripts/int_tests",
                "frozen_root_path": "../clarity-ext-frozen",
                "exec_root_path": "."
            }

        if use_cache is None:
            use_cache = mode == self.RUN_MODE_TEST

        if use_cache:
            self.logger.info("Using cache {}".format(self.CACHE_NAME))
            utils.use_requests_cache(self.CACHE_NAME)

        if isinstance(run_arguments_list, str) or isinstance(run_arguments_list, unicode):
            arguments = run_arguments_list.split(" ")
            key_values = (argument.split("=") for argument in arguments)
            run_arguments_list = {key: value for key, value in key_values}

        module_obj = importlib.import_module(module)
        extension = getattr(module_obj, "Extension")
        instance = extension(None)

        if not run_arguments_list and (mode == self.RUN_MODE_TEST or mode == self.RUN_MODE_FREEZE):
            for integration_test in instance.integration_tests():
                if isinstance(integration_test, IntegrationTest) and integration_test.preparer:
                    artifact_service = self._artifact_service(integration_test.pid())
                    integration_test.preparer.prepare(artifact_service)

            run_arguments_list = map(self._parse_run_argument, instance.integration_tests())
            if len(run_arguments_list) == 0:
                print("WARNING: No integration tests defined. Not able to test.")
                return
        elif not isinstance(run_arguments_list, list):
            run_arguments_list = [run_arguments_list]

        if mode in [self.RUN_MODE_TEST, self.RUN_MODE_EXEC]:
            if mode == self.RUN_MODE_TEST and print_help:
                print("To execute from Clarity:")
                print("  clarity-ext extension --args '{}' {} {}".format(
                    "pid={processLuid}",
                    module, self.RUN_MODE_EXEC))
                print("To freeze the latest test run (set as reference data for future validations):")
                print("  clarity-ext extension {} {}".format(
                    module, self.RUN_MODE_FREEZE))

            for run_arguments in run_arguments_list:
                path = self._run_path(run_arguments, module, mode, config)
                frozen_path = self._run_path(run_arguments, module, self.RUN_MODE_FREEZE, config)

                if mode == self.RUN_MODE_TEST:
                    http_cache_file = '{}.sqlite'.format(self.CACHE_NAME)

                    # Remove everything but the cache files
                    if os.path.exists(path):
                        utils.clean_directory(path, [http_cache_file, self.CACHE_ARTIFACTS_DIR])
                    else:
                        os.makedirs(path)

                    # Copy the cache file from the frozen path if available:
                    frozen_http_cache_file = os.path.join(frozen_path, http_cache_file)
                    frozen_cache_dir = os.path.join(frozen_path, self.CACHE_ARTIFACTS_DIR)
                    if os.path.exists(frozen_http_cache_file):
                        self.logger.info("Frozen http cache file exists and will be used")
                        shutil.copy(frozen_http_cache_file, path)

                    if os.path.exists(frozen_cache_dir):
                        if os.path.exists(os.path.join(path, self.CACHE_ARTIFACTS_DIR)):
                            shutil.rmtree(os.path.join(path, self.CACHE_ARTIFACTS_DIR))
                        self.logger.info("Frozen cache directory exists and will be used")
                        shutil.copytree(frozen_cache_dir, os.path.join(path, self.CACHE_ARTIFACTS_DIR))

                old_dir = os.getcwd()
                os.chdir(path)

                self.logger.info("Executing at {}".format(os.path.abspath(path)))
                cache_artifacts = mode == self.RUN_MODE_TEST
                context = ExtensionContext.create(run_arguments["pid"], cache=cache_artifacts)
                instance = extension(context)
                os_service = OSService()
                if issubclass(extension, DriverFileExtension):
                    file_svc = DriverFileService.create_file_service(
                        instance, instance.shared_file(), self.logger, os_service)
                    commit = mode == self.RUN_MODE_EXEC
                    file_svc.execute(commit=commit, artifacts_to_stdout=artifacts_to_stdout)
                elif issubclass(extension, GeneralFileExtension):
                    file_svc = ResponseFileService.create_file_service(instance, self.logger, os_service)
                    file_svc.execute(commit=False, artifacts_to_stdout=artifacts_to_stdout)
                elif issubclass(extension, GeneralExtension):
                    instance.execute()
                else:
                    raise NotImplementedError("Unknown extension type")
                context.cleanup()

                os.chdir(old_dir)

                if os.path.exists(frozen_path) and file_svc:
                    test_info = RunDirectoryInfo(path, file_svc)
                    frozen_info = RunDirectoryInfo(frozen_path, file_svc)
                    diff_report = list(test_info.compare(frozen_info))
                    if len(diff_report) > 0:
                        msg = []
                        for type, key, diff in diff_report:
                            msg.append("{} ({})".format(key, type))
                            msg.append(diff)
                        raise ResultsDifferFromFrozenData("\n".join(msg))
                else:
                    print("No frozen data found at {}".format(frozen_path))

        elif mode == self.RUN_MODE_FREEZE:
            frozen_root_path = config.get("frozen_root_path", ".")
            print("Freezing data (requests, responses and result files/hashes) to {}"
                  .format(frozen_root_path))

            for run_arguments in run_arguments_list:
                test_path = self._run_path(run_arguments, module, self.RUN_MODE_TEST, config)
                frozen_path = self._run_path(run_arguments, module, self.RUN_MODE_FREEZE, config)
                print(test_path, "=>", frozen_path)
                if os.path.exists(frozen_path):
                    self.logger.info("Removing old frozen directory '{}'".format(frozen_path))
                    shutil.rmtree(frozen_path)
                shutil.copytree(test_path, frozen_path)
        else:
            raise NotImplementedError("Mode '{}' is not implemented".format(mode))


class ResultsDifferFromFrozenData(Exception):
    pass


class RunDirectoryInfo(object):
    """
    Provides methods to query a particular result directory for its content

    Used to compare two different runs, e.g. a current test and a frozen test
    """
    def __init__(self, path, file_service):
        self.path = path
        self.uploaded_path = os.path.join(self.path, "uploaded")
        self.file_service = file_service

    @lazyprop
    def uploaded_files(self):
        """Returns a dictionary of uploaded files indexed by key"""
        ret = dict()
        if not os.path.exists(self.uploaded_path):
            return ret
        for file_name in os.listdir(self.uploaded_path):
            assert os.path.isfile(os.path.join(self.uploaded_path, file_name))
            file_key = self.file_service.file_key(file_name)
            if file_key:
                if file_key in ret:
                    raise Exception("More than one file with the same prefix")
                ret[file_key] = os.path.abspath(os.path.join(self.uploaded_path, file_name))
            else:
                raise Exception("Unexpected file name {}, should start with Clarity ID".format(file_name))
        return ret

    def compare_files(self, a, b):
        with open(a, 'r') as f:
            fromlines = f.readlines()
        with open(b, 'r') as f:
            tolines = f.readlines()

        diff = list(difflib.unified_diff(fromlines, tolines, a, b))
        return diff

    def compare(self, other):
        """Returns a report for the differences between the two runs"""
        a_keys = set(self.uploaded_files.keys())
        b_keys = set(other.uploaded_files.keys())
        if a_keys != b_keys:
            raise Exception("Keys differ: {} != {}".format(a_keys, b_keys))

        for key in self.uploaded_files:
            path_a = self.uploaded_files[key]
            path_b = other.uploaded_files[key]
            diff = self.compare_files(path_a, path_b)
            if len(diff) > 0:
                yield ("uploaded", key, "".join(diff[0:10]))


class GeneralExtension(object):
    """
    An extension that must implement the `execute` method
    """
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
        self.response = None
        self.validation_service = ValidationService(
            context=context, logger=self.logger)

    def handle_validation(self, validation_results):
        return self.validation_service.handle_validation(validation_results)

    @abstractmethod
    def integration_tests(self):
        """Returns `DriverFileTest`s that should be run to validate the code"""
        pass

    def test(self, pid):
        """Creates a test instance suitable for this extension"""
        return ExtensionTest(pid=pid)


class GeneralFileExtension(GeneralExtension):
    __metaclass__ = ABCMeta

    def newline(self):
        return "\n"

    @abstractmethod
    def filename(self):
        """Returns the name of the file
        (containing either response from update, or a file to be uploaded to lims)"""
        pass


class DriverFileExtension(GeneralFileExtension):
    __metaclass__ = ABCMeta

    @abstractmethod
    def shared_file(self):
        """Returns the name of the shared file that should include the newly generated file"""
        return "Sample List"

    @abstractmethod
    def content(self):
        """Yields the output lines of the file, or the response at updates"""
        pass


class SampleSheetExtension(DriverFileExtension):
    """
    Provides helper methods for creating a CSV
    """
    __metaclass__ = ABCMeta

    NONE = "<none>"

    def __init__(self, context):
        super(SampleSheetExtension, self).__init__(context)
        self.column_count = 9

    def header(self, name):
        return self.line("[{}]".format(name))

    def udf(self, name):
        """Returns the UDF if available, otherwise self.NONE. Provided for readability"""
        return self.context.udfs.get(name, self.NONE)

    def line(self, *args):
        """
        Generates one line of the sample sheet, CSV formatted

        Example: Calling with self.line("a", "b") will produce 'a,b,,,,,,,'
        """
        # TODO: The example shows commas in each line. Is that actually required?
        arg_list = list(args) + [""] * (self.column_count - len(args))
        return ",".join(map(str, arg_list))


class TemplateExtension(DriverFileExtension):
    """
    Creates driver files from templates
    """
    __metaclass__ = ABCMeta

    NONE = "<none>"

    def __init__(self, context):
        super(TemplateExtension, self).__init__(context)
        file_name = sys.modules[self.__module__].__file__
        self.template_dir = os.path.dirname(file_name)
        self.module_name = self.__module__.split(".")[-1]

        # Search for a template with the same name as the module:
        candidates = list()
        for candidate_file in os.listdir(self.template_dir):
            if candidate_file.startswith(self.module_name + ".templ."):
                candidates.append(candidate_file)
        if len(candidates) > 1:
            raise ValueError("More than one template file found: ", ",".join(candidates))
        self.default_template_name = candidates[0] if len(candidates) == 1 else None

    @property
    def template_path(self):
        """Returns the name of the template. By default, it will use the convention of returning the template
        named `<current module>.templ.*` if one is found."""
        return os.path.join(self.template_dir, self.default_template_name)

    def content(self):
        with open(self.template_path, 'r') as fs:
            text = fs.read()
            text = codecs.decode(text, "utf-8")
            template = Template(text)
            rendered = template.render(ext=self)
            return rendered


class ExtensionTest(object):
    def __init__(self, pid):
        self.pid = pid
