import argparse
from src.domains import DomainConverter
from src import utils, info, error, PREFIX
from src.cloudflare import (
    create_list, update_list, create_rule, 
    update_rule, delete_list, delete_rule
)

class CloudflareManager:
    def __init__(self, prefix: str):
        """
        Initialize the CloudflareManager class with a given prefix.
        
        Args:
            prefix (str): Prefix used for naming lists and rules.
        """
        self.list_name = f"[{prefix}]"
        self.rule_name = f"[{prefix}] Block Ads"
        self.cache = utils.load_cache()

    def update_resources(self):
        """
        Updates the Cloudflare lists and rules with new domains to block.
        Manages creation, updating, and deletion of lists and rules as necessary.
        """
        # Retrieve domains to block from the DomainConverter
        domains_to_block = DomainConverter().process_urls()
        
        # Cloudflare Gateway free limit check
        if len(domains_to_block) > 300000:
            error("The domains list exceeds Cloudflare Gateway's free limit of 300,000 domains.")
        
        # Retrieve current lists and rules from cache or Cloudflare
        current_lists = utils.get_current_lists(self.cache, self.list_name)
        current_rules = utils.get_current_rules(self.cache, self.rule_name)

        # Map list IDs to their current domains
        list_id_to_domains = {}
        for lst in current_lists:
            items = utils.get_list_items_cached(self.cache, lst["id"])
            list_id_to_domains[lst["id"]] = set(items)

        # Map current domains to their corresponding list IDs
        domain_to_list_id = {domain: lst_id for lst_id, domains in list_id_to_domains.items() for domain in domains}

        # Calculate the remaining domains that are not already in the lists
        remaining_domains = set(domains_to_block) - set(domain_to_list_id.keys())

        # Calculate list indexes
        list_name_to_id = {lst["name"]: lst["id"] for lst in current_lists}
        all_indexes = set(range(1, (len(domains_to_block) + 999) // 1000 + 1))

        # Process and update the lists
        new_list_ids = []
        for i in all_indexes:
            list_name = f"{self.list_name} - {i:03d}"
            
            if list_name in list_name_to_id:
                list_id = list_name_to_id[list_name]
                current_values = list_id_to_domains[list_id]
                remove_items = current_values - set(domains_to_block)
                chunk = current_values - remove_items

                new_items = []
                if len(chunk) < 1000:
                    needed_items = 1000 - len(chunk)
                    new_items = list(remaining_domains)[:needed_items]
                    chunk.update(new_items)
                    remaining_domains.difference_update(new_items)

                # Update the list with new and removed items
                if remove_items or new_items:
                    update_list(list_id, remove_items, new_items)
                    info(f"Updated list: {list_name}")
                    self.cache["mapping"][list_id] = list(chunk)
                    
                new_list_ids.append(list_id)
            else:
                # Create new lists for remaining domains
                if remaining_domains:
                    needed_items = min(1000, len(remaining_domains))
                    new_items = list(remaining_domains)[:needed_items]
                    remaining_domains.difference_update(new_items)
                    lst = create_list(list_name, new_items)
                    info(f"Created list: {lst['name']}")
                    self.cache["lists"].append(lst)
                    self.cache["mapping"][lst["id"]] = new_items
                    new_list_ids.append(lst["id"])

        # Update the rule with the new list IDs
        cgp_rule = next((rule for rule in current_rules if rule["name"] == self.rule_name), None)
        cgp_list_ids = utils.extract_list_ids(cgp_rule)

        if cgp_rule:
            if set(new_list_ids) != cgp_list_ids:
                updated_rule = update_rule(self.rule_name, cgp_rule["id"], new_list_ids)
                info(f"Updated rule {updated_rule['name']}")
                self.cache["rules"] = [updated_rule]
        else:
            rule = create_rule(self.rule_name, new_list_ids)
            info(f"Created rule {rule['name']}")
            self.cache["rules"].append(rule)

        # Save the updated cache
        utils.save_cache(self.cache)

    def delete_resources(self):
        """
        Deletes all Cloudflare lists and rules associated with the current prefix.
        """
        current_lists = utils.get_current_lists(self.cache, self.list_name)
        current_rules = utils.get_current_rules(self.cache, self.rule_name)
        current_lists.sort(key=utils.safe_sort_key)

        # Delete all rules with the rule name
        for rule in current_rules:
            delete_rule(rule["id"])
            info(f"Deleted rule: {rule['name']}")

        # Delete all lists associated with the prefix
        for lst in current_lists:
            delete_list(lst["id"])
            info(f"Deleted list: {lst['name']}")

            # Remove deleted lists from cache
            self.cache["lists"] = [item for item in self.cache["lists"] if item["id"] != lst["id"]]
            if lst["id"] in self.cache["mapping"]:
                del self.cache["mapping"][lst["id"]]

            # Save the updated cache
            utils.save_cache(self.cache)

        # Clear rules from cache after deletion
        self.cache["rules"] = []
        utils.save_cache(self.cache)


def main():
    """
    Main entry point for the Cloudflare Manager script.
    Handles argument parsing and initiates actions.
    """
    parser = argparse.ArgumentParser(description="Cloudflare Manager Script")
    parser.add_argument("action", choices=["run", "leave"], help="Choose action: run or leave")
    args = parser.parse_args()    
    cloudflare_manager = CloudflareManager(PREFIX)
    
    # Execute the corresponding action
    if args.action == "run":
        cloudflare_manager.update_resources()
        utils.delete_cache()
    elif args.action == "leave":
        cloudflare_manager.delete_resources()
    else:
        error("Invalid action. Please choose either 'run' or 'leave'.")

if __name__ == "__main__":
    main()
