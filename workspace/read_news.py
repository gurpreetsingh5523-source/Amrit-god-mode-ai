#!/usr/bin/env python3

import json

def read_and_print_headlines(filename):
    try:
        with open(filename, 'r') as file:
            news_data = json.load(file)
            for headline in news_data["headlines"]:
                print(headline)
    except FileNotFoundError:
        print(f"Error: {filename} not found.")
    except KeyError:
        print("Error: The expected key was not found in the JSON data.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    read_and_print_headlines("latest_ai_news.json")