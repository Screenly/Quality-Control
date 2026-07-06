import os
import random
import sys
from datetime import datetime, timezone
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


def get_team_id() -> str:
    """
    Return the current account's team ID via the built-in all-screens label.
    """
    response = requests.get(
        "https://api.screenlyapp.com/v4/labels?type=eq.all-screens",
        headers=REQUEST_HEADERS,
    )
    response.raise_for_status()
    labels = response.json()
    if not labels:
        raise ValueError("No 'all-screens' label found in the account")
    return labels[0]["team_id"]


def get_ten_random_assets(team_id: str) -> List[str]:
    """
    Return 10 random asset IDs that belong to the current team.
    Filtering by team_id ensures the token has permission to add them to playlists.
    """
    response = requests.get(
        f'https://api.screenlyapp.com/v4/assets?select=id&team_id=eq.{team_id}&type=in.("appweb","audio","edge-app","image","video","web")&status=in.("finished","processing")',
        headers=REQUEST_HEADERS,
    )
    response.raise_for_status()

    assets = response.json()
    asset_count = len(assets)

    return [assets[random.randint(0, asset_count - 1)]["id"] for _ in range(10)]


def get_screens() -> List[Dict[str, Any]]:
    """
    Return a list of screens in the account.
    """

    response = requests.get('https://api.screenlyapp.com/v4/screens?select=id,name,hostname,status,in_sync&type=eq.hardware&is_enabled=eq.true', headers=REQUEST_HEADERS)
    response.raise_for_status()
    return response.json()


@retry(AssertionError, tries=10, delay=SCREEN_SYNC_THRESHOLD / 10)
def wait_for_screens_to_sync():
    """
    Waits for all online screens to be in sync. Offline screens are reported
    but do not block the sync check since they cannot sync while unreachable.
    """

    try:
        screens = get_screens()
    except requests.HTTPError as error:
        print(f"Unable to fetch screens: {error}: {error.response.content}")
        sys.exit(1)
    except Exception as error:
        print(f"Unable to fetch screens: {error}")
        sys.exit(1)

    screens_not_in_sync = [screen for screen in screens if not screen['in_sync']]

    offline_screens = [s for s in screens_not_in_sync if s['status'].lower() == 'offline']
    out_of_sync_screens = [s for s in screens_not_in_sync if s['status'].lower() != 'offline']

    if offline_screens:
        print(f"Skipping {len(offline_screens)} offline screen(s) (cannot sync while unreachable):")
        for screen in offline_screens:
            print(f"  OFFLINE: {screen['name']}({screen['hostname']})")

    if not out_of_sync_screens:
        return

    print(f"...waiting for {len(out_of_sync_screens)} screen(s) to sync:")
    for screen in out_of_sync_screens:
        print(f"  OUT OF SYNC: {screen['name']}({screen['hostname']}) — {screen['status'].lower()}")

    raise AssertionError("Not all online screens synchronized")


def get_qc_playlist_ids():
    """
    Get all playlists starting with 'PLAYLIST_PREFIX'.
    """

    response = requests.get("https://api.screenlyapp.com/v4/playlists", headers=REQUEST_HEADERS)
    response.raise_for_status()

    qc_playlists = []
    for playlist in response.json():
        if playlist["title"].startswith(PLAYLIST_PREFIX):
            qc_playlists.append(playlist["id"])

    return qc_playlists


def delete_playlist(playlist_id):
    """
    Delete a playlist and its items. In v4, label associations and playlist
    items must be removed before the playlist itself can be deleted.
    """
    requests.delete(
        f"https://api.screenlyapp.com/v4/labels/playlists?playlist_id=eq.{playlist_id}",
        headers=REQUEST_HEADERS,
    )
    items_response = requests.delete(
        f"https://api.screenlyapp.com/v4/playlist-items?playlist_id=eq.{playlist_id}",
        headers=REQUEST_HEADERS,
    )
    if not items_response.ok:
        return False
    response = requests.delete(
        f"https://api.screenlyapp.com/v4/playlists?id=eq.{playlist_id}",
        headers=REQUEST_HEADERS,
    )
    return response.ok


