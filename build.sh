#!/bin/bash
echo "Running Fixel Backend Build..."
python build/build.py
if [ $? -ne 0 ]; then
    echo "Build failed!"
    exit 1
fi
echo "Build success."
