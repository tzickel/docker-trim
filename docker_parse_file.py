#!/usr/bin/env python
def parse_file(file_output):
    with open(file_output, 'rt') as f:
        ret = set()
        for line in f:
            line = line.strip()
            if 'interpreter' in line:
                # TODO risky parsing
                line = line.split(', interpreter ')[1].split(',')[0]
                ret.add(line)
        return ret


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 1:
        sys.stderr.write('Usage: %s <input file output>\n' % sys.argv[0])
        sys.exit(1)
    for line in parse_file(sys.argv[1]):
        print(line)
