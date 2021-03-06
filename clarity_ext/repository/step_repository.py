from clarity_ext.domain.artifact import Artifact
from clarity_ext.domain.analyte import Analyte
from clarity_ext.domain.result_file import ResultFile
from clarity_ext.domain.shared_result_file import SharedResultFile
from clarity_ext.repository.container_repository import ContainerRepository
from clarity_ext.domain.user import User
import copy


class StepRepository(object):
    """
    Provides access to data that's available through a current step.

    All methods return the domain objects, wrapping the REST resources.

    Since the underlying library does caching, this repository does not need
    to do that.
    """

    def __init__(self, session, udf_map=None):
        """
        Creates a new StepRepository

        :param session: A session object for connecting to Clarity
        :param udf_map: A map between domain objects and user defined fields. See `DEFAULT_UDF_MAP` for details
        """
        self.session = session
        self.udf_map = udf_map or DEFAULT_UDF_MAP
        self.orig_state_cache = dict()

    def all_udfs(self):
        """
        Returns the UDFs on the current step
        """
        return self.session.current_step.udf

    def all_artifacts(self):
        """
        Fetches all artifacts from the input output map, wraps them in to a domain object.
        From then on, the domain object knows the following:
            * From what resource was it built (for debug reasons, e.g. for getting the URL)
            * Is it an input or output artifact
            * What's the corresponding input or output object (input objects have a reference
              to the output object and vice-versa

        After this, all querying should be done on these domain objects.

        The list is not unique, i.e. artifacts will be fetched more than once.

        Performance note: This method may fetch much more data than necessary as it's designed
        for simplified use of the API. If optimal performance is required, use the underlying REST API
        instead.
        """
        input_output_maps = self.session.current_step.input_output_maps
        artifact_keys = set()
        for input, output in input_output_maps:
            artifact_keys.add(input["uri"])
            artifact_keys.add(output["uri"])
        artifacts = self.session.api.get_batch(artifact_keys)
        artifacts_by_uri = {artifact.uri: artifact for artifact in artifacts}
        for input, output in input_output_maps:
            input['uri'] = artifacts_by_uri[input['uri'].uri]
            output['uri'] = artifacts_by_uri[output['uri'].uri]

        ret = []
        # TODO: Ensure that the container repo fetches all containers in one batch call:
        container_repo = ContainerRepository()
        for input_res, output_res in input_output_maps:
            input, output = self._wrap_input_output(
                input_res, output_res, container_repo)
            ret.append((input, output))

        self._add_to_orig_state_cache(ret)
        return ret

    def _add_to_orig_state_cache(self, artifact_tuple_list):
        artifact_set = set(list(sum(artifact_tuple_list, ())))
        artifact_dict = {artifact.id: copy.copy(artifact) for artifact in artifact_set}
        artifact_dict.update(self.orig_state_cache)
        self.orig_state_cache = artifact_dict

    def _wrap_input_output(self, input_info, output_info, container_repo):
        # Create a map of all containers, so we can fill in it while building
        # domain objects.

        # Create a fresh container repository. Then we know that only one container
        # will be created for each object in a call to this method
        input_resource = input_info["uri"]
        output_resource = output_info["uri"]
        output_gen_type = output_info["output-generation-type"]
        input = self._wrap_artifact(
            input_resource, container_repo, gen_type="Input", is_input=True)
        output = self._wrap_artifact(output_resource, container_repo,
                                     gen_type=output_gen_type, is_input=False)

        if output_gen_type == "PerInput":
            output.generation_type = Artifact.PER_INPUT
        elif output_gen_type == "PerAllInputs":
            output.generation_type = Artifact.PER_ALL_INPUTS
        else:
            raise NotImplementedError(
                "Generation type {} is not implemented".format(output_gen_type))

        if isinstance(output, ResultFile):
            output.output_type = Artifact.OUTPUT_TYPE_RESULT_FILE
        elif isinstance(output, Analyte):
            output.output_type = Artifact.OUTPUT_TYPE_ANALYTE
        elif isinstance(output, SharedResultFile):
            output.output_type = Artifact.OUTPUT_TYPE_SHARED_RESULT_FILE
        else:
            raise NotImplementedError(
                "Output type {} is not implemented".format(output.__class__.__name__))

        # Add a reference to the other object for convenience:
        input.output = output
        output.input = input

        return input, output

    def _wrap_artifact(self, artifact, container_repo, gen_type, is_input):
        """
        Wraps an artifact in a domain object, if one exists. The domain objects provide logic
        convenient methods for working with the domain object in extensions.
        """
        if artifact.type == "Analyte":
            wrapped = Analyte.create_from_rest_resource(artifact, is_input, self.udf_map, container_repo)
        elif artifact.type == "ResultFile" and gen_type == "PerInput":
            wrapped = ResultFile.create_from_rest_resource(artifact, is_input, self.udf_map, container_repo)
        elif artifact.type == "ResultFile" and gen_type == "PerAllInputs":
            wrapped = SharedResultFile.create_from_rest_resource(artifact, self.udf_map)
        else:
            raise Exception("Unknown type and gen_type combination {}, {}".format(
                artifact.type, gen_type))

        # TODO: This is kind of a hack for adding the parent process. Make more use of OOP.
        try:
            wrapped.parent_process = artifact.parent_process
        except AttributeError:
            wrapped.parent_process = None

        return wrapped

    def _wrap_artifacts(self, artifacts):
        for artifact in artifacts:
            yield self._wrap_artifact(artifact)

    def update_artifacts(self, artifacts):
        """
        Updates each entry in objects to db
        """
        update_queue = []
        response = []
        for artifact in artifacts:
            updated_fields = self._retrieve_updated_fields(artifact)
            original_artifact_from_rest = artifact.api_resource
            updated_rest_resource, single_response = \
                artifact.updated_rest_resource(
                    original_artifact_from_rest, updated_fields)
            response.append(single_response)
            update_queue.append(updated_rest_resource)

        self.session.api.put_batch(update_queue)
        return sum(response, [])

    def _retrieve_updated_fields(self, updated_artifact):
        orig_art = self.orig_state_cache[updated_artifact.id]
        return updated_artifact.differing_fields(orig_art)

    def current_user(self):
        current_user_resource = self.session.current_step.technician
        return User.create_from_rest_resource(current_user_resource)




"""
The default UDF map. Certain features of the library depend on some fields existing on the domain
objects that are only available through UDFs. To make the library usable without having to define
exactly the same names in different implementations, a different UDF map can be provided for
different setups. TODO: Make the UDF map configurable in the settings for the clarity-ext tool.
"""
DEFAULT_UDF_MAP = {
    "Analyte": {
        "concentration_ngul": "Conc. Current (ng/ul)",
        "concentration_nm": "Conc. Current (nM)",
        "requested_concentration_ngul": "Target conc. (ng/ul)",
        "requested_concentration_nm": "Target conc. (nM)",
        "requested_volume": "Target vol. (ul)",
        "volume": "Current sample volume (ul)"
    },
    "ResultFile": {
        "concentration_ngul": "Conc. Current (ng/ul)",
        "volume": "Current sample volume (ul)"
    },
    "SharedResultFile": {
        "has_errors": "Has errors2",
    }
}
