#!/bin/bash -x

# Absolute path to this script, e.g. /home/user/bin/foo.sh
SCRIPT=$(readlink -f "$0")
# Absolute path this script is in, thus /home/user/bin
SCRIPT_DIR=$(dirname "$SCRIPT")

ROOT_DIR=$(readlink -f "$SCRIPT_DIR/..")
BUILD_DIR="$ROOT_DIR/build"
SRC_DIR="$ROOT_DIR/src"
CONFIG_DIR="$ROOT_DIR/config"
SHARED_DIR="$HOME/shared"

mkdir -p $BUILD_DIR
mkdir -p $SHARED_DIR

rsync -a $SRC_DIR/python/ $BUILD_DIR/python
rsync -a $VIRTUAL_ENV/lib/python3.5/site-packages/ $BUILD_DIR/python
rsync -a $CONFIG_DIR/stellar_stack.yml $BUILD_DIR/stellar_stack.yml

aws cloudformation package --template-file $BUILD_DIR/stellar_stack.yml --output-template-file $SHARED_DIR/stellar_stack.yml --s3-bucket scd-code


