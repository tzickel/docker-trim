#!/usr/bin/env bash
set -e

# Usage: DOCKER_ARGS="--rm -it" oneshot_trim.sh <image name> <run time parameters>
# set DOCKER_RUN_ARGS to change the runtime parameters for docker run
# If running in mac or windows, make sure your working directory is in a mountable directory (in mac os-x it's /Users by default)

[[ -z "$1" ]] && { echo "Please specifiy a docker image"; exit 1; }
IMAGE_NAME="$1"
DOCKER_ARGS=${DOCKER_ARGS:--it --rm}
shift
# If image does not exist, pull it.
[[ "$(docker images -q ${IMAGE_NAME} 2> /dev/null)" == "" ]] && docker pull ${IMAGE_NAME}
# Create an instrumentation temporary image
echo "Creating temporary instrumentation image"
INSTRUMENT_IMAGE=`python docker_prep_instrument_image.py ${IMAGE_NAME}`
echo "Running image, press Ctrl-C when done (or finish the container)"
STRACE_TMP_FILE="${IMAGE_NAME}.strace_tmp_file"
# TODO check for file existance (and not directory)
touch ${STRACE_TMP_FILE}
# Run the instrumentation image, and output the file access i/o to STRACE_TMP_FILE
set +e
docker run ${DOCKER_ARGS} --cap-add=SYS_PTRACE --mount type=bind,source="`pwd`/${STRACE_TMP_FILE}",target=/tmp/strace_output ${INSTRUMENT_IMAGE} $@
set -e
echo "Processing file access instrumentation"
STRACE_PARSED_TMP_FILE="${IMAGE_NAME}.strace_parsed_tmp_file"
# Parse the strace output into a file list
python docker_parse_strace.py ${IMAGE_NAME} ${STRACE_TMP_FILE} > ${STRACE_PARSED_TMP_FILE}
# Check out the file types being opened
FILE_TMP_FILE="${IMAGE_NAME}.file_tmp_file"
docker run --entrypoint="" --mount type=bind,source="`pwd`/${STRACE_PARSED_TMP_FILE}",target=/tmp/parsed_output --rm ${INSTRUMENT_IMAGE} /tmp/instrumentation/file -m /tmp/instrumentation/magic.mgc -b -L -f /tmp/parsed_output > ${FILE_TMP_FILE}
# Extract the ELF interpreter being used to run the apps
python docker_parse_file.py ${FILE_TMP_FILE} >> ${STRACE_PARSED_TMP_FILE}
# Remove the temporary instrumentation image
echo "Removing temporary instrumentation image"
docker rmi -f ${INSTRUMENT_IMAGE}
# Parse the file list, and create the final file list
FINAL_TMP_FILE="${IMAGE_NAME}.final_tmp_file"
python docker_scan_image.py ${IMAGE_NAME} ${STRACE_PARSED_TMP_FILE} > ${FINAL_TMP_FILE}
# Create the trimmed image
echo "Creating trimmed image"
python docker_trim.py ${IMAGE_NAME} ${FINAL_TMP_FILE}
echo "Final file still exists if you want to combine it with other runs of the image: ${FINAL_TMP_FILE} (rename it if you re-use the script in this case)"
# Remove temporary files
rm ${STRACE_TMP_FILE} ${STRACE_PARSED_TMP_FILE} ${FILE_TMP_FILE}