# Automated Quality Control for Screenly and Anthias

## `test_disk_image_downloads.py`

[![Test Disk Images](https://github.com/Screenly/Quality-Control/actions/workflows/test-disk-images.yml/badge.svg)](https://github.com/Screenly/Quality-Control/actions/workflows/test-disk-images.yml)

This script runs nightly to ensure that all disk images are available. Includes both the shortlinks in the dashboard, as well as parsing the JSON file for Rasperry Pi Imager.

## `automated_quality_control.py`

[![Automated Quality Control (against real devices)](https://github.com/Screenly/Quality-Control/actions/workflows/automated-quality-control.yml/badge.svg)](https://github.com/Screenly/Quality-Control/actions/workflows/automated-quality-control.yml)

This script runs every hour and schedules random assets against *real* Screenly devices and ensures that they sync the assets properly.