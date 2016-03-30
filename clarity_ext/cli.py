from __future__ import print_function
import click
import logging
from clarity_ext.utils import use_requests_cache
from clarity_ext.integration import IntegrationTestService
from clarity_ext.extensions import ExtensionService


@click.group()
@click.option("--level", default="WARN")
@click.option("--cache")
def main(level, cache):
    """
    :param level: ["DEBUG", "INFO", "WARN", "ERROR"]
    :param cache: Set to a cache name if running from a cache (or caching)
                This is used to ensure reproducible and fast integration tests
    :return:
    """
    logging.basicConfig(level=level.upper())
    # TODO: Add a file based implementation for requests-cache, so we can
    # code review it (and filter) and check the cached values into the same repo.
    if cache:
        use_requests_cache(cache)

@main.command("integration-config")
@click.argument("config")
def integration_config(config):
    """Parses and prints out the configuration"""
    raise NotImplementedError("Working on convention stuff")
    integration_svc = IntegrationTestService()
    print(integration_svc.report_config(config))


@main.command("config-pycharm")
@click.argument("module")
def config_pycharm(module):
    """Generates PyCharm configuration for all scripts found"""
    from clarity_ext.pycharm import generate_pycharm_run_config
    generate_pycharm_run_config(module)


@main.command("integration-run")
@click.argument("module")
@click.option("--force/--noforce", default=False)
def integration_run(module, force):
    """
    Runs all scripts as they are configured in the config file, if a run doesn't already exist.

    Delete the test run folder for running again.

    :param config: The config file (YAML). Take a look at ./sites/sample.yml for a sample
    :return:
    """
    integration_svc = IntegrationTestService()
    integration_svc.run(module, force)
    print("Done running tests. Freeze them for future use with `clarity-ext integration-freeze {}`".format(
        module))


@main.command("integration-freeze")
@click.argument("config")
@click.option("--name")
def integration_freeze(config, name):
    """
    Freezes the results of the run. Call this when you're happy with the results of running integration-run.

    The results of this operation should be checked in to version control. Each developer and the build server
    can then validate the correctness of the scripts without having to set the LIMS system in the same state
    as it was at the time of freezing.

    :param config: The configuration file to use
    :param name: The name of the script. Points to an entry in the config file.
    :return:
    """
    integration_svc = IntegrationTestService()
    integration_svc.freeze(config, name)


@main.command("integration-validate")
@click.argument("config")
def integration_validate(config):
    """
    Validates all frozen tests, by running them on the cached request/responses
    and comparing the output between the runs.

    :param config: The configuration file to use
    :return:
    """
    integration_svc = IntegrationTestService()
    integration_svc.validate(config)


@main.command()
@click.argument("module")
@click.argument("mode")
@click.option("--args")
def extension(module, mode, args):
    """Loads the extension and executes the integration tests.

    :param mode: One of
        exec: Execute the code in normal mode
        test: Test the code locally
        freeze: Freeze an already created test (move from test-run to test-frozen)
        validate: Test the code locally, then compare with the frozen directory
    """
    extension_svc = ExtensionService()
    extension_svc.execute(module, mode, args)

if __name__ == "__main__":
    main()
