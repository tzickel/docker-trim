#!/usr/bin/env python
# TODO did I cover all bases ?
# TODO python chdir open(<stdin>) ?
import subprocess
import json
import os


def run(cmd):
    return subprocess.check_output(cmd, shell=True)


def get_working_dir(image):
    return json.loads(run('docker inspect %s' % (image)))[0]['Config']['WorkingDir'] or '/'


def parse_strace_log(logfile, working_dir):
    files = set()
    with open(logfile, 'r') as f:
        for line in f:
            line = line[:-1]
            if '", ' in line:
                # TODO what happens if file has ", in it ? check...
                fname = line.split('", ', 1)[0].split('"', 1)[1]
                if not os.path.isabs(fname):
                    fname = os.path.join(working_dir, fname)
                files.add(fname)
            elif 'chdir("' in line:
                data = line.split('"', 1)
                if 'chdir' in data[0]:
                    data = data[1].rsplit('"', 1)
                    dir_ = data[0]
                    value = data[1].rsplit(' ', 1)[1]
                    if value == '0':
                        if os.path.isabs(dir_):
                            working_dir = dir_
                        else:
                            working_dir = os.path.join(working_dir, dir_)
    return files


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        sys.stderr.write('Usage: %s <input image> <strace output file> [strace output file...]\n' % sys.argv[0])
        sys.exit(1)
    image = sys.argv[1]
    log_files = sys.argv[2:]

    working_dir = get_working_dir(image)
    output_files = set()
    for log_file in log_files:
        files = parse_strace_log(log_file, working_dir)
        output_files.update(files)
    for fname in output_files:
        print(fname)
