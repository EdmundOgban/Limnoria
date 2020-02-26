#-*- coding: utf8 -*-
import re

icaodesc_re = re.compile(r'^([A-Z]{4}).+?-(?: )?(.+)')

def search_missing(f):
    import icao_list

    for line in f:
        icao = re.match(r'^([A-Z]{4})', line)
        if icao.group(1) not in icao_list.airport_desc:
            print line

def generate_dict(f):
    with open("icao_list.py", "w") as fw:
        fw.write("#-*- coding: utf8 -*-\n")
        fw.write("airport_desc = {\n")
        for line in f:
            icao_match = icaodesc_re.match(line)
            if icao_match:
                icao, description = icao_match.groups()
                if '"' in description:
                    sep = "'"
                else:
                    sep = '"'
                fw.write('    "{}": {sep}{}{sep},\n'.format(icao, description, **dict(sep=sep)))
        fw.write("}\n")

with open("icao_list.txt") as f:
    generate_dict(f)
    f.seek(0)
    search_missing(f)

raw_input()
    
