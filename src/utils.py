import os
import re
import json
import subprocess
import http.client
from src import ids_pattern, info, silent_error, CACHE_FILE


class DataHandler:
    def __init__(self, cache_file=CACHE_FILE):
        self.cache_file = cache_file
        self.data = self.load_data()

    def load_data(self):
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        return {}

    def save_data(self):
        with open(self.cache_file, 'w') as f:
            json.dump(self.data, f, indent=2)

    def get_current_lists(self):
        return self.data.get('current_lists', None)

    def get_current_rules(self):
        return self.data.get('current_rules', None)

    def update_cache(self, current_lists, current_rules):
        self.data['current_lists'] = current_lists
        self.data['current_rules'] = current_rules
        self.save_data()

    def update_data(self, list_id, domains):
        self.data[list_id] = list(domains)
        self.save_data()

    def get_cached_domain_mapping(self):
        return {list_id: set(domains) for list_id, domains in self.data.items() if list_id not in ['current_lists', 'current_rules']}

def safe_sort_key(list_item):
    match = re.search(r'\d+', list_item["name"])
    return int(match.group()) if match else float('inf')

def extract_list_ids(rule):
    if not rule or not rule.get('traffic'):
        return set()
    return set(ids_pattern.findall(rule['traffic']))

def delete_cache():
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
    GITHUB_REPOSITORY = os.getenv('GITHUB_REPOSITORY') 
    
    BASE_URL = f"api.github.com"
    CACHE_URL = f"/repos/{GITHUB_REPOSITORY}/actions/caches"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Python http.client"
    }

    conn = http.client.HTTPSConnection(BASE_URL)

    conn.request("GET", CACHE_URL, headers=headers)
    response = conn.getresponse()

    if response.status == 200:
        data = response.read()
        caches = json.loads(data).get('actions_caches', [])

        if len(caches) > 0:
            caches_to_delete = [cache['id'] for cache in caches]
        
            for cache_id in caches_to_delete:
                delete_url = f"{CACHE_URL}/{cache_id}"
                conn.request("DELETE", delete_url, headers=headers)
                delete_response = conn.getresponse()
                if delete_response.status == 204:
                    info(f"Deleted cache ID: {cache_id}")
                else:
                    silent_error(f"Failed to delete cache ID: {cache_id}, status code: {delete_response.status}")
                delete_response.read()
        else:
            silent_error("No old caches to delete, only one or zero caches found.")
    else:
        silent_error(f"Failed to fetch caches, status code: {response.status}")

    conn.close()
