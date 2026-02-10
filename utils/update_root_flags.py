#!/usr/bin/env python3
"""
Utility script to update root flags in htb_data.json
Can be run manually or imported.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json

DB_FILE = "htb_data.json"


def load_db():
    data = {"users": {}}
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            print("JSON Corrupt. Starting fresh (Old file backed up).")
            os.rename(DB_FILE, f"{DB_FILE}.bak")
    return data


def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)


def get_user_activity(user_id, htb_api_url, htb_api_token):
    import requests

    url = f"{htb_api_url}/api/v4/user/profile/activity/{user_id}"
    headers = {
        "Authorization": f"Bearer {htb_api_token}",
        "User-Agent": "DiscordBot/1.0",
        "Accept": "application/json",
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("profile", {}).get("activity", [])
        return None
    except Exception as e:
        print(f"Connection Error: {e}")
        return None


def check_root_flags_manual(htb_api_url, htb_api_token, db=None):
    """Check, update, and print users with root flags."""
    if db is None:
        db = load_db()

    if not db["users"]:
        print("No users are being tracked yet!")
        return db

    print("\nAnalyzing root flags and updating database...\n")

    root_flag_data = []
    updated_count = 0

    for htb_id, user_data in db["users"].items():
        user_name = user_data.get("name", "Unknown")
        solved_ids = set(user_data.get("solved_ids", []))
        user_flag_ids = user_data.get("user_flag_ids", [])

        if "root_flag_ids" not in user_data:
            user_data["root_flag_ids"] = []

        user_flag_machine_ids = {
            int(uid.split("_")[0])
            for uid in user_flag_ids
            if "_user" in uid and uid.split("_")[0].isdigit()
        }

        activities = get_user_activity(htb_id, htb_api_url, htb_api_token)
        if not activities:
            continue

        root_flags = {}
        challenge_ids = set()

        for activity in activities:
            act_id = activity.get("id")
            act_type = activity.get("object_type")
            act_flag_type = activity.get("type")
            act_name = activity.get("name")

            if act_type == "machine" and act_flag_type == "root":
                if act_id in solved_ids and act_id not in user_flag_machine_ids:
                    root_flags[act_id] = act_name

            elif act_type == "challenge":
                if act_id in solved_ids:
                    challenge_ids.add(act_id)

        needs_update = False
        update_messages = []

        if root_flags:
            new_root_flag_ids = sorted(root_flags.keys())
            old_root_flag_ids = sorted(user_data.get("root_flag_ids", []))
            root_flag_count = len(new_root_flag_ids)

            if new_root_flag_ids != old_root_flag_ids:
                user_data["root_flag_ids"] = new_root_flag_ids
                needs_update = True

            current_machines = user_data.get("machines", 0)
            if current_machines != root_flag_count:
                user_data["machines"] = root_flag_count
                needs_update = True
                if new_root_flag_ids == old_root_flag_ids:
                    update_messages.append(
                        f"machines count = {root_flag_count} (was {current_machines})"
                    )

            if new_root_flag_ids != old_root_flag_ids:
                update_messages.append(
                    f"{root_flag_count} root flag(s), machines count = {root_flag_count}"
                )

            root_flag_data.append((user_name, htb_id, root_flags))
        else:
            if user_data.get("root_flag_ids"):
                user_data["root_flag_ids"] = []
                needs_update = True
            if user_data.get("machines", 0) > 0:
                user_data["machines"] = 0
                needs_update = True

        challenge_count = len(challenge_ids)
        current_challenges = user_data.get("challenges", 0)
        if current_challenges != challenge_count:
            user_data["challenges"] = challenge_count
            needs_update = True
            update_messages.append(
                f"challenges count = {challenge_count} (was {current_challenges})"
            )

        if needs_update:
            updated_count += 1
            if update_messages:
                print(f"   Updated {user_name}: {', '.join(update_messages)}")

    if updated_count > 0:
        save_db(db)
        print(f"\nDatabase updated! ({updated_count} user(s) modified)\n")

    if not root_flag_data:
        print("No root flags found. Everyone needs to step up their game!")
        return db

    root_flag_data.sort(key=lambda x: len(x[2]), reverse=True)

    print("=" * 60)
    print("ROOT FLAG OWNERS")
    print("=" * 60)

    for user_name, htb_id, root_flags in root_flag_data:
        flag_count = len(root_flags)
        print(f"\n{user_name} ({flag_count} root flag{'s' if flag_count > 1 else ''})")
        print(f"   HTB ID: {htb_id}")
        for fid, name in sorted(root_flags.items()):
            print(f"   {name} (Machine ID: {fid})")

    print("\n" + "=" * 60)
    print(f"Total users with root flags: {len(root_flag_data)}")
    print("=" * 60 + "\n")

    return db


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    HTB_API_URL = os.getenv("HTB_API_URL")
    HTB_API_TOKEN = os.getenv("HTB_API_TOKEN")

    if not HTB_API_URL or not HTB_API_TOKEN:
        print("Missing HTB_API_URL or HTB_API_TOKEN in .env")
        exit(1)

    print("Starting root flags update...")
    check_root_flags_manual(HTB_API_URL, HTB_API_TOKEN)
    print("Update complete!")
