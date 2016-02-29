import click
import clarity_ext.csv_generator

@click.group()
def main():
    pass

@main.command()
@click.argument("pid")
@click.option("--commit/--no-commit", default=False)
def driverfile(pid, commit):
    """
    Generates a file based on the pid (current step id) and a config file (YAML)

    When hooked up to the LIMS, always set commit to True. When testing locally
    it should not be set.
    """
    click.echo('PID={}, commit={}'.format(pid, commit))

