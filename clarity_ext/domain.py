class Plate:
    """Encapsulates a Plate"""

    DOWN_FIRST = 1
    LEFT_FIRST = 2

    def __init__(self):
        self._wells = {}

    def _enumerate_keys(self, order=DOWN_FIRST):
        # TODO: Provide support for other formats
        # TODO: Make use of functional prog. - and remove dup.
        if order == self.DOWN_FIRST:
            for row in "ABCDEFGH":
                for col in range(1, 13):
                    yield "{}:{}".format(row, col)
        else:
            for col in range(1, 13):
                for row in "ABCDEFGH":
                    yield "{}:{}".format(row, col)

    def enumerate_wells(self, order=DOWN_FIRST):
        for key in self._enumerate_keys(order):
            if key in self._wells:
                yield key, self._wells[key]
            else:
                yield key, None

    def set_well(self, well_id, content):
        """
        well_id should be a string in the format 'B:1'
        """
        self._wells[well_id] = content

