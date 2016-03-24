# Calculates dilute volumes, volume from sample and volume from buffer
# for each analyte within a given process.
# User provide target concentration and target volume for each analyte.
# Give error if any volume is less than 2 ul
# Give error if any volume exceeds 51 ul

from clarity_ext.extensions import DriverFileExt, DriverFileTest


class Extension(DriverFileExt):
    """Calculates dilute volumes and export to dilute driver file"""

    def content(self):
        validation_results = self.context.dilution_scheme.validate()

        # Move control over to the framework when it comes to validation_results:
        # For now it just throw an error if there is anything there, but
        # we will change it to doing something more complex (TODO)
        self.handle_validation(validation_results)

        for dilute in self.context.dilution_scheme.dilutes:
            row = [dilute.sample_name,
                   "WellPosSource",
                   "PlatePosSource",
                   "{:.1f}".format(dilute.sample_volume),
                   "{:.1f}".format(dilute.buffer_volume),
                   "{}".format(dilute.target_well_index),
                   dilute.target_container]
            yield "\t".join(row)

    def filename(self):
        return "dilution"  # TODO

    def integration_tests(self):
        # The step used during design/last iteration of this extension:
        yield DriverFileTest(step="24-3643", out_file="92-7103")
        # yield DriverFileTest(step="24-3637", out_file="92-7047")

