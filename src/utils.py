import os
import re
import json
import http.client
from src import ids_pattern, CACHE_FILE
from src.cloudflare import get_lists, get_rules, get_list_items

# Function to load the cache from a file
def load_cache() -> dict:
    """
    Loads the cache from the CACHE_FILE if it exists.

    Returns:
        dict: The cache data, or an empty cache if the file doesn't exist.
    """
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as file:
            return json.load(file)
    return {"lists": [], "rules": [], "mapping": {}}

# Function to save the cache to a file
def save_cache(cache: dict) -> None:
    """
    Saves the current cache to the CACHE_FILE.

    Args:
        cache (dict): The cache data to be saved.
    """
    with open(CACHE_FILE, 'w') as file:
        json.dump(cache, file)

# Function to retrieve current lists from cache or fetch them from Cloudflare
def get_current_lists(cache: dict, list_name: str) -> list:
    """
    Retrieves the current lists from cache, or fetches them if not in cache.

    Args:
        cache (dict): The cache object.
        list_name (str): The list name prefix to search for.

    Returns:
        list: The current lists.
    """
    if cache["lists"]:
        return cache["lists"]
    current_lists = get_lists(list_name)
    cache["lists"] = current_lists
    save_cache(cache)
    return current_lists

# Function to retrieve current rules from cache or fetch them from Cloudflare
def get_current_rules(cache: dict, rule_name: str) -> list:
    """
    Retrieves the current rules from cache, or fetches them if not in cache.

    Args:
        cache (dict): The cache object.
        rule_name (str): The rule name to search for.

    Returns:
        list: The current rules.
    """
    if cache["rules"]:
        return cache["rules"]
    current_rules = get_rules(rule_name)
    cache["rules"] = current_rules
    save_cache(cache)
    return current_rules

# Function to get list items from cache or fetch from Cloudflare
def get_list_items_cached(cache: dict, list_id: str) -> list:
    """
    Retrieves list items from cache or fetches them if not cached.

    Args:
        cache (dict): The cache object.
        list_id (str): The ID of the list to retrieve items for.

    Returns:
        list: The list items.
    """
    if list_id in cache["mapping"]:
        return cache["mapping"][list_id]
    items = get_list_items(list_id)
    cache["mapping"][list_id] = items
    save_cache(cache)
    return items

# Function to safely sort lists based on numeric value in the name
def safe_sort_key(list_item: dict) -> int:
    """
    Extracts a numeric key from a list item for safe sorting.

    Args:
        list_item (dict): The list item from which to extract the key.

    Returns:
        int: The extracted numeric key, or infinity if no match is found.
    """
    match = re.search(r'\d+', list_item["name"])
    return int(match.group()) if match else float('inf')

# Function to extract list IDs from a rule's traffic data
def extract_list_ids(rule: dict) -> set:
    """
    Extracts list IDs from the traffic data in a rule.

    Args:
        rule (dict): The rule from which to extract list IDs.

    Returns:
        set: A set of extracted list IDs.
    """
    if not rule or not rule.get('traffic'):
        return set()
    return set(ids_pattern.findall(rule['traffic']))

# Function to delete caches from GitHub Actions
def delete_cache() -> None:
    """
    Deletes cached items from GitHub Actions using the GitHub API.
    """
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
    GITHUB_REPOSITORY = os.getenv('GITHUB_REPOSITORY')
    
    BASE_URL = "api.github.com"
    CACHE_URL = f"/repos/{GITHUB_REPOSITORY}/actions/caches"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Python http.client"
    }

    conn = http.client.HTTPSConnection(BASE_URL)

    # Request to get the list of caches
    conn.request("GET", CACHE_URL, headers=headers)
    response = conn.getresponse()

    if response.status == 200:
        data = response.read()
        caches = json.loads(data).get('actions_caches', [])

        # If there are caches, delete them
        if caches:
            caches_to_delete = [cache['id'] for cache in caches]
        
            for cache_id in caches_to_delete:
                delete_url = f"{CACHE_URL}/{cache_id}"
                conn.request("DELETE", delete_url, headers=headers)
                delete_response = conn.getresponse()
                delete_response.read()  # Ensure response is processed
                
    conn.close()
