from domain import *


class Dilute:
    # Enclose sample data, user input and derived variables for a
    # single row in a dilution
    def __init__(self, input_analyte, output_analyte):
        self.target_concentration = output_analyte.target_concentration
        self.target_volume = output_analyte.target_volume

        # TODO: Ensure that the domain object sets these to None if not available
        # TODO: Add the following condition to the validation stuff:
        # if self.target_concentration is None or self.target_volume is None:
        self.source_well = input_analyte.well
        self.source_container = input_analyte.container
        self.target_well = output_analyte.well
        self.target_container = output_analyte.container
        self.sample_name = output_analyte.name
        self.source_concentration = input_analyte.concentration
        self.sample_volume = None
        self.buffer_volume = None
        self.source_well_index = None
        self.source_plate_pos = None
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
        self.source_plate_position_map = self._build_plate_position_map(
            [dilute.source_container for dilute in dilutes],
            "DNA"
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

        self.dilutes = self.init_dilutes(input_analytes, output_analytes)
        robot_deck_positioner = RobotDeckPositioner(robot_name, self.dilutes)

        for dilute in self.dilutes:
            dilute.source_well_index = robot_deck_positioner.indexer(
                dilute.source_well, plate_size_y)
            dilute.source_plate_pos = robot_deck_positioner.\
                source_plate_position_map[dilute.source_container.id]
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

    @staticmethod
    def init_dilutes(input_analytes, output_analytes):
        dilutes = []
        for in_analyte, out_analyte in zip(input_analytes, output_analytes):
            dilutes.append(Dilute(in_analyte, out_analyte))
        return dilutes
