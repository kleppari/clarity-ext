import os
from genologics.lims import Lims
from genologics.epp import attach_file
from genologics.config import BASEURI, USERNAME, PASSWORD
from genologics.entities import *
from clarity_ext.domain import Plate, Analyte
from clarity_ext.dilution import DilutionScheme
import importlib
from utils import lazyprop
import shutil
import difflib


# The object accessible during execution of the driver file script:
# Contains things like the current plate.
# The underlying connection objects etc. can be accessed through "advanced"
class DriverFileContext:
    """
    Context object for DriverFile extensions

    Provides context objects as lazy properties.
    """
    def __init__(self, current_step, advanced, logger=None):
        self.current_step = current_step
        self.advanced = advanced
        self.logger = logger or logging.getLogger(__name__)

    @lazyprop
    def plate(self):
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
    def dilution_scheme(self):
        # TODO: Might want to have this on a property called dilution
        return DilutionScheme(self.input_analytes,
                              self.output_analytes,
                              "Hamilton",
                              8)

    @lazyprop
    def input_analytes(self):
        # Get an unique set of input analytes
        # The rest client have a proper call for this (all_inputs) but it
        # renders a run time error
        input_artifacts = []
        for input_artifact, _ in self.current_step.input_output_maps:
            if input_artifact:
                input_artifacts.append(input_artifact["uri"])

        # unique_inputs = dict([(ia.uri, ia) for ia in input_artifacts])
        # sorted_tuples = sorted(unique_inputs.items(), reverse=True)
        # input_uris = [tuple[1] for tuple in sorted_tuples]

        # input_uris = list(set(input_uris))
        # input_uris = list(set([artifact.uri for artifact in input_artifacts]))

        unique_inputs = dict([(ia.uri, ia) for ia in input_artifacts])
        tmp = [(ia.uri, ia) for ia in input_artifacts]
        unique_inputs = dict(tmp)

        # tmp = [tuple[1] for tuple in unique_inputs.items()]

        input_uris = [tuple[1] for tuple in tmp]
        # input_uris = [tuple[0] for tuple in unique_inputs.items()]
        input_uris = unique_inputs.values()

        self.logger.debug("input uris, {}".format(input_artifacts))
        resources = self.advanced.lims.get_batch(input_artifacts)
        return [Analyte(resource) for resource in resources]

    @lazyprop
    def output_analytes(self):
        # TODO: Could be more DRY
        # TODO: Doesn't there exist anything for this in the genologics package?
        # TODO: I believe that the rest client already caches input_output_maps in-process,
        #       if not, put that into a lazyprop too
        # The rest client have the proper calls for this (analytes), but
        # it renders a run-time error.
        output_uris = []
        for _, output_uri in self.current_step.input_output_maps:
            if output_uri and output_uri["output-type"] == "Analyte":
                output_uris.append(output_uri["uri"])
        resources = self.advanced.lims.get_batch(output_uris)
        return [Analyte(resource) for resource in resources]


