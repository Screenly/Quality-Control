import os
import random
import sys
import argparse
import re
import zstandard as zstd
from datetime import datetime
from typing import Any, Dict, List, Optional

from google.cloud import storage
from datetime import datetime, timezone, timedelta

import requests
from retry import retry


API_TOKEN = os.environ.get("SCREENLY_API_TOKEN")
REQUEST_HEADERS = {
    "Authorization": f"Token {API_TOKEN}",
    "Content-Type": "application/json",
}

def get_latest_log_blob(hostname: str) -> Optional[storage.Blob]:
    """
    Get the most recent log file for a given hostname.
    """
    # Initialize GCS client
    client = storage.Client(project='srly-prod')

    # Set your bucket name and the prefix (like a directory)
    bucket_name = 'srly-prod-uploads'
    prefix = f'{hostname}/logs/'

    # Access the bucket
    bucket = client.bucket(bucket_name)

    # List blobs (files) with prefix
    blobs = list(client.list_blobs(bucket, prefix=prefix))

    if not blobs:
        return None

    # Sort by creation time and return the most recent
    latest_blob = max(blobs, key=lambda blob: blob.time_created)
    return latest_blob

def download_blob_content(blob: storage.Blob) -> str:
    """
    Download and return the content of a blob as a string.
    Handles both compressed (.zst) and uncompressed log files.
    """
    try:
        # Download the blob content as bytes
        content_bytes = blob.download_as_bytes()

        # Check if this is a compressed .zst file
        if blob.name.endswith('.zst'):
            # Decompress the content using zstandard
            dctx = zstd.ZstdDecompressor()
            decompressed_bytes = dctx.decompress(content_bytes)
            # Decode to string (assuming UTF-8 encoding)
            content_str = decompressed_bytes.decode('utf-8')
        else:
            # For uncompressed files, decode directly
            content_str = content_bytes.decode('utf-8')

        return content_str
    except Exception as e:
        print(f"Error downloading/decompressing blob {blob.name}: {e}")
        return ""

def check_for_oom_errors(log_content: str) -> List[str]:
    """
    Check log content for Out of Memory (OOM) errors.
    Returns a list of matching OOM error lines.
    """
    oom_patterns = [
        r'out of memory',
        r'OOM',
        r'oom',
        r'Out of memory',
        r'killed.*memory',
        r'memory.*killed',
        r'Cannot allocate memory',
        r'fatal.*memory',
        r'segmentation fault.*memory'
    ]

    oom_errors = []
    lines = log_content.split('\n')

    for line in lines:
        for pattern in oom_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                oom_errors.append(line.strip())
                break  # Avoid duplicate matches for the same line

    return oom_errors

def get_screens() -> List[Dict[str, Any]]:
    """
    Return a list of screens in the account.
    """

    response = requests.get('https://api.screenlyapp.com/api/v4.1/screens?select=id,name,hostname,groups:labels!label_screen!inner(human_name),report:screen_reports(client_version)&type=eq.hardware&groups.human_name=eq.candidate&is_enabled=eq.true&', headers=REQUEST_HEADERS)
    response.raise_for_status()
    return response.json()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-version", type=str, required=True)
    args = parser.parse_args()

    screens = get_screens()
    screens = [screen for screen in screens if '-armhf-' not in screen['report']['client_version']]
    version_mismatch_screens = []
    for screen in screens:
        version = screen['report']['client_version']
        version_tail = re.search(r'.*-(\d+\.\d+\.\d+-.*)', version).group(1)
        if not version_tail.startswith(args.client_version):
            version_mismatch_screens.append(screen)

    print(f"Found {len(screens)} screens to check")

    if version_mismatch_screens:
        print(f"Version mismatch for {len(version_mismatch_screens)} screens")
        for screen in version_mismatch_screens:
            print(f"Screen {screen['id']} has version {screen['report']['client_version']}")
        sys.exit(1)

    oom_screens = []

    for screen in screens:
        hostname = screen['hostname']
        print(f"\nChecking screen: {hostname}")

        # Get the latest log file
        latest_blob = get_latest_log_blob(hostname)

        if not latest_blob:
            print(f"  No log files found for {hostname}")
            continue

        print(f"  Latest log file: {latest_blob.name}")
        print(f"  Created: {latest_blob.time_created}")

        # Download and check log content
        log_content = download_blob_content(latest_blob)

        if not log_content:
            print(f"  Could not download log content for {hostname}")
            continue

        # Check for OOM errors
        oom_errors = check_for_oom_errors(log_content)
        if not oom_errors:
            print(f"  ✅ No OOM errors found")
        else:
            print(f"  ⚠️  FOUND {len(oom_errors)} OOM ERROR(S):")
            oom_screens.append({
                'hostname': hostname,
                'screen_id': screen['id'],
                'log_file': latest_blob.name,
                'oom_errors': oom_errors
            })
            for error in oom_errors[:5]:  # Show first 5 errors
                print(f"    {error}")
            if len(oom_errors) > 5:
                print(f"    ... and {len(oom_errors) - 5} more errors")

    # Summary report
    print(f"\n{'='*60}")
    print(f"SUMMARY REPORT")
    print(f"{'='*60}")
    print(f"Total screens checked: {len(screens)}")
    print(f"Screens with OOM errors: {len(oom_screens)}")

    if not oom_screens:
        print(f"\n✅ No OOM errors found in any screens!")
        return

    print(f"\nScreens with OOM errors:")
    for screen_info in oom_screens:
        print(f"  - {screen_info['hostname']} (ID: {screen_info['screen_id']})")
        print(f"    Log file: {screen_info['log_file']}")
        print(f"    OOM errors found: {len(screen_info['oom_errors'])}")

    sys.exit(1)


if __name__ == "__main__":
    main()