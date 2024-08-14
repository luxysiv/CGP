import os
import re
import json
import subprocess
from src import ids_pattern, silent_error, CACHE_FILE

class DataHandler:
    def __init__(self):
        self.data = self.load_data()

    def load_data(self):
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        return {}

    def save_data(self):
        with open(CACHE_FILE, 'w') as f:
            json.dump(self.data, f)

    def update_data(self, list_id, domains):
        self.data[list_id] = list(domains)
        self.save_data()

def safe_sort_key(list_item):
    match = re.search(r'\d+', list_item["name"])
    return int(match.group()) if match else float('inf')

def extract_list_ids(rule):
    if not rule or not rule.get('traffic'):
        return set()
    return set(ids_pattern.findall(rule['traffic']))
