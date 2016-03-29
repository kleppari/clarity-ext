
class Analyte():
    """
    Describes an Analyte in the Clarity LIMS system, including custom UDFs.

    Takes an analyte resource as input.
    """

    def __init__(self, resource):
        self.resource = resource

    # Mapped properties from the underlying resource
    # TODO: we might want to supply all of these via inheritance (or some Python trick)
    # or require the caller to use the underlying resource object (but that increases complexity)
    @property
    def name(self):
        return self.resource.name

    # Mapped UDFs
    @property
    def concentration(self):
        return self.resource.udf["Concentration"]

    @property
    def target_concentration(self):
        return float(self.resource.udf["Target Concentration"])

    @property
    def target_volume(self):
        return self.resource.udf["Target Volume"]

    # Other properties
    @property
    def well(self):
        row, col = self.resource.location[1].split(":")
        return Well(row, col)

    @property
    def container(self):
        return self.resource.location[0]


class Well:
    """Encapsulates a well in a plate"""
    def __init__(self, row, col, content=None):
        self.row = row
        self.col = col
        self.content = content
        self.row_index_dict = dict(
            [(row_str, row_ind)
             for row_str, row_ind
             in zip("ABCDEFGH", range(0, 7))])

    def get_key(self):
        return "{}:{}".format(self.row, self.col)

    def __repr__(self):
        return "{}:{}".format(self.row, self.col)

    def __str__(self):
        return "{} => {}".format(self.get_key(), self.content)

    def get_coordinates(self):
        # Zero based
        return self.row_index_dict[self.row], int(self.col) - 1


class Plate:
    """Encapsulates a Plate"""

    DOWN_FIRST = 1
    LEFT_FIRST = 2

    def __init__(self):
        self.wells = {}
        # For simplicity, set all wells:
        for well in self._traverse():
            self.wells[well] = Well(well[0], well[1])

    def _traverse(self, order=DOWN_FIRST):
        """Traverses the well in a certain order, yielding keys as (row,col) tuples"""

        # TODO: Provide support for other formats
        # TODO: Make use of functional prog. - and remove dup.
        if order == self.DOWN_FIRST:
            for row in "ABCDEFGH":
                for col in range(1, 13):
                    yield (row, col)
        else:
            for col in range(1, 13):
                for row in "ABCDEFGH":
                    yield (row, col)

    # Lists the wells in a certain order:
    def enumerate_wells(self, order=DOWN_FIRST):
        for key in self._traverse(order):
            yield self.wells[key]

    def list_wells(self, order=DOWN_FIRST):
        return list(self.enumerate_wells(order))

    def set_well(self, well_id, content):
        """
        well_id should be a string in the format 'B:1'
        """
        if type(well_id) is str:
            split = well_id.split(":")
            well_id = split[0], int(split[1])

        if well_id not in self.wells:
            raise KeyError("Well id {} is not available in this plate".format(well_id))

        self.wells[well_id].content = content


class Dilute:
    # Enclose sample data, user input and derived variables for a
    # single row in a dilution
    def __init__(self, input_analyte, output_analyte):
        self.target_concentration = output_analyte.target_concentration
        self.target_volume = output_analyte.target_volume

        # TODO: Ensure that the domain object sets these to None if not available
        # TODO: Add the following condition to the validation stuff:
        # if self.target_concentration is None or self.target_volume is None:
        self.target_well = output_analyte.well
        self.target_container = output_analyte.container
        self.sample_name = output_analyte.name
        self.source_concentration = input_analyte.concentration
        self.sample_volume = None
        self.buffer_volume = None
        self.target_well_index = None
        self.target_plate_pos = None
        self.has_to_evaporate = None


class RobotDeckPositioner:
    """
    Handle plate positions on the robot deck (target and source)
    as well as well indexing
     """
    def __init__(self, robot_name, dilutes):
        index_method_map = {"Hamilton": self._calculate_well_index_hamilton}
        self.indexer = index_method_map[robot_name]
        self.target_plate_position_map = self._build_plate_position_map(
            [dilute.target_container for dilute in dilutes],
            "END"
        )

    @staticmethod
    def _calculate_well_index_hamilton(well, plate_size_y):
        (y, x) = well.get_coordinates()
        return x * plate_size_y + y + 1

    @staticmethod
    def _build_plate_position_map(containers, plate_pos_prefix):
        # Fetch an unique list of container names from input
        # Make a dictionary with container names and plate positions
        unique_containers = sorted(list(
            {container.id for container in containers}))
        positions = range(1, len(unique_containers) + 1)
        target_plate_positions = \
            ["{}{}".format(plate_pos_prefix, pos) for pos in positions]
        plate_positions = dict(zip(unique_containers, target_plate_positions))
        return plate_positions


class DilutionScheme:
    """Creates a dilution scheme, given input and output analytes."""

    def __init__(
            self, input_analytes, output_analytes,
            robot_name, plate_size_y):

        self.dilutes = []
        for in_analyte, out_analyte in zip(input_analytes, output_analytes):
            self.dilutes.append(Dilute(in_analyte, out_analyte))

        robot_deck_positioner = RobotDeckPositioner(robot_name, self.dilutes)

        for dilute in self.dilutes:
            dilute.sample_volume = \
                dilute.target_concentration * dilute.target_volume / \
                dilute.source_concentration
            dilute.buffer_volume = \
                max(dilute.target_volume - dilute.sample_volume, 0)
            dilute.target_well_index = robot_deck_positioner.indexer(
                dilute.target_well, plate_size_y)
            dilute.target_plate_pos = robot_deck_positioner\
                .target_plate_position_map[
                    dilute.target_container.id]
            dilute.has_to_evaporate = \
                (dilute.target_volume - dilute.sample_volume) < 0

    def validate(self):
        """Yields validation errors or warnings"""
        if any(dilute.sample_volume < 2 for dilute in self.dilutes):
            yield ValidationException("Too low sample volume")

        if any(dilute.sample_volume > 50 for dilute in self.dilutes):
            yield ValidationException("Too high sample volume")

        if any(dilute.buffer_volume > 50 for dilute in self.dilutes):
            yield ValidationException("Too high buffer volume")

        if any(dilute.has_to_evaporate for dilute in self.dilutes):
            yield ValidationException("Sample has to be evaporated", ValidationType.WARNING)


class ValidationType:
    ERROR = 1
    WARNING = 2


class ValidationException:
    def __init__(self, msg, validation_type=ValidationType.ERROR):
        self.msg = msg
        self.type = validation_type

    def _repr_type(self):
        if self.type == ValidationType.ERROR:
            return "Error"
        elif self.type == ValidationType.WARNING:
            return "Warning"

    def __repr__(self):
        return "{}: {}".format(self._repr_type(), self.msg)
