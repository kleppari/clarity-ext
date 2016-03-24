from clarity_ext.extensions import ResultFilesExt
from clarity_ext.domain import Plate
from clarity_ext.pdf import PdfSplitter


class Extension(ResultFilesExt):
    def generate(self):
        """
        Splits a PDF file in the following format:
          * 10 pages skipped
          * Samples in the order A1, B1 (DOWN_FIRST)
        into separate pdf files
        """
        # The context has access to a local version of the in file (actually downloaded if needed):
        shared_file = self.context.local_shared_file

        page = 10  # Start on page 10 (zero indexed)
        splitter = PdfSplitter(shared_file)

        # Go through each well in the plate, splitting
        for well in self.context.plate.enumerate_wells(order=Plate.DOWN_FIRST):
            if well.artifact_id:
                self.logger.debug("{} is on page {}".format(well, page + 1))
                result_file_key = well.artifact_id
                filename = "{}_{}.pdf".format(result_file_key, well.get_key().replace(":", "_"))
                splitter.split(page, filename)
            page += 1

    def integration_tests(self):
        # NOTE: It's not possible to query for the output files in order.
        # If it was, we could return an index instead of the ID here
        yield self.test("24-3649", "92-7408")

