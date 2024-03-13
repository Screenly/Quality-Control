import os
import random
import sys
from datetime import datetime
from typing import Any, Dict, List

import requests
from retry import retry

API_TOKEN = os.environ.get("SCREENLY_API_TOKEN")
REQUEST_HEADERS = {
    "Authorization": f"Token {API_TOKEN}",
    "Content-Type": "application/json",
}
SCREEN_SYNC_THRESHOLD = 60 * 6  # 6 minutes
PLAYLIST_PREFIX = "QC"


def get_ten_random_assets():
    """
    Return 10 random assets in the account.
    """

    response = requests.get(
        'https://api.screenlyapp.com/api/v4/assets?select=id&type=in.("appweb","audio","edge-app","image","video","web")&status=in.("finished","processing")',
        headers=REQUEST_HEADERS,
    )
    response.raise_for_status()

    asset_count = len(response.json())

    # Pick 10 random assets
    asset_list = []
    for i in range(10):
        random_index = random.randint(0, asset_count - 1)
        asset_list.append(response.json()[random_index]["id"])

    return asset_list


def get_screens() -> List[Dict[str, Any]]:
    """
    Return a list of screens in the account.
    """

    response = requests.get('https://api.screenlyapp.com/api/v4/screens?select=id,name,hostname,status,in_sync&type=eq.hardware&is_enabled=eq.true', headers=REQUEST_HEADERS)
    response.raise_for_status()
    return response.json()


@retry(AssertionError, tries=10, delay=SCREEN_SYNC_THRESHOLD / 10)
def wait_for_screens_to_sync():
    """
    Waits for all screens to be in sync.
    """

    try:
        screens = get_screens()
    except requests.HTTPError as error:
        print(f"Unable to fetch screens: {error}: {error.response.content}")
        sys.exit(1)
    except Exception as error:
        print(f"Unable to fetch screens: {error}")
        sys.exit(1)

    if all(screen['in_sync'] for screen in screens):
        return

    screens_not_in_sync = [screen for screen in screens if not screen['in_sync']]

    print(f"...waiting for {len(screens_not_in_sync)} screen(s) to sync")

    for screen in screens_not_in_sync:
        print(f"{screen['name']}({screen['hostname']}) not in sync: {screen['status'].lower()}")

    raise AssertionError("Not all screens synchronized")


def get_qc_playlist_ids():
    """
    Get all playlist starting with 'PLAYLIST_PREFIX'.
    """

    response = requests.get("https://api.screenlyapp.com/api/v3/playlists/", headers=REQUEST_HEADERS)
    response.raise_for_status()

    qc_playlists = []
    for playlist in response.json():
        if playlist["title"].startswith(PLAYLIST_PREFIX):
            qc_playlists.append(playlist["id"])

    return qc_playlists


def delete_playlist(playlist_id):
    """
    Delete a playlist.
    """
    response = requests.delete(
        f"https://api.screenlyapp.com/api/v3/playlists/{playlist_id}/",
        headers=REQUEST_HEADERS,
    )
    return response.ok


def create_qc_playlist():
    """
    Create a new QC playlist with random assets.
    """

    current_date = datetime.utcnow()
    playlist_name = f"{PLAYLIST_PREFIX} {current_date.strftime('%Y-%m-%d @ %H:%M:%S')}"

    assets = []
    for asset in get_ten_random_assets():
        assets.append({"id": asset, "duration": 10})

    payload = {
        "title": playlist_name,
        "groups": [{"id": "all-screens"}],
        "is_enabled": True,
        "assets": assets,
        "predicate": "TRUE",
    }

    response = requests.post(
        "https://api.screenlyapp.com/api/v3/playlists/",
        headers=REQUEST_HEADERS,
        json=payload,
    )
    response.raise_for_status()


def main():
    if not API_TOKEN:
        print("API_TOKEN is not set")
        sys.exit(1)

    # We don't need this as if we were fixing something that should
    # improve sync after the playlist update, we would never be able
    # to detect recovery after our fix without manual interaction
    # print("Performing initial screen sync check...")
    # wait_for_screens_to_sync()

    try:
        qc_playlists = get_qc_playlist_ids()
    except requests.HTTPError as error:
        print(f"Unable to fetch playlists: {error.response.json()}")
        sys.exit(1)
    except Exception as error:
        print(f"Unable to fetch playlists: {error}")
        sys.exit(1)

    print("Cleaning up old QC playlist...")
    if len(qc_playlists) > 0:
        print("Found a QC playlist. Deleting it...")
        for playlist in qc_playlists:
            delete_playlist(playlist)

    print("Creating new QC playlist...")
    try:
        create_qc_playlist()
    except requests.HTTPError as error:
        print(f"Unable to create playlist: {error.response.json()}")
        sys.exit(1)
    except Exception as error:
        print(f"Unable to create playlist: {error}")
        sys.exit(1)

    print("Waiting for screens to sync...")
    wait_for_screens_to_sync()

    print("Automated QC completed successfully! :)")


if __name__ == "__main__":
    main()
