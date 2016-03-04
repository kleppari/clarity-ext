import click
import logging
import requests_cache
from clarity_ext.integration import IntegrationTestService
from clarity_ext.driverfile import DriverFileService
import yaml

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
    if cache:
        click.echo("Running with the cache '{}'. If the requests exist in the cache, they will be used".
                   format(cache))
        requests_cache.install_cache(cache)
    logging.basicConfig(level=level)


@main.command("integration-config")
@click.argument("config")
def integration_config(config):
    """Parses and prints out the configuration"""
    integration_svc = IntegrationTestService()
    print integration_svc.report_config(config)


@main.command("integration-run")
#@click.argument("config")
@click.argument("module")
@click.option("--root", default=".")
@click.option("--force/--noforce", default=False)
def integration_run(module, root, force):
    """
    Runs all scripts as they are configured in the config file, if a run doesn't already exist.

    Delete the test run folder for running again.

    :param config: The config file (YAML). Take a look at ./sites/sample.yml for a sample
    :return:
    """
    integration_svc = IntegrationTestService()
    integration_svc.run(module, root, force)



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
@click.argument("pid")
@click.argument("script")
@click.option("--commit/--no-commit", default=False)
@click.option("--path", default=".")
def driverfile(pid, script, commit, path):
    """
    Generates a file based on the pid (current step id) and a python script.

    The script will be executed inside a sandbox that has already set up.

    It has access to the following (may be lazily materialized):
    TODO: Document the context

    When hooked up to the LIMS, always set commit to True. When testing locally
    it should not be set.
    """
    click.echo('Generating driver file: pid={}, script={}, commit={}'.format(pid, script, commit))

    # TODO: Provide file caching for development mode
    svc = DriverFileService(pid, script, path)
    svc.execute(commit)



if __name__ == "__main__":
    main()
