#!/usr/bin/env python
# This script needs non relative file and directories list
# Currently works on linux docker images
# Currently works only on images which can be run
# TODO write better usage info
# TODO what about stripping when tarring?
# TODO move the shebang processing to file magic rule
import subprocess
import tarfile
import os


def run(cmd):
    return subprocess.check_output(cmd, shell=True)


def get_abs_path(path, helper=None):
    if not os.path.isabs(path):
        if not helper:
            path = os.path.join('/', path)
        else:
            path = os.path.join(os.path.dirname(helper), path)
    path = os.path.normpath(path)
    return path


def filter_image(image, files_list):
    container_id = run('docker create %s' % (image)).decode('utf-8').strip()
    try:
        p = subprocess.Popen('docker export %s' % (container_id), shell=True, stdout=subprocess.PIPE)
        links = {}
        with tarfile.open(fileobj=p.stdout, mode='r|*', format=tarfile.PAX_FORMAT) as tar_in:
            for member in tar_in:
                fname = get_abs_path(member.name)
                fname_link = None
                if member.isreg():
                    data = tar_in.extractfile(member)
                    if data:
                        line = data.read(2)
                        if line == b'#!':
                            line = data.readline()
                            line = line.strip().split(b' ')[0]
                            fname_link = get_abs_path(line.decode('utf-8'), fname)
                        data.close()
                # symlink is relative to member.name, hardlink is absolute
                elif member.issym():
                    fname_link = get_abs_path(member.linkname, fname)
                elif member.islnk():
                    fname_link = get_abs_path(member.linkname)
                if fname_link is not None:
                    links.setdefault(fname, set()).add(fname_link)
        p.wait()
        if p.returncode != 0:
            raise Exception('Error building trimmed image')
        needed_file_names = set(files_list)

        to_check_file_names = set(needed_file_names)
        while to_check_file_names:

            add_directories = set()
            for file_name in to_check_file_names:
                # TODO complaint about depth level > 1 for links path
                old_file_name = None
                while file_name != old_file_name:
                    old_file_name = file_name
                    file_name = os.path.split(file_name)
                    fname = file_name[1]
                    file_name = file_name[0]
                    if file_name not in needed_file_names:
                        add_directories.add(file_name)
                    link = links.get(file_name)
                    if link:
                        for file_name_link in link:
                            add_directories.add(os.path.join(file_name_link, fname))

            to_check_file_names |= add_directories
            needed_file_names |= add_directories

            next_to_check = set()
            for to_check_file_name in to_check_file_names:
                link = links.get(to_check_file_name)
                if link:
                    for link_file_name in link:
                        if link_file_name not in needed_file_names:
                            needed_file_names.add(link_file_name)
                            next_to_check.add(link_file_name)
            to_check_file_names = next_to_check

        return needed_file_names
    finally:
        run('docker rm -f -v %s' % (container_id))


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        sys.stderr.write('Usage: %s <input image> <file list> [file list...]\n\n' % sys.argv[0])
        sys.stderr.write('file list must contain absolute (non-relative) paths (files and dirs) to preserve individually from the original image\n')
        sys.exit(1)
    in_image = sys.argv[1]
    trim_list = sys.argv[2:]

    files_list = set(['/.dockerenv', '/etc/passwd', '/etc/shadow', '/etc/group'])
    for trim_file in trim_list:
        with open(trim_file, 'rt') as f:
            for line in f:
                line = line.strip()
                if not os.path.isabs(line):
                    sys.stderr.write('This script must process only non-relative files: %s\n' % line)
                    sys.exit(1)
                line = os.path.normpath(line)
                files_list.add(line)

    for fname in filter_image(in_image, files_list):
        print(fname)