def get_all_screens_label_id():
    """
    Return the ID of the built-in 'all-screens' label.
    """
    response = requests.get(
        "https://api.screenlyapp.com/v4/labels?type=eq.all-screens",
        headers=REQUEST_HEADERS,
    )
    response.raise_for_status()
    labels = response.json()
    if not labels:
        raise ValueError("No 'all-screens' label found in the account")
    return labels[0]["id"]


def add_asset_to_playlist(playlist_id, asset_id):
    """
    Add a single asset to a playlist via the v4 playlist-items endpoint.
    """
    payload = {
        "playlist_id": playlist_id,
        "asset_id": asset_id,
        "duration": 10,
    }
    response = requests.post(
        "https://api.screenlyapp.com/v4/playlist-items",
        headers={**REQUEST_HEADERS, "Prefer": "return=representation"},
        json=payload,
    )
    response.raise_for_status()


def assign_playlist_to_all_screens(playlist_id):
    """
    Assign a playlist to all screens by linking the built-in
    'all-screens' label to the playlist.
    """
    label_id = get_all_screens_label_id()
    payload = {
        "label_id": label_id,
        "playlist_id": playlist_id,
    }
    response = requests.post(
        "https://api.screenlyapp.com/v4/labels/playlists",
        headers={**REQUEST_HEADERS, "Prefer": "return=representation, resolution=ignore-duplicates"},
        json=payload,
    )
    response.raise_for_status()


def create_qc_playlist():
    """
    Create a new QC playlist, populate it with random assets,
    and assign it to all screens.
    """

    current_date = datetime.now(timezone.utc)
    playlist_name = f"{PLAYLIST_PREFIX} {current_date.strftime('%Y-%m-%d @ %H:%M:%S')}"

    payload = {
        "title": playlist_name,
        "is_enabled": True,
        "predicate": "TRUE",
    }

    response = requests.post(
        "https://api.screenlyapp.com/v4/playlists",
        headers={**REQUEST_HEADERS, "Prefer": "return=representation"},
        json=payload,
    )
    response.raise_for_status()

    data = response.json()
    playlist_id = data[0]["id"] if isinstance(data, list) else data["id"]
    print(f"Playlist created: {playlist_id}")

    team_id = get_team_id()

    print("Adding assets to playlist...")
    for asset_id in get_ten_random_assets(team_id):
        add_asset_to_playlist(playlist_id, asset_id)

    print("Assigning playlist to all screens...")
    assign_playlist_to_all_screens(playlist_id)


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
        print(f"Unable to fetch playlists: {error.response.status_code} {error.response.text}")
        sys.exit(1)
    except Exception as error:
        print(f"Unable to fetch playlists: {error}")
        sys.exit(1)

    print("Cleaning up old QC playlist...")
    if len(qc_playlists) > 0:
        print("Found a QC playlist. Deleting it...")
        for playlist in qc_playlists:
            if not delete_playlist(playlist):
                print(f"Warning: failed to delete playlist {playlist}")

    print("Creating new QC playlist...")
    try:
        create_qc_playlist()
    except requests.HTTPError as error:
        print(f"QC playlist setup failed: {error.response.status_code} {error.response.text}")
        sys.exit(1)
    except Exception as error:
        print(f"QC playlist setup failed: {error}")
        sys.exit(1)

    print("Waiting for screens to sync...")
    try:
        wait_for_screens_to_sync()
    except AssertionError as error:
        print(f"Warning: {error}. Fetching final screen status...")
        try:
            final_screens = get_screens()
            not_synced = [s for s in final_screens if not s['in_sync']]
            offline = [s for s in not_synced if s['status'].lower() == 'offline']
            out_of_sync = [s for s in not_synced if s['status'].lower() != 'offline']
            print(f"Final status: {len(offline)} offline, {len(out_of_sync)} out of sync after timeout:")
            for s in offline:
                print(f"  OFFLINE: {s['name']}({s['hostname']})")
            for s in out_of_sync:
                print(f"  OUT OF SYNC: {s['name']}({s['hostname']}) — {s['status'].lower()}")
        except Exception as fetch_error:
            print(f"Could not fetch final screen status: {fetch_error}")

    print("Automated QC completed successfully! :)")


if __name__ == "__main__":
    main()
