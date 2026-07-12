#!/usr/bin/env bash
# exit on error
set -o errexit

echo "--- Starting Render Build Command ---"

# 1. Install python dependencies
pip install -r requirements.txt

# 2. Download and extract static ffmpeg/ffprobe binary for audio validation
if [ ! -f "bin/ffmpeg" ] || [ ! -f "bin/ffprobe" ]; then
  echo "Downloading static ffmpeg & ffprobe binaries (Linux x86_64)..."
  mkdir -p bin
  # Fetch John Van Sickle's trusted static build
  curl -L -o ffmpeg.tar.xz https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
  tar -xJf ffmpeg.tar.xz --strip-components=1 -C bin
  rm -f ffmpeg.tar.xz
  echo "✅ ffmpeg and ffprobe installed successfully in bin/ directory"
else
  echo "✅ ffmpeg and ffprobe already present in bin/ directory"
fi

echo "--- Render Build Command Complete ---"
