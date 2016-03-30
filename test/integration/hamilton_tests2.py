# Unit test the output of the dilution script, generating driver file for Hamilton
# Using the utility in dilute_filer_reader
# Hamilton tests 2 utilize a process which have a target plate

import unittest
from clarity_ext.utility.hamilton_driver_file_reader import HamiltonReader as FileReader
from clarity_ext.utility.hamilton_driver_file_reader import HamiltonColumnReference as ColumnRef
from clarity_ext_scripts.dilution.create_hamilton_dilution import Extension
from clarity_ext.driverfile import DriverFileContext
from genologics.lims import Lims
from genologics.epp import attach_file
from genologics.config import BASEURI, USERNAME, PASSWORD
from genologics.entities import *
from clarity_ext.utils import use_requests_cache

TEST_PROCESS_URI = "https://lims-staging.snpseq.medsci.uu.se/api/v2/processes/24-3643"
SAMPLE1 = "EdvardProv60"
SAMPLE2 = "EdvardProv61"
SAMPLE3 = "EdvardProv62"
SAMPLE4 = "EdvardProv63"


class HamiltonTests(unittest.TestCase):

    def setUp(self):
        use_requests_cache("cache")
        self.lims = Lims(BASEURI, USERNAME, PASSWORD)
        self.lims.check_version()
        process = Process(self.lims, TEST_PROCESS_URI)
        context = DriverFileContext(process, advanced=self)
        extension = Extension(context)
        driver_file_contents = "\n".join([row_ for row_ in extension.content()])
        self.hamilton_reader = FileReader(driver_file_contents)
        self.column_ref = ColumnRef()

    # @unittest.skip("")
    def test_import_hamilton_reader(self):
        self.assertIsNotNone(self.hamilton_reader,
                             "Hamilton reader is not initialized")

    # @unittest.skip("")
    def test_number_columns(self):
        number_cols = len(self.hamilton_reader.matrix[0])
        self.assertEqual(number_cols, 7,
                         "Number columns not correct")

    # @unittest.skip("")
    def test_number_rows(self):
        number_rows = len(self.hamilton_reader.matrix)
        self.assertEqual(number_rows, 4,
                         "Number rows not correct\n{}"
                         .format(self.hamilton_reader.matrix))

    # @unittest.skip("")
    def test_volume_sample(self):
        contents = self.hamilton_reader.dict_matrix[SAMPLE1][self.column_ref.volume_sample]
        self.assertEqual(float(contents), 14.9,
                         "Volume from sample value is not right\n{}"
                         .format(self.hamilton_reader.dict_matrix))

    # @unittest.skip("")
    def test_volume_buffer(self):
        contents = self.hamilton_reader.dict_matrix[SAMPLE1][self.column_ref.volume_buffer]
        self.assertEqual(float(contents), 5.1,
                         "Volume from buffer value is not right\n{}"
                         .format(self.hamilton_reader.dict_matrix))

    # @unittest.skip("")
    def test_target_well_position(self):
        contents = self.hamilton_reader.dict_matrix[SAMPLE4][self.column_ref.target_well_pos]
        self.assertEqual(int(contents), 69,
                         "Target well position is not right")

    # @unittest.skip("")
    def test_target_plate_position(self):
        contents = self.hamilton_reader.dict_matrix[SAMPLE1][self.column_ref.target_plate_pos]
        self.assertEqual(contents, "END1",
                         "Target plate position is not right")

    # @unittest.skip("")
    def test_target_plate_position2(self):
        contents = self.hamilton_reader.dict_matrix[SAMPLE4][self.column_ref.target_plate_pos]
        self.assertEqual(contents, "END2",
                         "Target plate position is not right")

    # @unittest.skip("")
    def test_source_well_position(self):
        contents = self.hamilton_reader.dict_matrix[SAMPLE3][self.column_ref.source_well_pos]
        self.assertEqual(int(contents), 50,
                         "Source well position is not right, sample = {}, contents = {}\n{}"
                         .format(SAMPLE3, contents, self.hamilton_reader.dict_matrix))

    def test_source_well_position2(self):
        contents = self.hamilton_reader.dict_matrix[SAMPLE1][self.column_ref.source_well_pos]
        self.assertEqual(int(contents), 36,
                         "Source well position is not right, sample = {}, contents = {}\n{}"
                         .format(SAMPLE1, contents, self.hamilton_reader.dict_matrix))

    def test_source_plate_position(self):
        contents = self.hamilton_reader.dict_matrix[SAMPLE1][self.column_ref.source_plate_pos]
        self.assertEqual(contents, "DNA1",
                         "Source plate position is not right, sample = {}, contents = {}\n{}"
                         .format(SAMPLE1, contents, self.hamilton_reader.dict_matrix))

    def test_source_plate_position2(self):
        contents = self.hamilton_reader.dict_matrix[SAMPLE2][self.column_ref.source_plate_pos]
        self.assertEqual(contents, "DNA2",
                         "Source plate position is not right, sample = {}, contents = {}\n{}"
                         .format(SAMPLE2, contents, self.hamilton_reader.dict_matrix))

if __name__ == "__main__":
    unittest.main()