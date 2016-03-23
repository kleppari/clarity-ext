from clarity_ext.extensions import ResultFilesExt
from clarity_ext.domain import Plate

class Extension(ResultFilesExt):
    def generate(self):
        print self.context.current_step
        # ResultFilesExt classes have access to an "in_file"
        # TODO: Copied the following from Clarity - use the REST client instead!
        #       Before that, hide this in the context

        # This will return the path to the in_file, but after it has been downloaded locally
        path = self.context.local_in_file
        # TODO: This is very slow uncached! Speed it up.
        # Create a mapping from well to output ID:

        # TODO: move mapping to context object
        mapping = {}
        for output in self.context.current_step.all_outputs():
            if output.container:
                mapping[output.location[1]] = output.id

        #print mapping

        # Now, the pdf's pages are in this format:
        #  * 10 pages skipped
        #  * Samples in the order A1, B1 (DOWN_FIRST)

        # We can use the Plate class for helping out with this, since
        # it knows how to enumerate wells in a certain order:
        plate = Plate()
        for well in plate.enumerate_wells(order=Plate.DOWN_FIRST):
            print well

        return

        for each in range(len(wells)):
            page = 10 + each                #first image is on page 10
            well_loci = wells[each]
            limsid = sys.argv[each + 4]
            filename = limsid + "_" + well_loci
            # TODO: PDF package doesn't exist
            command = 'pdfimages ' + thePDF +' -j -f ' + str(page) + ' -l ' + str(page) + ' ' + filename
            os.system(command)
            longname = filename + "-000"
            ppmname = longname + ".ppm"

            # TODO: convert command doesn't exist
            jpegname = longname + ".jpeg"
            command2 = "convert " + ppmname + " " + jpegname
            os.system(command2)

            # TODO: Don't allow this crap!
            command3 = "rm *ppm"            #removing ppm image so it isn't inadvertently attached
            os.system(command3)


    def integration_tests(self):
        # TODO: If possible, query for the list in the API and reference
        # it here with an index instead
        # https://genologics.zendesk.com/requests/15568
        yield self.test("24-3649", "92-7408")

        """
        tempwd = os.getcwd()
        thePDF = tempwd + "/frag.pdf"           #temp PDF will be in this location

        wells=[]
        """

