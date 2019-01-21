#!/usr/bin/env python
# This script needs non relative file and directories list
# Currently works on non-windows docker images
# Currently works only on images which can be run
# TODO write better usage info
# TODO what about stripping when tarring?
# TODO not reproducable
import subprocess
import tarfile
import os
import json
import hashlib
try:
    from StringIO import StringIO
except ImportError:
    from io import BytesIO as StringIO


def run(cmd):
    return subprocess.check_output(cmd, shell=True)


def get_image_config(image):
    inspect = json.loads(run('docker inspect %s' % image))
    if len(inspect) > 1:
        raise Exception('Please enter only one unique id')
    return inspect[0]['Config']


def transplant_dockerfile(from_image, to_image):
    from_config = config_a = get_image_config(from_image)
    p_in = subprocess.Popen('docker save %s' % (to_image), shell=True, stdout=subprocess.PIPE)
    p_out = subprocess.Popen('docker load -q', shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    cs = None
    with tarfile.open(fileobj=p_in.stdout, mode='r|*', format=tarfile.PAX_FORMAT) as tar_in:
        with tarfile.open(fileobj=p_out.stdin, mode='w|', format=tarfile.PAX_FORMAT) as tar_out:
            for member in tar_in:
                filename = member.name
                if os.path.dirname(filename) == '' and filename.endswith('.json'):
                    fix_this = True
                else:
                    fix_this = False
                if member.isreg():
                    data = tar_in.extractfile(member)
                    if fix_this:
                        # Docker correctly puts the manifest.json file after the config.json file (if not report a bug in this project)
                        if filename == 'manifest.json':
                            json_data = json.load(data)
                            if len(json_data) != 1 or not cs:
                                raise Exception('Docker is doing something funny, please report this bug')
                            json_data[0]['Config'] = cs + '.json'
                            json_data = json.dumps(json_data).encode('utf-8')
                        else:
                            json_data = json.load(data)
                            json_data['config'] = config_a
                            if 'Image' in json_data['config']:
                                json_data['config']['Image'] = ''
                            json_data = json.dumps(json_data).encode('utf-8')
                            cs = hashlib.sha256(json_data).hexdigest()
                            member.name = cs + '.json'
                        member.size = len(json_data)
                        data.close()
                        data = StringIO(json_data)
                    tar_out.addfile(member, fileobj=data)
                    data.close()
                else:
                    tar_out.addfile(member)
    p_in.stdout.close()
    p_out.stdin.close()
    output_image_id = p_out.stdout.read().decode('utf-8').strip().rsplit(' ', 1)[1]
    p_out.wait()
    p_in.wait()
    if p_out.returncode != 0:
        raise Exception('Error writing resulting docker image (%d)' % p_out.returncode)
    if p_in.returncode != 0:
        raise Exception('Error writing resulting docker image (%d)' % p_in.returncode)
    return output_image_id


def filter_image(image, files_list):
    container_id = run('docker create %s' % (image)).decode('utf-8').strip()
    try:
        p = subprocess.Popen('docker export %s' % (container_id), shell=True, stdout=subprocess.PIPE)
        # TODO should we include hash as well ? 
        p_out = subprocess.Popen('docker import - -m "%s"' % ("Image trimmed from " + image), shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        with tarfile.open(fileobj=p.stdout, mode='r|*', format=tarfile.PAX_FORMAT) as tar_in:
            with tarfile.open(fileobj=p_out.stdin, mode='w|', format=tarfile.PAX_FORMAT) as tar_out:
                for member in tar_in:
                    fname = '/' + os.path.normpath(member.name)
                    if not fname in files_list:
                        continue
                    if member.isreg():
                        data = tar_in.extractfile(member)
                        tar_out.addfile(member, fileobj=data)
                        data.close()
                    else:
                        tar_out.addfile(member)
        p_out.stdin.close()
        p_out.wait()
        if p_out.returncode != 0:
            raise Exception('Error writing resulting docker image (%d)' % p_out.returncode)
        tmp_image_id = p_out.stdout.read().decode('utf-8').strip()
        p.wait()
        if p.returncode != 0:
            raise Exception('Error reading temporary container (%d)' % p.returncode)
        return tmp_image_id
    finally:
        run('docker rm -f -v %s' % (container_id))


def build_trimmed_image(tmp_image, dockerfile):
    p_out = subprocess.Popen('docker build -q -', shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    dockerfile = 'FROM %s\n' % (tmp_image) + dockerfile
    p_out.stdin.write(dockerfile.encode('utf-8'))
    p_out.stdin.close()
    output_image_id = p_out.stdout.read().decode('utf-8').strip()
    p_out.wait()
    if p_out.returncode != 0:
        raise Exception('Error writing resulting docker image (%d)' % p_out.returncode)
    return output_image_id


def trim_image(in_image, files_list):
    tmp_image = filter_image(in_image, files_list)
    out_image = transplant_dockerfile(in_image, tmp_image)
    run('docker rmi %s' % (tmp_image))
    return out_image


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        sys.stderr.write('Usage: %s <input image> <file list> [file list...]\n\n' % sys.argv[0])
        sys.stderr.write('file list must contain absolute (non-relative) paths (files and dirs) to preserve individually from the original image\n')
        sys.exit(1)
    in_image = sys.argv[1]
    trim_list = sys.argv[2:]

    files_list = set(['/.dockerenv'])
    for trim_file in trim_list:
        with open(trim_file, 'rt') as f:
            for line in f:
                line = line[:-1]
                if not os.path.isabs(line):
                    sys.stderr.write('This script must process only non-relative files: %s\n' % line)
                    sys.exit(1)
                line = os.path.normpath(line)
                files_list.add(line)

    print(trim_image(in_image, files_list))
