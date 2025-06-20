import os
import random
import sys
import argparse
import re
from datetime import datetime
from typing import Any, Dict, List

from google.cloud import storage
from datetime import datetime, timezone, timedelta

import requests
from retry import retry


API_TOKEN = os.environ.get("SCREENLY_API_TOKEN")
REQUEST_HEADERS = {
    "Authorization": f"Token {API_TOKEN}",
    "Content-Type": "application/json",
}

def list_blobs(hostname: str):
    # Initialize GCS client
    client = storage.Client(project='srly-prod')

    # Set your bucket name and the prefix (like a directory)
    bucket_name = 'srly-prod-uploads'
    prefix = f'{hostname}/logs/'  # Optional, set '' for all files

    # Time range: now and 24 hours ago
    now = datetime.now(timezone.utc)
    cutoff_time = now - timedelta(hours=24)

    # Access the bucket
    bucket = client.bucket(bucket_name)

    # List blobs (files) with prefix
    blobs = client.list_blobs(bucket, prefix=prefix)

    # Filter blobs created within the last 24 hours
    recent_blobs = [blob for blob in blobs if blob.time_created >= cutoff_time]

    return recent_blobs



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
        print(version_tail)
        if not version_tail.startswith(args.client_version):
            version_mismatch_screens.append(screen)

    print(screens)


    if version_mismatch_screens:
        print(f"Version mismatch for {len(version_mismatch_screens)} screens")
        for screen in version_mismatch_screens:
            print(f"Screen {screen['id']} has version {screen['report']['client_version']}")
        sys.exit(1)

    for screen in screens:
        print(screen['hostname'])
        for blob in list_blobs(screen['hostname']):
            print(blob.name)



if __name__ == "__main__":
    main()