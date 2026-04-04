import requests

def fetch_data(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        return None

def process_data(data):
    if data is not None:
        for item in data:
            print(item)
    else:
        print("No data received.")

def main():
    api_url = "https://api.example.com/data"
    fetched_data = fetch_data(api_url)
    process_data(fetched_data)

if __name__ == "__main__":
    main()