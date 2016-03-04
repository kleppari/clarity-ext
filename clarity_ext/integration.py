import os
import subprocess
import yaml
import shutil
import re
import logging



# Creates an integration test config file based on convention
# i.e. position and contents of the script classes themselves.
# TODO: Move all of this metaprogramming stuff to its own class
class ConfigFromConventionProvider:

    @classmethod
    def _enumerate_modules(cls, root_name):
        import importlib
        import pkgutil
        root = importlib.import_module(root_name)
        for loader, module_name, is_pkg in pkgutil.walk_packages(root.__path__):
            module = loader.find_module(module_name).load_module(module_name)
            yield module

    @classmethod
    def _get_config_by_convention(cls, root):
        def enumerate():
            for module in cls._enumerate_modules(root):
                # Ignore modules that don't have a class named Extension:
                if hasattr(module, "Extension"):
                    entry = dict()
                    entry["name"] = module.__name__
                    extension_cls = getattr(module, "Extension")
                    from clarity_ext.extensions import DriverFileExt

                    # NOTE: For some reason, the root does not get added to the enumerated modules
                    entry["script"] = "{}.{}".format(root, module.__name__)

                    # The command is based on the type:
                    if issubclass(extension_cls, DriverFileExt):
                        entry["cmd"] = "driverfile"

                    # Check if the module has more metadata:
                    entry["tests"] = []
                    if hasattr(module, "TEST_PIDS"):
                        test_pids = getattr(module, "TEST_PIDS")
                        if isinstance(test_pids, str):
                            test_pids = [test_pids]
                        for pid in test_pids:
                            entry["tests"].append({"pid": pid})
                    yield entry

        return list(enumerate())




class IntegrationTestService:
    CACHE_NAME = "test_run_cache"

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.CACHE_FULL_NAME = "{}.sqlite".format(self.CACHE_NAME)

    @staticmethod
    def _test_validate_directory(config_entry, pid):
        return os.path.join(".", "runs", config_entry["name"], pid, "test-validate")

    @staticmethod
    def _test_run_directory(config_entry, pid):
        return os.path.join(".", "runs", config_entry["name"], pid, "test-run")

    @staticmethod
    def _test_frozen_directory(config_entry, pid):
        return os.path.join(".", "runs", config_entry["name"], pid, "test-frozen")

    @staticmethod
    def _get_config(path):
        stream = file(path, 'r')
        return yaml.load(stream)

    def _execute_test(self, entry, test, script_root, directory):
        os.chdir(directory)
        cmd = entry["cmd"]
        pid = test["pid"]
        script = os.path.join(script_root, entry["script"])
        script = os.path.abspath(script)
        subprocess.call(["clarity-ext", "--cache", self.CACHE_NAME, cmd, pid, script])

    def _run(self, entry, script_root, force):
        print "Running test '{}'".format(entry["name"])
        tests = entry["tests"]
        if not tests:
            print "- No tests are configured. Ignoring"
        else:
            for test in tests:
                pid = test["pid"]
                # Check if we already have a run for this:
                test_run_directory = self._test_run_directory(entry, pid)
                if os.path.exists(test_run_directory):
                    if force:
                        print "We already got a test run folder at {}. Recreating it.".format(test_run_directory)
                        shutil.rmtree(test_run_directory)
                    else:
                        print "Test results already exist and force is not set to True"
                        continue

                print "Running configured action"
                os.makedirs(test_run_directory)
                self._execute_test(entry, test, script_root, test_run_directory)

    def run(self, module, script_root, force=False):
        """
        Runs a new run for all the extensions in the config file

        Ignores runs that already have a run file. Delete their directory
        or run with force to rerun.

        :param config:
        :param script_root:
        :param force:
        :return:
        """
        script_root = os.path.abspath(script_root)
        config = ConfigFromConventionProvider._get_config_by_convention(module)
        for entry in config:
            self._run(entry, script_root, force)

    def _freeze_test(self, entry, test):
        source = self._test_run_directory(entry, test["pid"])

        if not os.path.exists(source):
            raise FreezingBeforeRunning()

        target = self._test_frozen_directory(entry, test["pid"])
        print "Freezing test {} => {}".format(source, target)
        if os.path.exists(target):
            print "Target already exists, removing it"
            shutil.rmtree(target)
        shutil.copytree(source, target)

    def _freeze_entry(self, entry, test_filter):
        print "Freezing {}. Freezing test={}".format(entry, test_filter)
        tests = entry["tests"]
        tests_to_freeze = [test for test in tests if re.match(test_filter, test["pid"])]
        print tests_to_freeze
        for test in tests_to_freeze:
            self._freeze_test(entry, test)

    def _enumerate_runs(self, config_obj):
        """
        Given a config file, enumerates all the available tests in it
        """
        for entry in config_obj:
            for test in entry["tests"]:
                directory = self._test_run_directory(entry, test["pid"])
                if os.path.exists(directory):
                    yield entry, test

    def _enumerate_frozen_tests(self, config_obj):
        for entry in config_obj:
            for test in entry["tests"]:
                directory = self._test_frozen_directory(entry, test["pid"])
                if os.path.exists(directory):
                    yield entry, test

    def freeze(self, module, name=None, test_filter=".*"):
        """
        Freezes the tests. Call this when you're happy with the results of calling "run".

        :param config:
        :return:
        """
        config_obj = ConfigFromConventionProvider._get_config_by_convention(module)
        if name is None:
            # freeze all tests that have a run
            print "NOTE: Freezing without a filter. All runs found will be frozen."
            for entry, test in self._enumerate_runs(config_obj):
                self._freeze_test(entry, test)
        else:
            entry = [entry for entry in config_obj if entry["name"] == name][0]
            self._freeze_entry(entry, test_filter)

    def validate(self, module):
        """
        Runs the tests on the frozen tests. The idea is that this should run (at least) on every official build,
        thus validating every script against a known state

        :param config:
        :return:
        """
        config_obj = ConfigFromConventionProvider._get_config_by_convention(module)
        for entry, test in self._enumerate_frozen_tests(config_obj):
            validate_directory = self._test_validate_directory(entry, test["pid"])
            frozen_directory = self._test_frozen_directory(entry, test["pid"])
            if os.path.exists(validate_directory):
                logging.debug("Validation folder exists. Removing it.")
                shutil.rmtree(validate_directory)
            os.makedirs(validate_directory)
            cache_file = os.path.join(frozen_directory, self.CACHE_FULL_NAME)
            shutil.copy(cache_file, validate_directory)

    def report_config(self, config):
        """Parses the config and prints out a summary"""
        obj = self._get_config(config)
        report = list()
        report.append("Scripts:")
        for entry in obj:
            report.append(" - {}".format(entry["name"]))
        return "\n".join(report)

    @staticmethod
    def config_by_convention(module):
        """
        Returns a config object based on convention, i.e. by searching for all
        extensions in the module and all submodules.
        """
        pass


class FreezingBeforeRunning(Exception):
    """Thrown when the user tries to freeze a state before doing an initial run"""
    pass


class ValidatingBeforeFreezing(Exception):
    """Thrown when the user tries to validate before freezing"""
    pass
