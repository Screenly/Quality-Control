import os
import sys
import random
import requests
from retry import retry
from datetime import datetime

API_TOKEN = os.environ.get('SCREENLY_API_TOKEN')
REQUEST_HEADERS = {
        'Authorization': f'Token {API_TOKEN}',
        'Content-Type': 'application/json'
    }

def get_ten_random_assets():
    """
    Return 10 random assets in the account.
    """

    response = requests.get('https://api.screenlyapp.com/api/v3/assets/',
        headers=REQUEST_HEADERS
    )

    if not response.ok:
        raise Exception("Unable to fetch assets")

    asset_count = len(response.json())

    # Pick 10 random assets
    asset_list = []
    for i in range(10):
        random_index = random.randint(0, asset_count - 1)
        asset_list.append(response.json()[random_index]['id'])

    return asset_list


def get_screen_list():
    """
    Return a list of screens in the account.
    """

    response = requests.get('https://api.screenlyapp.com/api/v3/screens/',
        headers=REQUEST_HEADERS
    )

    if not response.ok:
        raise Exception("Unable to fetch screens")

    return [screen['id'] for screen in response.json()]


def ensure_screen_in_sync(screen_id):
    response = requests.get(f'https://api.screenlyapp.com/api/v3/screens/{screen_id}/',
        headers=REQUEST_HEADERS
    )

    if not response.ok:
        raise Exception("Unable to fetch screen")

    assert response.json()['in_sync'] == True

@retry(AssertionError, tries=20, delay=10)
def wait_for_screens_to_sync():
    try:
        screens = get_screen_list()
    except:
        print("Unable to fetch screens")
        sys.exit(1)

    print("...")

    for screen in screens:
        ensure_screen_in_sync(screen)


def get_qc_playlists():
    response = requests.get('https://api.screenlyapp.com/api/v3/playlists/',
        headers=REQUEST_HEADERS
    )

    if not response.ok:
        raise Exception("Unable to fetch playlists")

    qc_playlists = []
    for playlist in response.json():
        if playlist['title'].startswith('QC'):
            print(playlist)
            qc_playlists.append(playlist['id'])

    return qc_playlists


def delete_playlist(playlist_id):
    response = requests.delete(f'https://api.screenlyapp.com/api/v3/playlists/{playlist_id}/',
        headers=REQUEST_HEADERS
    )
    return response.ok


def create_qc_playlist():
    current_date = datetime.utcnow()
    playlist_name = f"QC {current_date.strftime('%Y-%m-%d @ %H:%M:%S')}"

    assets = []
    for asset in get_ten_random_assets():
        assets.append({"id": asset, "duration": 10})

    payload = {
        'title': playlist_name,
        'groups': [{'id': 'all-screens'}],
        'is_enabled': True,
        'assets': assets,
        "predicate": "TRUE"
    }

    response = requests.post('https://api.screenlyapp.com/api/v3/playlists/',
        headers=REQUEST_HEADERS,
        json=payload
    )

    print(response.content)

    if not response.ok:
        raise Exception("Unable to create playlist")


def main():
    if not API_TOKEN:
        print("API_TOKEN is not set")
        sys.exit(1)

    print("Performing initial screen sync check...")
    wait_for_screens_to_sync()

    try:
        qc_playlists = get_qc_playlists()
    except:
        print("Unable to fetch playlists")
        sys.exit(1)

    print("Cleaning up old QC playlist...")
    if len(qc_playlists) > 0:
        print("Found a QC playlist. Deleting it...")
        for playlist in qc_playlists:
            delete_playlist(playlist)

    print("Creating new QC playlist...")
    try:
        create_qc_playlist()
    except:
        print("Unable to create playlist")
        sys.exit(1)

    print("Waiting for screens to sync...")
    wait_for_screens_to_sync()


if __name__ == "__main__":
    main()