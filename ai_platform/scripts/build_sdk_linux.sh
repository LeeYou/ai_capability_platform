#!/bin/bash
set -e
cmake -S . -B build-sdk-linux -DBUILD_SERVER=OFF -DBUILD_JNI_WRAPPERS=ON -DBUILD_SDK_ONLY=ON
cmake --build build-sdk-linux
