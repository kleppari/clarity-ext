import unittest
from clarity_ext.dilution import DILUTION_WASTE_VOLUME
from mock import MagicMock
from clarity_ext.dilution import DilutionScheme
from test.unit.clarity_ext import helpers


class UpdateFieldsForDilutionTests(unittest.TestCase):

    def setUp(self):
        repo = MagicMock()
        svc = helpers.mock_two_containers_artifact_service()
        self.dilution_scheme = DilutionScheme(svc, "Hamilton")

        analyte_pair_by_dilute = self.dilution_scheme.analyte_pair_by_transfer
        for dilute in self.dilution_scheme.transfers:
            # Make preparation, fetch the analyte to be updated
            source_analyte = analyte_pair_by_dilute[dilute].input_artifact
            destination_analyte = analyte_pair_by_dilute[
                dilute].output_artifact

            # Update fields for analytes
            source_analyte.volume = dilute.source_initial_volume - \
                dilute.requested_volume - DILUTION_WASTE_VOLUME

            destination_analyte.concentration = dilute.requested_concentration

            destination_analyte.volume = dilute.requested_volume

    def test_source_volume_update_1(self):
        dilute = self.dilution_scheme.transfers[0]
        expected = 9.0
        outcome = self.dilution_scheme.analyte_pair_by_transfer[
            dilute].input_artifact.volume
        print(dilute.sample_name)
        self.assertEqual(expected, outcome)

    def test_source_volume_update_all(self):
        source_volume_sum = 0
        for dilute in self.dilution_scheme.transfers:
            outcome = self.dilution_scheme.analyte_pair_by_transfer[
                dilute].input_artifact.volume
            source_volume_sum += outcome
        expected_sum = 96.0
        self.assertEqual(expected_sum, source_volume_sum)