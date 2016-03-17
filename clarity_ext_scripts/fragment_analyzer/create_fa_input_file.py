from clarity_ext.extensions import DriverFileExt, DriverFileTest
import datetime


class Extension(DriverFileExt):
    """
    Creates an input file for the Fragment Analyzer.
    """

    def filename(self):
        """Returns the name of the file to be uploaded"""
        today = datetime.date.today()
        prefix = today.strftime("%y%m%d")
        return "{}_{}.{}".format(prefix, "FA_input", "txt")

    def content(self):
        """Yields the lines to be written to the file"""
        yield "key,sample"
        for well in self.context.plate.list_wells(self.context.plate.DOWN_FIRST):
            yield "{}:{},{}".format(well.row, well.col, well.content or "0")

    def integration_tests(self):
        """Returns metadata for one or more integration test to run against the server"""
        yield DriverFileTest(step="24-3144", out_file="92-5243")

