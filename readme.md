# What is it ?

This set of tools allows you to create a trimmed docker image that contains only parts of the original file system of an existing docker image.

It also contains documentation and helper scripts to tell you which files are required from the original docker image.

Do not use this tool if you don't have knowledge of what the files you will be removing means for production use.

# Known issues

* This isn't battle tested, your mileage may vary, use at your own risk. Report back if there is a bug or a missing feature.

* The commands and their arguments aren't finalized yet.

# Requirements

* Python 2 or 3.

* Docker runtime.

* The image must be of a non-windows docker image, and be able to run on the host.

# How-to

This part will explain how to first collect which files are needed in the docker image, and then how to trim the docker image.

## Instrumenting an docker image for checking which files to keep

In this step we will explore one option to figure out which files we need to keep in an image.

Let's say we want to figure which files does the docker image redis:5.0.3 actually use.

First we need a one-time step to get an generic instrumentation package, so run the get_instrumentation.sh bash script.

```
$ bash ./get_instrumentation.sh
Building instrumentation file, will take awhile...
```

Then we run this build command to create our instrumented image. Take notice that this new redis_instrument:5.0.3 image's entrypoint will be changed to instrument file access to /tmp/strace_output.

```
$ docker build . --build-arg baseimage=redis:5.0.3 -t redis_instrument:5.0.3 -f Dockerfile.instrument
...
Successfully tagged redis_instrument:5.0.3
```

Now you can create an empty file strace_output1 (If you do not do that the next step will create a directory instead, and the process won't work until you delete the directory and run this command instead):

```
$ touch strace_output1
```

And run the docker with the command as follows (dont forget to add any required run parameters as needed):

```
$ docker run -it --rm --cap-add=SYS_PTRACE -v `pwd`/strace_output1:/tmp/strace_output redis_instrument:5.0.3 docker-entrypoint.sh redis-server
7:C 21 Jan 2019 08:03:00.367 # oO0OoO0OoO0Oo Redis is starting oO0OoO0OoO0Oo
...
```

If the image is non-interactive, be sure to stop it after you've captured a good usage of it.

Be sure to take notice of the original redis ENTRYPOINT (docker inspect redis:5.0.3) and use it as well, so it's input will be instrumented as well!

You can produce as many strace_output runs (with different file names) as you feel needed to capture all possible uses of the image after it's trimmed.

You should now have one or more strace log outputs of running your image.

Let's parse the output of the strace file access to a file list (you can provide many strace output files):

```
$ python docker_parse_strace.py redis:5.0.3 strace_output1 > parsed_strace_output
```

Now we need to extract the dynamic loader name (if exists):

```
$ docker run -it --entrypoint="" -v `pwd`/parsed_strace_output:/tmp/parsed_output --rm redis_instrument:5.0.3 /tmp/instrumentation/file -m /tmp/instrumentation/magic.mgc -b -L -f /tmp/parsed_output > file_output
```

And add it to our list:

```
$ python docker_parse_file.py file_output >> parsed_strace_output
```

Don't forget to remove the redis_instrument:5.0.3 image after you don't need it anymore:

```
$ docker rmi redis_instrument:5.0.3
```

## Trimming a docker image

Let's take the image redis:5.0.3 and trim it given the parsed_strace_output from the previous stage.

First, running this command will make sure to process from a file list, the symbolic links and directories as well (that exist in the docker image):

```
$ python docker_scan_image.py redis:5.0.3 parsed_strace_output > final_file_list
```

Then, we can use the output of that command (redirected to a file called final_file_list) to trim down the original docker image to a new one (which the name will be written in the end):

```
$ python docker_trim.py redis:5.0.3 final_file_list
sha256:e8f1b99ac811951fb0b746940ff3715520bf00a5ee3e37f54a4436c25afa5d8c
```

The produced docker image should have the same metadata (including ENTRYPOINT and CMD) of the original image so you can use it just as before.

If you want a saner name for the image, you can tag it (replace the hash from the previous command output):

```
$ docker tag sha256:e8f1b99ac811951fb0b746940ff3715520bf00a5ee3e37f54a4436c25afa5d8c redis:5.0.3_trimmed
```

We can now compare the new image sizes:
```
$ docker images redis:5.0.3
REPOSITORY          TAG                 IMAGE ID            CREATED             SIZE
redis               5.0.3               5d2989ac9711        3 weeks ago         95MB

$ docker images redis:5.0.3_trimmed
REPOSITORY          TAG                 IMAGE ID            CREATED             SIZE
redis               5.0.3_trimmed       e8f1b99ac811        21 minutes ago      14MB
```
We can see a reduction in size from 95MB to 14MB.
