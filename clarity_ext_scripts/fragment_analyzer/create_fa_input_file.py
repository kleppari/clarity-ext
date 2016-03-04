from clarity_ext.extensions import DriverFileExt
import datetime

# The following variables can be set to enable automatic testing
# If skipped, there will be no automatic testing for this class.

# Use TEST_PIDS to set the steps to integration test against
TEST_PIDS = ["24-1205", "24-1501"]  # Can also be set to a list


class Extension(DriverFileExt):
    def create(self):
        today = datetime.date.today()
        prefix = today.strftime("%y%m%d")
        self.context.outfile.name = "{}_{}.{}".format(prefix, "FA_input", "csv")
        self.context.outfile.write_line("key,sample")

        for well in self.context.plate.list_wells(self.context.plate.DOWN_FIRST):
            line = "{}:{},{}".format(well.row, well.col, well.content or "0")
            self.context.outfile.write_line("{}".format(line))
