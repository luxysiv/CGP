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

def run_command(command):
    result = subprocess.run(command, shell=True, check=True, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result

def configure_git_user():
    run_command(f'git config --global user.email "github-actions[bot]@users.noreply.github.com"')
    run_command(f'git config --global user.name "GitHub Actions"')

def add_and_commit(file_name, commit_message):
    # Add file to staging
    run_command(f'git add {file_name}')
    
    # Check if there are any changes to commit
    status = subprocess.run('git status --porcelain', shell=True, text=True, capture_output=True)
    if status.stdout.strip():  # If there are changes
        run_command(f'git commit -m "{commit_message}"')
    else:
        silent_error("No changes.")

def push_changes(branch):
    github_token = os.getenv("GITHUB_TOKEN")
    if run_command(f'git push https://x-access-token:{github_token}@github.com/{os.getenv("GITHUB_REPOSITORY")}.git {branch}') is None:
        silent_error("Failed to push changes.")