class DriverFileService:
    def __init__(self, process_id, script_module, result_path, lims_file, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.logger.info("Generating driverfile using script module '{}'".format(script_module))
        self.script_module = script_module
        self.process_id = process_id
        self.result_path = result_path
        self.lims_file = lims_file
        self.lims = Lims(BASEURI, USERNAME, PASSWORD)
        self.lims.check_version()
        self.current_step = Process(self.lims, id=self.process_id)
        self.logger.debug("Created a process step: {}".format(self.current_step))

    def execute(self, commit=False, artifacts_to_stdout=False):
        """
        :param commit: Set to True to write back to the LIMS. Set to False while testing, which only
           moves the file to the ./uploaded directory
        :param driver_files_to_stdout: Set to True to write uploaded artifacts to stdout too.
        :return:
        """
        self.logger.info("Generating DriverFile for step={}".format(self.current_step))
        context = DriverFileContext(self.current_step, advanced=self)
        self.logger.debug("Created a context file for the current step, {}".format(self.current_step))
        module = importlib.import_module(self.script_module)
        extension = getattr(module, "Extension")
        instance = extension(context)
        self.logger.debug("Successfully created an extension instance. Executing the create method.")

        # Save the file to the directory:
        local_file = self._save_file_locally(instance, self.result_path)
        self._upload(local_file, commit, artifacts_to_stdout)

    def _save_file_locally(self, instance, root):
        """Saves the output generated by the instance"""
        if not os.path.exists(root):
            self.logger.debug("Creating directories {}".format(root))
            os.makedirs(root)
        full_path = os.path.join(root, instance.filename())
        with open(full_path, 'w') as f:
            self.logger.debug("Writing output to {}.".format(full_path))
            for line in instance.content():
                f.write(line + "\n")
        return full_path

    def _upload(self, local_file, commit, artifacts_to_stdout):
        self.logger.info("Uploading local file {} to the LIMS placeholder at {}".format(local_file, self.lims_file))
        output_file_resource = self._get_output_file_resource()
        if commit:
            # Find the output on the current step
            self.logger.info("Uploading to the LIMS server")
            attach_file(local_file, output_file_resource)
        else:
            # When not connected to an actual server, we copy the file to another directory for integration tests
            upload_path = os.path.join(self.result_path, "uploaded")
            self.logger.info("Commit is set to false, copying the file to {}".format(upload_path))
            if os.path.exists(upload_path):
                os.rmdir(upload_path)
            os.mkdir(upload_path)
            # The LIMS does always add a prefix with the artifact ID:
            new_file_name = "{}_{}".format(output_file_resource.id, os.path.basename(local_file))
            new_file_path = os.path.join(upload_path, new_file_name)
            shutil.copyfile(local_file, new_file_path)

        if artifacts_to_stdout:
            print "--- {} => {}".format(local_file, output_file_resource.id)
            with open(local_file, 'r') as f:
                print f.read()
            print "---"

    def _get_output_file_resource(self):
        outputs = list(self.current_step.all_outputs())
        output_file_resources = [output for output in outputs if output.id == self.lims_file]
        assert len(output_file_resources) <= 1
        if len(output_file_resources) == 0:
            available = [output_file.id for output_file in outputs]
            message = "Output file '{}' not found. Available IDs on the step: {}" \
                .format(self.lims_file, ", ".join(available))
            raise OutputFileNotFound(message)
        return output_file_resources[0]


class DriverFileIntegrationTests:
    @staticmethod
    def _locate_driver_file_pair(run_directory, frozen_directory, test):
        def locate_driver_file(path):
            files = os.listdir(path)
            count = len(files)
            if count != 1:
                raise UnexpectedNumberOfFilesException("{}: {}".format(path, count))

            for file_name in files:
                import fnmatch
                if fnmatch.fnmatch(file_name, "{}*".format(test["out_file"])):
                    return os.path.join(path, file_name)
                else:
                    raise FrozenFileNotFoundException("No frozen file found")

        frozen_path = os.path.join(frozen_directory, "uploaded")
        run_path = os.path.join(run_directory, "uploaded")

        # We want to find one file (can currently only be one) and it should
        # start with the step name. The rest of the file name can be anything and is not
        # tested here
        frozen_file = locate_driver_file(frozen_path)
        run_file = locate_driver_file(run_path)
        return frozen_file, run_file

    def validate(self, run_directory, frozen_directory, test):
        pair = self._locate_driver_file_pair(run_directory, frozen_directory, test)
        fromfile, tofile = pair
        fromlines = open(fromfile, 'r').readlines()  # U?
        tolines = open(tofile, 'r').readlines()
        diff = list(difflib.unified_diff(fromlines, tolines, fromfile, tofile))
        if len(diff) > 0:
            raise FilesDifferException("Diff (max 100 lines):\n{}".format("".join(diff[0:100])))


class FilesDifferException(Exception):
    pass


class FrozenFileNotFoundException(Exception):
    pass


class UnexpectedNumberOfFilesException(Exception):
    pass


class OutputFileNotFound(Exception):
    pass


