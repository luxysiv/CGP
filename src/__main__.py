import os
import argparse
from concurrent.futures import ThreadPoolExecutor
from src.domains import DomainConverter
from src.cloudflare import (
    get_lists, get_rules, create_list, update_list, create_rule, 
    update_rule, delete_list, delete_rule, get_list_items
)
from src import utils, info, error, silent_error, PREFIX

class CloudflareManager:
    def __init__(self, prefix, data_handler):
        self.list_name = f"[{prefix}]"
        self.rule_name = f"[{prefix}] Block Ads"
        self.data_handler = data_handler

    def update_resources(self):
        domains_to_block = DomainConverter().process_urls()
        if len(domains_to_block) > 300000:
            error("The domains list exceeds Cloudflare Gateway's free limit of 300,000 domains.")

        current_lists = get_lists(self.list_name)
        current_rules = get_rules(self.rule_name)

        # Initialize list_id_to_domains
        list_id_to_domains = {}

        # Populate the list_id_to_domains dictionary using data from data_handler or fetch online if not available
        with ThreadPoolExecutor() as executor:
            futures = {}
            for lst in current_lists:
                if lst["id"] in self.data_handler.data:
                    list_id_to_domains[lst["id"]] = set(self.data_handler.data[lst["id"]])
                else:
                    futures[executor.submit(get_list_items, lst["id"])] = lst["id"]

            for future in futures:
                lst_id = futures[future]
                items = future.result()
                list_id_to_domains[lst_id] = set(items)
                self.data_handler.data[lst_id] = items  # Save fetched data to the handler

        domain_to_list_id = {domain: lst_id for lst_id, domains in list_id_to_domains.items() for domain in domains}
        remaining_domains = set(domains_to_block) - set(domain_to_list_id.keys())

        list_name_to_id = {lst["name"]: lst["id"] for lst in current_lists}
        existing_indexes = sorted([int(name.split('-')[-1]) for name in list_name_to_id.keys()])
        all_indexes = set(range(1, max(existing_indexes + [(len(domains_to_block) + 999) // 1000]) + 1))
        missing_indexes = sorted(all_indexes - set(existing_indexes))

        new_list_ids = []
        for i in sorted(existing_indexes + missing_indexes):
            list_name = f"{self.list_name} - {i:03d}"
            if list_name in list_name_to_id:
                list_id = list_name_to_id[list_name]
                current_values = list_id_to_domains.get(list_id, set())
                remove_items = current_values - set(domains_to_block)
                chunk = current_values - remove_items

                new_items = []
                if len(chunk) < 1000:
                    needed_items = 1000 - len(chunk)
                    new_items = list(remaining_domains)[:needed_items]
                    chunk.update(new_items)
                    remaining_domains.difference_update(new_items)

                if remove_items or new_items:
                    update_list(list_id, remove_items, new_items)
                    self.data_handler.update_data(list_id, chunk)
                    info(f"Updated list: {list_name}")
                
                new_list_ids.append(list_id)
            else:
                if remaining_domains:
                    needed_items = min(1000, len(remaining_domains))
                    new_items = list(remaining_domains)[:needed_items]
                    remaining_domains.difference_update(new_items)
                    lst = create_list(list_name, new_items)
                    self.data_handler.update_data(lst["id"], set(new_items))
                    info(f"Created list: {lst['name']}")
                    new_list_ids.append(lst["id"])

        cgp_rule = next((rule for rule in current_rules if rule["name"] == self.rule_name), None)
        cgp_list_ids = utils.extract_list_ids(cgp_rule)

        if cgp_rule:
            if set(new_list_ids) != cgp_list_ids:
                update_rule(self.rule_name, cgp_rule["id"], new_list_ids)
                info(f"Updated rule {cgp_rule['name']}")
        else:
            rule = create_rule(self.rule_name, new_list_ids)
            info(f"Created rule {rule['name']}")

        # Delete excess lists that are no longer needed
        excess_lists = [lst for lst in current_lists if lst["id"] not in new_list_ids]
        for lst in excess_lists:
            delete_list(lst["id"])
            self.data_handler.data.pop(lst["id"], None)
            info(f"Deleted excess list: {lst['name']}")

        # Save the updated data after processing
        self.data_handler.save_data()

    def delete_resources(self):
        current_lists = get_lists(self.list_name)
        current_rules = get_rules(self.rule_name)
        current_lists.sort(key=utils.safe_sort_key)

        for rule in current_rules:
            delete_rule(rule["id"])
            info(f"Deleted rule: {rule['name']}")

        for lst in current_lists:
            delete_list(lst["id"])
            self.data_handler.data.pop(lst["id"], None)
            info(f"Deleted list: {lst['name']}")

        self.data_handler.save_data()

def main():
    parser = argparse.ArgumentParser(description="Cloudflare Manager Script")
    parser.add_argument("action", choices=["run", "leave"], help="Choose action: run or leave")
    args = parser.parse_args()

    data_handler = utils.DataHandler()
    cloudflare_manager = CloudflareManager(PREFIX, data_handler)

    if args.action == "run":
        cloudflare_manager.update_resources()

        utils.configure_git_user()
        utils.add_and_commit("cloudflare_data.txt", "Update Cloudflare data")
        utils.push_changes("main")

    elif args.action == "leave":
        cloudflare_manager.delete_resources()

        utils.configure_git_user()
        utils.add_and_commit("cloudflare_data.txt", "Clear Cloudflare data")
        utils.push_changes("main")
        
    else:
        error("Invalid action. Please choose either 'run' or 'leave'.")

if __name__ == "__main__":
    main()
