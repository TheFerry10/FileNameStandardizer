#!/bin/bash

# delete scripts/landingzone/ directory if it exists
if [ -d "scripts/source/" ]; then
    echo "Deleted existing scripts/source/ directory."
    rm -rf scripts/source/
fi

# create scripts/source/ directory
mkdir -p scripts/source/

# create empty files in scripts/source/ directory
echo "Creating empty files in scripts/source/ directory..."
touch scripts/source/IMG-20240721-WA0007.jpg
touch scripts/source/VID-20240721-WA0000.mp4
touch scripts/source/20240724_182842.jpg
touch scripts/source/20240724_182842.mp4
touch scripts/source/document.pdf
