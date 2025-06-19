import os
import random
import sys
import argparse
from datetime import datetime
from typing import Any, Dict, List

import requests
from retry import retry


API_TOKEN = os.environ.get("SCREENLY_API_TOKEN")
REQUEST_HEADERS = {
    "Authorization": f"Token {API_TOKEN}",
    "Content-Type": "application/json",
}


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
    print(screens)


    version_mismatch_screens = [
    screen for screen in screens
      if screen["report"]["client_version"] != args.client_version
    ]

    if version_mismatch_screens:
        print(f"Version mismatch for {len(version_mismatch_screens)} screens")
        for screen in version_mismatch_screens:
            print(f"Screen {screen['id']} has version {screen['report']['client_version']}")
        sys.exit(1)


if __name__ == "__main__":
    main()