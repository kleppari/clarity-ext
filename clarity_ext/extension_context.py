from genologics.config import BASEURI, USERNAME, PASSWORD
from genologics.lims import Lims
from genologics.entities import *
import requests
import xml.etree.ElementTree as ElementTree
import os
from clarity_ext.utils import lazyprop
from clarity_ext.domain import *


class ExtensionContext:
    """
    Defines context objects for extensions.
    """
    def __init__(self, current_step, shared_file, logger=None):
        # TODO: Add the lims property to "advanced" so that it won't be accessed accidentally?
        # TODO: These don't need to be provided in most cases
        lims = Lims(BASEURI, USERNAME, PASSWORD)
        lims.check_version()

        self.advanced = Advanced(lims)
        self.current_step = Process(lims, id=current_step)
        self.logger = logger or logging.getLogger(__name__)
        self.shared_file = shared_file

    @property
    def local_shared_file(self):
        # Does nothing if the file is here

        if not os.path.exists(self.shared_file):
            print self.shared_file
            response = self.advanced.get("artifacts/{}".format(self.shared_file))
            xml = response.text
            root = ElementTree.fromstring(xml)
            files = [child.get('limsid')
                     for child in root if child.tag == "{http://genologics.com/ri/file}file"]
            assert len(files) == 1
            response = self.advanced.get("files/{}/download".format(files[0]))
            with open(self.shared_file, 'wb') as fd:
                for chunk in response.iter_content():
                    fd.write(chunk)
        return self.shared_file

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

