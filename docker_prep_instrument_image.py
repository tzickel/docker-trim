#!/usr/bin/env python
import subprocess
import json
import tarfile
import os
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


def tar_add_string_as_file(tar, name, s):
    t = tarfile.TarInfo(name=name)
    t.size = len(s)
    tar.addfile(tarinfo=t, fileobj=StringIO(s.encode('utf-8')))


def prep_instrument_image(image):
    config = get_image_config(image)
    entrypoint = config.get('Entrypoint')
    cmd = config.get('Cmd')
    trace_entrypoint = ["/tmp/instrumentation/strace", "-e" , "file", "-f", "-o", "/tmp/strace_output"]
    if entrypoint:
        trace_entrypoint.extend(entrypoint)
    # TODO . or the python script path (show output?)
    if not os.path.exists('instrumentation.tar.gz'):
        run('./get_instrumentation.sh')
    p_out = subprocess.Popen('docker build -q -', shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    Dockerfile = 'FROM %s\nRUN mkdir -p /tmp/instrumentation\nADD instrumentation.tar.gz /tmp/instrumentation\nENTRYPOINT %s\n' % (image, json.dumps(trace_entrypoint))
    if cmd:
        Dockerfile += 'CMD %s\n' % (json.dumps(cmd))
    with tarfile.open(fileobj=p_out.stdin, mode='w|', format=tarfile.PAX_FORMAT) as tar_out:
        tar_add_string_as_file(tar_out, 'Dockerfile', Dockerfile)
        # TODO arcname, in case we add a dir
        tar_out.add('instrumentation.tar.gz', arcname='instrumentation.tar.gz')
    p_out.stdin.close()
    output_image_id = p_out.stdout.read().decode('utf-8').strip()
    p_out.wait()
    if p_out.returncode != 0:
        raise Exception('Error writing resulting docker image (%d)' % p_out.returncode)
    return output_image_id


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        sys.stderr.write('Usage: %s <input image name> [output image tag]\n\n' % sys.argv[0])
        sys.stderr.write('Prepare an custom docker image that is ready to instrument file access I/O\n')
        sys.exit(1)
    image_in = sys.argv[1]
    try:
        image_out = sys.argv[2]
    except:
        image_out = None

    output_image = prep_instrument_image(image_in)
    if image_out:
        run('docker tag %s %s' % (output_image, image_out))
        print(image_out)
    else:
        print(output_image)
