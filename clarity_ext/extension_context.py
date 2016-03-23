from genologics.config import BASEURI, USERNAME, PASSWORD
from genologics.lims import Lims
from genologics.entities import *
import requests
import xml.etree.ElementTree as ElementTree
import os


class ExtensionContext:
    """
    Defines context objects for extensions.
    """
    def __init__(self, current_step, in_file, logger=None):
        # TODO: Add the lims property to "advanced" so that it won't be accessed accidentally?
        # TODO: These don't need to be provided in most cases
        lims = Lims(BASEURI, USERNAME, PASSWORD)
        lims.check_version()

        self.advanced = Advanced(lims)
        self.current_step = Process(lims, id=current_step)
        self.logger = logger or logging.getLogger(__name__)
        self.in_file = in_file

    @property
    def local_in_file(self):
        # Does nothing if the file is here

        if not os.path.exists(self.in_file):
            response = self.advanced.get("artifacts/{}".format(self.in_file))
            xml = response.text
            root = ElementTree.fromstring(xml)
            files = [child.get('limsid')
                     for child in root if child.tag == "{http://genologics.com/ri/file}file"]
            assert len(files) == 1
            response = self.advanced.get("files/{}/download".format(files[0]))
            with open(self.in_file, 'wb') as fd:
                for chunk in response.iter_content():
                    fd.write(chunk)
        return self.in_file


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

