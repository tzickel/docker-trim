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

# QuickStart

You can use (and read) the script oneshot_trim.sh for easily trimming an docker image, for example here is the redis:5.0.3 image:
```
$ ./oneshot_trim.sh redis:5.0.3
5.0.3: Pulling from library/redis
Digest: sha256:b950de29d5d4e4ef9a9d2713aa1213f76486dd8f9c0a43e9e8aac72e2cfc3827
Status: Downloaded newer image for redis:5.0.3
Creating temporary instrumentation image
Running image, press Ctrl-C when done (or finish the container)
9:C 04 Feb 2019 20:26:00.466 # oO0OoO0OoO0Oo Redis is starting oO0OoO0OoO0Oo
... redis output ...
9:M 04 Feb 2019 20:26:00.523 * Ready to accept connections
... now we press ctrl-c ...
^C9:signal-handler (1549311976) Received SIGINT scheduling shutdown...
9:M 04 Feb 2019 20:26:16.556 # Redis is now ready to exit, bye bye...
Processing file access instrumentation
Removing temporary instrumentation image
Deleted: sha256:3a417c2d29baab9c43eb64b0b3a2db8102dc84765d54d865222b614a5ea748cf
Deleted: sha256:b7182c046c8936f26452e2b001bf776769379f1b42cdaece5dc1a91a85268df3
Deleted: sha256:74b20939ee3a55ddf6f827b43ba6c29d68d3220f3bf619855183fb1ac1a50080
Deleted: sha256:fde2b0d3b7ad89a4f249e9996fe9a4d27b69fe904a4c2daa1dc1c7c5e57604fe
Deleted: sha256:bd5ca729b7e418911296869fe6c935f21ba3543d62d4c8e912a42c9fc53cc2f8
Deleted: sha256:1848ed87456f0f29703c6c36fd1d0d4fb995f051a9857972f650bb7b68a1b027
Creating trimmed image
sha256:525578ca12108b7fac9bcb3d152c949a74506f606e1e1282663a5a7ccdf3e653
Final file still exists if you want to combine it with other runs of the image: redis:5.0.3.final_tmp_file (rename it if you re-use the script in this case)
```

The trimmed image is called sha256:525578ca12108b7fac9bcb3d152c949a74506f606e1e1282663a5a7ccdf3e653 but you can tag it to any name. Read more if you want to learn on how to merge multiple runs of a docker image into one trimmed image.

From the script file:
```
# Usage: DOCKER_ARGS="--rm -it" oneshot_trim.sh <image name> <run time parameters>
# set DOCKER_RUN_ARGS to change the runtime parameters for docker run
# If running in mac or windows, make sure your working directory is in a mountable directory (in mac os-x it's /Users by default)
```

# How-to

This part will explain how to first collect which files are needed in the docker image, and then how to trim the docker image.

## Instrumenting an docker image for checking which files to keep

This shows you a quick demo for how to trim the docker image redis:5

If you don't have the image, let's pull it first:

```
$ docker pull redis:5
Status: Downloaded newer image for redis:5
```

First we need to create an instrumentation docker image to monitor which files are used by the image, we'll call it redis:5_instrument

```
$ python docker_prep_instrument_image.py redis:5 redis:5_instrument
redis:5_instrument
```

Let's create a file that will capture the file access (not doing this step will cause an error later on, and an empty directory will be created which will need to be deleted):

```
$ touch strace_output1
```

Now let's run it and capture some file access:
```
$ docker run -it --rm --cap-add=SYS_PTRACE -v `pwd`/strace_output1:/tmp/strace_output redis:5_instrument
7:C 21 Jan 2019 08:03:00.367 # oO0OoO0OoO0Oo Redis is starting oO0OoO0OoO0Oo
```

After you finish interacting with the container in a meaningful way that captures your use-cases (you can run it multiple times with a new strace_output file each time) let's parse the output (you can pass multiple output files here):

```
$ python docker_parse_strace.py redis:5 strace_output1 > parsed_strace_output
```

Now we need to extract the dynamic loader name (if exists):

```
$ docker run -it --entrypoint="" -v `pwd`/parsed_strace_output:/tmp/parsed_output --rm redis:5_instrument /tmp/instrumentation/file -m /tmp/instrumentation/magic.mgc -b -L -f /tmp/parsed_output > file_output
```

And add it to our list:

```
$ python docker_parse_file.py file_output >> parsed_strace_output
```

Don't forget to remove the redis:5_instrument image after you don't need it anymore:

```
$ docker rmi redis:5_instrument
```

## Trimming a docker image

Let's take the image redis:5 and trim it given the parsed_strace_output from the previous stage.

First, running this command will make sure to process from a file list, the symbolic links and directories as well (that exist in the docker image):

```
$ python docker_scan_image.py redis:5 parsed_strace_output > final_file_list
```

Then, we can use the output of that command (redirected to a file called final_file_list) to trim down the original docker image to a new one (which the name will be written in the end):

```
$ python docker_trim.py redis:5 final_file_list
sha256:e8f1b99ac811951fb0b746940ff3715520bf00a5ee3e37f54a4436c25afa5d8c
```

The produced docker image should have the same metadata (including ENTRYPOINT and CMD) of the original image so you can use it just as before.

If you want a saner name for the image, you can tag it (replace the hash from the previous command output):

```
$ docker tag sha256:e8f1b99ac811951fb0b746940ff3715520bf00a5ee3e37f54a4436c25afa5d8c redis:5_trimmed
```

We can now compare the new image sizes:
```
$ docker images redis:5
REPOSITORY          TAG                 IMAGE ID            CREATED             SIZE
redis               5                   5d2989ac9711        3 weeks ago         95MB

$ docker images redis:5_trimmed
REPOSITORY          TAG                 IMAGE ID            CREATED             SIZE
redis               5_trimmed           e8f1b99ac811        21 minutes ago      14MB
```
We can see a reduction in size from 95MB to 14MB.
