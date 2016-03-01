context.outfile.name = "FA_input.csv"
context.outfile.write_line("key,sample")

for well in context.plate.list_wells(context.plate.DOWN_FIRST):
    line = "{}:{},{}".format(well.row, well.col, well.content or "0")
    context.outfile.write_line("{}".format(line))

