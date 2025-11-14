import requests
import json

from config import YANDEX_GEOCODER_TOKEN as YANDEX_API_KEY
YANDEX_API_URL = "https://geocode-maps.yandex.ru/1.x/"
ALLOWED_COUNTRIES = ['RU', 'KZ'] # Russia and Kazakhstan

def get_simple_locality_variants(search_string: str):
    """
    Makes a single, simple request to the Yandex Geocoder API and filters
    for localities in Russia (RU) and Kazakhstan (KZ).
    """
    params = {
        'apikey': YANDEX_API_KEY,
        'geocode': search_string,
        'format': 'json',
        'results': 100,
        'kind': 'locality',
    }

    print(f"\nSearching for: '{search_string}'")
    try:
        response = requests.get(YANDEX_API_URL, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        feature_members = data.get('response', {}).get('GeoObjectCollection', {}).get('featureMember', [])

        variants = []

        for member in feature_members:
            geo_object = member.get('GeoObject', {})
            metadata = geo_object.get('metaDataProperty', {}).get('GeocoderMetaData', {})
            country_code = metadata.get('Address', {}).get('country_code')
            full_text = metadata.get('text')
            if country_code in ALLOWED_COUNTRIES: variants.append(f"{full_text} ({country_code})")

        return variants

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except requests.exceptions.RequestException as err:
        print(f"An error occurred: {err}")
    except json.JSONDecodeError:
        print("Error: Failed to decode JSON response from API.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    return []

# --- Example Usage ---

if __name__ == "__main__":

    query = input("What would you like to search for?: ")
    while query != '':
        res = get_simple_locality_variants(query)
        print(len(res))
        for variant in res: print(variant)
        query = input("What would you like to search for?: ")

print("\nScript finished.")