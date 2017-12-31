#!/bin/bash -x

# Any subsequent commands which fail will cause the script to exit.
set -e

PYTHON_VERSION=$(python -c 'import sys; print(sys.version_info[:])')
read PYTHON_MAJOR PYTHON_MINOR <<< $(echo $PYTHON_VERSION | awk -F',' '{print substr($1,2) $2}')
PYTHON_DIST=python$PYTHON_MAJOR.$PYTHON_MINOR

# Absolute path to this script
SCRIPT=$(readlink -f "$0")
# Absolute path to script dir
SCRIPT_DIR=$(dirname "$SCRIPT")

ROOT_DIR=$(readlink -f "$SCRIPT_DIR/..")
BUILD_DIR="$ROOT_DIR/build"
SRC_DIR="$ROOT_DIR/src"
CONFIG_DIR="$ROOT_DIR/config"
SHARED_DIR="$HOME/shared"

mkdir -p $BUILD_DIR
mkdir -p $SHARED_DIR

rsync -a $SRC_DIR/python/ $BUILD_DIR/python
rsync -a $VIRTUAL_ENV/lib/$PYTHON_DIST/site-packages/ $BUILD_DIR/python
rsync -a $CONFIG_DIR/stellar_stack.yml $BUILD_DIR/stellar_stack.yml

aws cloudformation package --template-file $BUILD_DIR/stellar_stack.yml --output-template-file $SHARED_DIR/stellar_stack.yml --s3-bucket scd-code


