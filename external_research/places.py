import requests

def get_places(query, api_key, fields=None):
    """
    Get places from the Places API.

    Args:
        query (str): The search text.
        api_key (str): The API key for authentication.
        fields (str): The field mask. Default is None.

    Returns:
        dict: A dictionary containing the result.
    """
    url = "https://places.googleapis.com/v1/places:searchText"
    
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": fields if fields else "*"
    }
    
    data = {
        "textQuery": query,
        "pageSize": 10  # or any other value you want to use for pageSize
    }

    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()  # Raises an HTTPError for bad responses

    return response.json()

def main():
    query = "dogbeach"
    api_key = 'AIzaSyAqnSRo-RQzU6h56_5FVM9r15STdZsYJ28'  # Replace with your actual API key
    fields = 'places.id,places.displayName,places.formattedAddress'

    try:
        response = get_places(query, api_key, fields)

        places = response.get('places', [])
        print("Places:")
        for place in places:
            print(f"ID: {place['id']}, Name: {place['displayName']['text']}, {place['formattedAddress']}")

        if 'nextPageToken' in response:
            print(f"Next page token: {response['nextPageToken']}")

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()