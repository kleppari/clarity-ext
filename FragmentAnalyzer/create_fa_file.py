#!/usr/bin/env python
import os
from argparse import ArgumentParser
from genologics.lims import Lims
from genologics.config import BASEURI, USERNAME, PASSWORD
from genologics.entities import *
from genologics.epp import attach_file, EppLogger

# NOTE: This file is very ad-hoc/hacky. It will be cleaned up

DESC = """Creates a file for the fragment analyzer"""


def write_to_csv(file_name, header, wells, template, default_name):
    """
    Send in a template line as a list object, e.g:
    """
    with open(file_name, "w") as csv:
        if header:
            csv.write("{}\n".format(header))  # Header

        for well in wells:
            name = well[1] or default_name
            if name:
                csv.write(template.format(key=well[0], sample=name) + "\n")

if __name__ == "__main__":
    #pid = '24-1049'
    #output_file = '92-3028'

    parser = ArgumentParser(description=DESC)
    parser.add_argument('pid',
                        help='Lims id for current Process')
    parser.add_argument('--output-file',
                        required=True, help='Name of the output file to attach')
    parser.add_argument('--header', default=None,
                        help='Header format')
    parser.add_argument('--commit', action='store_true',
                        help='Includes write actions, such as saving a file. Should be included production')
    parser.add_argument('--order', default="left",
                        help="The order to use, either left, for left first or down for down first")
    parser.add_argument('--template', default="{key},{sample}",
                        help="The template to use for each value line in the csv")
    parser.add_argument('--default', default="",
                        help="The default to use for the sample name if empty")
    args = parser.parse_args()
    print args.template

    print "You sent pid={}, output_file={}, commit={}".format(args.pid, args.output_file, args.commit)

    print BASEURI, USERNAME
    lims = Lims(BASEURI, USERNAME, PASSWORD)
    lims.check_version()

    current_step = Process(lims, id=args.pid)
    plate = Plate()
    for input, output in current_step.input_output_maps:
        # This is ridiculous, hide all of this away in some abstraction (higher than the rest client)
        if output['output-generation-type'] == "PerInput":
            # Process
            artifact = output['uri']
            location = artifact.location
            container = location[0].id
            well = location[1]
            plate.set_well(well, artifact.name)

    if args.order == "left":
        order = plate.LEFT_FIRST
    else:
        order = plate.DOWN_FIRST

    wells = list(plate.enumerate_wells(order))
    assert len(wells) == 96

    TEMP_FILE = "FA_input.csv"
    write_to_csv(TEMP_FILE, args.header, wells, args.template, args.default)
    if args.commit:
        print current_step.all_outputs()
        output_file_resource = [output for output in current_step.all_outputs() if output.id == args.output_file][0]
        attach_file(os.path.join(os.getcwd(), TEMP_FILE), output_file_resource)
    else:
        print "File not committed (test mode):"
        with open(TEMP_FILE, "r") as csv:
            for line in csv:
                print line.strip()

