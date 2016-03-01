import click
import logging

from clarity_ext.driverfile import DriverFileService


@click.group()
@click.option("--level", default="WARN")
def main(level):
    logging.basicConfig(level=level)
    pass


@main.command()
@click.argument("pid")
@click.argument("script")
@click.option("--commit/--no-commit", default=False)
def driverfile(pid, script, commit):
    """
    Generates a file based on the pid (current step id) and a python script.

    The script will be executed inside a sandbox that has already set up.

    It has access to the following (may be lazily materialized):
        *

    When hooked up to the LIMS, always set commit to True. When testing locally
    it should not be set.
    """
    click.echo('Generating driver file: pid={}, script={}, commit={}'.format(pid, script, commit))

    # TODO: Provide file caching for development mode
    svc = DriverFileService(pid, script)
    svc.execute()
