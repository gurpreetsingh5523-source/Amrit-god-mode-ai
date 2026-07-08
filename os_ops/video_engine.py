import requests
from typing import Optional, Union

def fetch_data(url: str) -> Union[dict, None]:
    """
    Fetch data from a given URL and return it as a dictionary.
    
    Parameters:
    - url (str): The URL from which to fetch the data.
    
    Returns:
    - dict: A dictionary containing the data fetched from the URL.
    - None: If an error occurs during the fetch operation.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None


def process_data(data: dict) -> Optional[str]:
    """
    Process the fetched data and return a formatted string.
    
    Parameters:
    - data (dict): The data to be processed.
    
    Returns:
    - str: A formatted string containing the processed data.
    - None: If 'data' is not a dictionary or does not contain the expected keys.
    """
    if not isinstance(data, dict):
        print("Invalid input: Data is not a dictionary.")
        return None
    
    if "name" in data and "age" in data:
        return f"Name: {data['name']}, Age: {data['age']}"
    else:
        print("Invalid data format: Missing keys.")
        return None


def main(url: str) -> Optional[str]:
    """
    Main function to fetch and process data.
    
    Parameters:
    - url (str): The URL from which to fetch the data.
    
    Returns:
    - str: A formatted string containing the processed data.
    - None: If an error occurs during fetching or processing.
    """
    try:
        data = fetch_data(url)
        if data is not None:
            return process_data(data)
        else:
            print("Failed to fetch data.")
            return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


# Example usage:
if __name__ == "__main__":
    url = "https://api.example.com/data"
    result = main(url)
    if result is not None:
        print(result)