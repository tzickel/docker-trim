#!/usr/bin/env bash
echo Building instrumentation file, this may take awhile...
docker run --rm `docker build -q - < Dockerfile.get_instrumentation` > instrumentation.tar.gz
echo instrumentation.tar.gz created
