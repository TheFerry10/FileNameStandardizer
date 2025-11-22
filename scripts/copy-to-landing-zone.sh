#!/bin/bash



mkdir -p scripts/landingzone

# Copy all files with .jpg and .mp4 extensions from scripts/source/ to scripts/landingzone/
cp -u -v scripts/source/*.jpg scripts/landingzone/
cp -u -v scripts/source/*.mp4 scripts/landingzone/
