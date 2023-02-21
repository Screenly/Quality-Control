import requests

def test_shortlinks():
    # Short links in the UI
    PI3_SHORTLINK = 'https://go.srly.io/Pi3-20'
    PI3_SHORTLINK_MD5 = 'https://go.srly.io/Pi3-20-md5'
    PI4_SHORTLINK = 'https://go.srly.io/RPi4'
    PI4_SHORTLINK_MD5 = 'https://go.srly.io/RPi4_md5'

    # Test the shortlinks for the Pi3 and Pi4
    assert requests.head(PI3_SHORTLINK, allow_redirects=True).status_code == 200
    assert requests.head(PI3_SHORTLINK_MD5, allow_redirects=True).status_code == 200
    assert requests.head(PI4_SHORTLINK, allow_redirects=True).status_code == 200
    assert requests.head(PI4_SHORTLINK_MD5, allow_redirects=True).status_code == 200
    print("All shortlinks are working")


def test_raspberry_pi_imager_url(json_path):
    json_response = requests.get(json_path)

    if not json_response.ok:
        raise Exception("Unable to fetch JSON file")

    json_data = json_response.json()
    for os in json_data['os_list']:
        print(os['url'])
        assert requests.head(os['url'], allow_redirects=True).status_code == 200


def main():
    test_shortlinks()
    test_raspberry_pi_imager_url('https://anthias.screenly.io/rpi-imager.json')
    test_raspberry_pi_imager_url('https://disk-images.screenlyapp.com/pi-imaging-utility.json')

if __name__ == "__main__":
    main()