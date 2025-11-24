#!/bin/bash

if [ -d "scripts/source/" ]; then
    echo "Deleting scripts/source/ directory..."
    rm -rf scripts/source/
    echo "Deleted scripts/source/ directory."
else
    echo "scripts/source/ directory does not exist. No action taken."
fi

if [ -d "scripts/landingzone/" ]; then
    echo "Deleting scripts/landingzone/ directory..."
    rm -rf scripts/landingzone/
    echo "Deleted scripts/landingzone/ directory."
else
    echo "scripts/landingzone/ directory does not exist. No action taken."
fi
