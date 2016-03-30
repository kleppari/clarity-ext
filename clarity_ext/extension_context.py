from genologics.config import BASEURI, USERNAME, PASSWORD
from genologics.lims import Lims
from genologics.entities import *
import requests
import os
from clarity_ext.utils import lazyprop
from clarity_ext.domain import *


# TODO: Use the same extension context for all extensions, throwing an exception if
# a particular feature is not available
class ExtensionContext:
    """
    Defines context objects for extensions.
    """
    def __init__(self, current_step, logger=None):
        # TODO: Add the lims property to "advanced" so that it won't be accessed accidentally?
        # TODO: These don't need to be provided in most cases
        lims = Lims(BASEURI, USERNAME, PASSWORD)
        lims.check_version()

        self.advanced = Advanced(lims)
        self.current_step = Process(lims, id=current_step)
        self.logger = logger or logging.getLogger(__name__)
        self._local_shared_files = []

    def local_shared_file(self, file_name):
        """
        Downloads the local shared file and returns the path to it on the file system.
        If the file already exists, it will not be downloaded again.

        Details:
        The downloaded files will be removed when the context is cleaned up. This ensures
        that the LIMS will not upload them by accident
        """

        # Ensure that the user is only sending in a "name" (alphanumerical or spaces)
        # File paths are not allowed
        import re
        if not re.match(r"[\w ]+", file_name):
            raise ValueError("File name can only contain alphanumeric characters, underscores and spaces")
        local_path = os.path.abspath(file_name.replace(" ", "_"))
        local_path = os.path.abspath(local_path)

        if not os.path.exists(local_path):
            by_name = [shared_file for shared_file in self.shared_files
                       if shared_file.name == file_name]
            assert len(by_name) == 1
            artifact = by_name[0]
            assert len(artifact.files) == 1
            file = artifact.files[0]
            self.logger.info("Downloading file {} (artifact={} '{}')"
                             .format(file.id, artifact.id, artifact.name))

            # TODO: implemented in the genologics package?
            response = self.advanced.get("files/{}/download".format(file.id))
            print "bab", response
            with open(local_path, 'wb') as fd:
                for chunk in response.iter_content():
                    fd.write(chunk)

            self.logger.info("Download completed, path='{}'".format(local_path))

        # Add to this list for cleanup:
        if local_path not in self._local_shared_files:
            self._local_shared_files.append(local_path)

        return local_path

    @lazyprop
    def plate2(self):
        self.logger.debug("Getting current plate (lazy property)")
        # TODO: Assumes 96 well plate only
        plate = Plate()
        for input, output in self.current_step.input_output_maps:
            if output['output-generation-type'] == "PerInput":
                # Process
                artifact = output['uri']
                location = artifact.location
                well = location[1]
                plate.set_well(well, artifact.name)
        return plate

    @lazyprop
    def input_analytes(self):
        input_uris = []
        for input_uri, _ in self.current_step.input_output_maps:
            if input_uri:
                input_uris.append(input_uri["uri"])
        resources = self.advanced.lims.get_batch(input_uris)
        return [Analyte(resource) for resource in resources]

    @lazyprop
    def output_analytes(self):
        # TODO: Could be more DRY
        # TODO: Doesn't there exist anything for this in the genologics package?
        # TODO: I believe that the rest client already caches input_output_maps in-process,
        #       if not, put that into a lazyprop too
        output_uris = []
        for _, output_uri in self.current_step.input_output_maps:
            if output_uri and output_uri["output-type"] == "Analyte":
                output_uris.append(output_uri["uri"])
        resources = self.advanced.lims.get_batch(output_uris)
        return [Analyte(resource) for resource in resources]

    @lazyprop
    def dilution_scheme(self):
        # TODO: Might want to have this on a property called dilution
        return DilutionScheme(self.input_analytes,
                              self.output_analytes)

    @lazyprop
    def shared_files(self):
        """
        Fetches all share files for the current step
        """
        unique = dict()
        # The API input/output map is rather convoluted, but according to
        # the Clarity developers, this is a valid way to fetch all shared result files:
        for input, output in self.current_step.input_output_maps:
            if output['output-generation-type'] == "PerAllInputs":
                unique.setdefault(output["uri"].id, output["uri"])

        artifacts = self.advanced.lims.get_batch(unique.values())
        return artifacts

    @lazyprop
    def plate(self):
        self.logger.debug("Getting current plate (lazy property)")
        # TODO: Assumes 96 well plate only
        self.logger.debug("Fetching plate")
        artifacts = []

        # TODO: Should we use this or .all_outputs?
        for input, output in self.current_step.input_output_maps:
            if output['output-generation-type'] == "PerInput":
                artifacts.append(output['uri'])

        # Batch fetch the details about these:
        artifacts_ex = self.advanced.lims.get_batch(artifacts)
        plate = Plate()
        for artifact in artifacts_ex:
            well_id = artifact.location[1]
            plate.set_well(well_id, artifact.name, artifact.id)

        return plate

    def cleanup(self):
        """Cleans up any downloaded resources. This method will be automatically
        called by the framework and does not need to be called by extensions"""
        # Clean up:
        for path in self._local_shared_files:
            if os.path.exists(path):
                self.logger.info("Local shared file '{}' will be removed to ensure "
                                 "that it won't be uploaded again")
                # TODO: Handle exception
                os.remove(path)


class Advanced:
    """Provides advanced features, should be avoided in extension scripts"""
    def __init__(self, lims):
        self.lims = lims

    def get(self, endpoint):
        """Executes a GET via the REST interface. One should rather use the lims property.
        The endpoint is the part after /api/v2/ in the API URI.
        """
        url = "{}/api/v2/{}".format(BASEURI, endpoint)
        return requests.get(url, auth=(USERNAME, PASSWORD))

