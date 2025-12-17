#!/usr/bin/env python3
import csv
import json
import os
import re
from datetime import datetime

from flask import Flask, render_template, request, jsonify, send_from_directory

app = Flask(__name__, static_folder="static", template_folder="static/templates")

# Load config and create config file with defaults if it doesn't exist
CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    "title": "Mains Leaderboard",
    "port": 8080,
    "shiny_odds": 8192,
    "volume": 0.5,
    "game": "crystal",
}

config = {}
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content:  # Only try to parse if file is not empty
                config = json.loads(content)
            else:
                print(f"Warning: {CONFIG_FILE} is empty. Using default configuration.")
                config = {}
    except json.JSONDecodeError as e:
        print(
            f"Warning: {CONFIG_FILE} contains invalid JSON: {e}. Using default configuration."
        )
        config = {}
    except Exception as e:
        print(
            f"Warning: Error reading {CONFIG_FILE}: {e}. Using default configuration."
        )
        config = {}

# Check if any keys are missing and add defaults
config_updated = False
for key, default_value in DEFAULT_CONFIG.items():
    if key not in config:
        config[key] = default_value
        config_updated = True

# Write back to file if config was updated
if config_updated:
    with open("config.json", "w") as config_file:
        json.dump(config, config_file, indent=4)  # Added indent=4 for pretty formatting

if config.get("game") == "xy":
    from bstgen6 import pokemon_bst
else:
    from bst import pokemon_bst

# Path to the CSV file
CSV_FILE = "pokemon_usage.csv"


def read_csv():
    """Read the CSV_FILE and return a list of dictionaries for each row."""
    rows = []
    with open(CSV_FILE, mode="r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Ensure Notes field exists for backward compatibility
            if "Notes" not in row:
                row["Notes"] = ""
            rows.append(row)
    return rows


def write_csv(rows):
    """Write the given list of dictionaries to CSV_FILE."""
    with open(CSV_FILE, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Pokemon", "Location", "Date", "Notes"])
        writer.writeheader()
        writer.writerows(rows)


# Serve index.html from the /static directory
@app.route("/")
def index():
    return render_template("index.html.j2", title=config["title"])


# Endpoint to add a new entry
@app.route("/add_entry", methods=["POST"])
def add_entry():
    pokemon = request.form["pokemon"].strip()  # Remove leading/trailing whitespace
    location = request.form["location"].strip()  # Remove leading/trailing whitespace
    date_str = request.form["date"]
    notes = request.form.get("notes", "").strip()  # Also trim notes

    # Convert 'YYYY-MM-DD' to 'M/D/YYYY' (no leading zeros)
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    date_formatted = dt.strftime("%m/%d/%Y")
    # Remove any leading zeros from month/day
    date_formatted = re.sub(r"\b0(\d)", r"\1", date_formatted)

    # Read current rows
    rows = read_csv()

    # Append new entry
    rows.append(
        {
            "Pokemon": pokemon,
            "Location": location,
            "Date": date_formatted,
            "Notes": notes,
        }
    )

    # Write back to CSV
    write_csv(rows)

    return jsonify({"success": True})


def calculate_time_since(from_date, to_date):
    """
    Calculate the time difference between two dates and return a formatted string
    in the format: 2 yrs, 4 mos, 8 days
    """
    if not from_date or not to_date:
        return "Never"

    # Ensure from_date is before to_date
    if from_date > to_date:
        from_date, to_date = to_date, from_date

    # Calculate total days first as a fallback
    total_days = (to_date - from_date).days

    if total_days == 0:
        return "0 days"

    # Calculate years, months, and days properly
    years = to_date.year - from_date.year
    months = to_date.month - from_date.month
    days = to_date.day - from_date.day

    # Adjust for negative days
    if days < 0:
        months -= 1
        # Get the number of days in the previous month
        if to_date.month == 1:
            prev_month_year = to_date.year - 1
            prev_month = 12
        else:
            prev_month_year = to_date.year
            prev_month = to_date.month - 1

        # Calculate days in previous month
        try:
            from calendar import monthrange

            days_in_prev_month = monthrange(prev_month_year, prev_month)[1]
            days += days_in_prev_month
        except:
            # Fallback if calendar import fails
            days += 30

    # Adjust for negative months
    if months < 0:
        years -= 1
        months += 12

    # Format the result with spaces
    parts = []
    if years > 0:
        parts.append(f"{years} yr{'s' if years != 1 else ''}")
    if months > 0:
        parts.append(f"{months} mo{'s' if months != 1 else ''}")
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")

    if not parts:
        return "0 days"

    return ", ".join(parts)


# Endpoint to fetch the leaderboard data
@app.route("/leaderboard")
def leaderboard():
    try:
        rows = read_csv()
        if not rows:
            return jsonify([])  # Return an empty list if no data

        # Attach index to each row for stable sorting
        for idx, row in enumerate(rows):
            try:
                row["_date_dt"] = datetime.strptime(row["Date"], "%m/%d/%Y")
            except ValueError:
                row["_date_dt"] = datetime.min
            row["_csv_idx"] = idx

        # Sort by date descending, then by CSV index descending (later rows first)
        sorted_rows = sorted(
            rows, key=lambda x: (x["_date_dt"], x["_csv_idx"]), reverse=True
        )

        # Get today's date and the most recent entry date for calculations
        today = datetime.now()
        most_recent_entry_date = sorted_rows[0]["_date_dt"] if sorted_rows else today
        most_recent_entry_idx = sorted_rows[0]["_csv_idx"] if sorted_rows else 0

        # Count occurrences of each Pokémon and track the last time ran
        # We'll store data as { "Pikachu": {"count": x, "last_date": y, "last_idx": z}, ... }
        data = {}
        for row in rows:
            pokemon = row["Pokemon"]
            # Parse date string 'M/D/YYYY'
            try:
                run_date = datetime.strptime(row["Date"], "%m/%d/%Y")
            except ValueError:
                # Fallback if the date format is unexpected
                # You could choose to ignore or handle differently
                run_date = None

            if pokemon not in data:
                data[pokemon] = {
                    "count": 0,
                    "last_date": run_date,  # store a datetime for comparison
                    "last_idx": row["_csv_idx"],
                }
            data[pokemon]["count"] += 1

            # Update last_date to the max date encountered
            if run_date and data[pokemon]["last_date"]:
                if run_date > data[pokemon]["last_date"] or (
                    run_date == data[pokemon]["last_date"]
                    and row["_csv_idx"] > data[pokemon]["last_idx"]
                ):
                    data[pokemon]["last_date"] = run_date
                    data[pokemon]["last_idx"] = row["_csv_idx"]
            elif run_date and not data[pokemon]["last_date"]:
                data[pokemon]["last_date"] = run_date
                data[pokemon]["last_idx"] = row["_csv_idx"]

        # Convert the dictionary to a list of dicts for sorting
        leaderboard_list = []
        for pokemon, info in data.items():
            last_date_dt = info["last_date"]
            last_idx = info["last_idx"]

            # If we have a datetime, convert back to string
            if last_date_dt:
                date_str = last_date_dt.strftime("%m/%d/%Y")
                # Remove leading zeros
                date_str = re.sub(r"\b0(\d)", r"\1", date_str)
            else:
                date_str = ""  # or some fallback if no date

            # Get BST from pokemon_bst dictionary with case-insensitive lookup
            bst = get_pokemon_bst(pokemon)

            # Calculate runs and time since last ran for this Pokemon
            runs_since_last = None
            time_since_last = None

            if last_date_dt:
                # Time since last ran = time from the last time this Pokemon was run to today
                try:
                    time_since_last = calculate_time_since(last_date_dt, today)
                except Exception as e:
                    print(f"Error calculating time since for {pokemon}: {e}")
                    time_since_last = "Error"

                # Runs since last ran = entries from the most recent entry back to this Pokemon's last run
                if (
                    last_date_dt == most_recent_entry_date
                    and last_idx == most_recent_entry_idx
                ):
                    # This Pokemon was the most recent entry, so 0 runs since
                    runs_since_last = 0
                else:
                    # Count entries that occurred after this Pokemon's last run
                    runs_count = 0
                    for row in sorted_rows:
                        # Entry must be after this Pokemon's last occurrence
                        if (row["_date_dt"] > last_date_dt) or (
                            row["_date_dt"] == last_date_dt
                            and row["_csv_idx"] > last_idx
                        ):
                            runs_count += 1
                    runs_since_last = runs_count

            leaderboard_list.append(
                {
                    "Pokemon": pokemon,
                    "Count": info["count"],
                    "Last Time Ran": date_str,
                    "BST": bst,
                    "Time Since Last Ran": (
                        time_since_last if time_since_last is not None else "Never"
                    ),
                    "Runs Since Last Ran": (
                        str(runs_since_last) if runs_since_last is not None else "Never"
                    ),
                    # keep a separate field for sorting by datetime
                    "_last_date_dt": last_date_dt if last_date_dt else datetime.min,
                }
            )

        # Sort by Count descending, then by Last Time Ran ascending
        leaderboard_list.sort(key=lambda x: (-x["Count"], x["_last_date_dt"]))

        # Remove the helper key
        for item in leaderboard_list:
            item.pop("_last_date_dt", None)

        return jsonify(leaderboard_list)

    except Exception as e:
        print(f"Error in leaderboard endpoint: {e}")
        return jsonify({"error": str(e)}), 500


# Endpoint to fetch the last 10 Pokémon ran
@app.route("/last10")
def last10():
    rows = read_csv()
    if not rows:
        return jsonify([])

    # Attach index to each row for stable sorting
    for idx, row in enumerate(rows):
        try:
            row["_date_dt"] = datetime.strptime(row["Date"], "%m/%d/%Y")
        except ValueError:
            row["_date_dt"] = datetime.min
        row["_csv_idx"] = idx

    # Sort by date descending, then by CSV index descending (later rows first)
    rows.sort(key=lambda x: (x["_date_dt"], x["_csv_idx"]), reverse=True)

    # Take the first 10
    last_10 = rows[:10]

    # For each entry, find the previous occurrence of the same Pokemon
    for i, entry in enumerate(last_10):
        entry_date = entry["_date_dt"]
        entry_idx = entry["_csv_idx"]
        pokemon = entry["Pokemon"]

        prev_time = None
        prev_runs = None

        # Search through ALL sorted rows (not just last 10) to find previous occurrence
        for j in range(len(rows)):
            # Skip entries that are not before the current entry
            if rows[j]["_date_dt"] > entry_date or (
                rows[j]["_date_dt"] == entry_date and rows[j]["_csv_idx"] >= entry_idx
            ):
                continue

            if rows[j]["Pokemon"] == pokemon:
                prev_date = rows[j]["_date_dt"]
                prev_time = calculate_time_since(prev_date, entry_date)

                # Count runs since last occurrence
                # This counts entries that occurred after the previous occurrence but before current entry
                runs_count = 0
                for k in range(len(rows)):
                    row_date = rows[k]["_date_dt"]
                    row_idx = rows[k]["_csv_idx"]

                    # Entry must be after the previous occurrence but before current entry
                    if (
                        (row_date > prev_date)
                        or (row_date == prev_date and row_idx > rows[j]["_csv_idx"])
                    ) and (
                        (row_date < entry_date)
                        or (row_date == entry_date and row_idx < entry_idx)
                    ):
                        runs_count += 1

                # Add this line to include the current run
                runs_count += 1

                prev_runs = runs_count
                break

        if prev_time is not None:
            entry["Time Since Last Ran"] = prev_time
        else:
            entry["Time Since Last Ran"] = "Never"

        if prev_runs is not None:
            entry["Runs Since Last Ran"] = str(prev_runs)
        else:
            entry["Runs Since Last Ran"] = "Never"

    # Clean up for JSON response
    for row in last_10:
        date_str = row["_date_dt"].strftime("%m/%d/%Y")
        date_str = re.sub(r"\b0(\d)", r"\1", date_str)
        row["Date"] = date_str
        row.pop("_date_dt", None)
        row.pop("_csv_idx", None)

    return jsonify(last_10)


# Endpoint to fetch all valid Pokemon and their BST
@app.route("/bst")
def pokemon_options():
    rows = []

    for pokemon_val, bst_val in pokemon_bst.items():
        curr_row = {}
        curr_row["Pokemon"] = pokemon_val
        curr_row["BST"] = bst_val
        rows.append(curr_row)

    sorted_by_name = sorted(rows, key=lambda x: x["Pokemon"])

    return jsonify(sorted_by_name)


# Endpoint to fetch location percentages
@app.route("/location_percentages")
def location_percentages():
    rows = read_csv()
    total_entries = len(rows)
    if total_entries == 0:
        return jsonify([])

    # Count locations and track last Pokemon and date for each
    location_counts = {}
    location_last_info = {}
    for row in rows:
        loc = row["Location"]
        location_counts[loc] = location_counts.get(loc, 0) + 1
        # Track the last entry for this location (rows are in order, so we keep updating)
        location_last_info[loc] = {"pokemon": row["Pokemon"], "date": row["Date"]}

    # Convert to list of {Location, Percentage, LastPokemon, LastDate}, sorted by count desc
    # (to mimic pandas value_counts behavior)
    result = []
    for loc, count in location_counts.items():
        percentage = (count / total_entries) * 100
        result.append(
            {
                "Location": loc,
                "Percentage": percentage,
                "LastPokemon": location_last_info[loc]["pokemon"],
                "LastDate": location_last_info[loc]["date"],
            }
        )

    # Sort by percentage descending
    result.sort(key=lambda x: x["Percentage"], reverse=True)

    return jsonify(result)


# Endpoint to fetch the total number of Pokémon entries
@app.route("/total_pokemon")
def total_pokemon():
    rows = read_csv()
    return jsonify({"total_pokemon": len(rows)})


# Endpoint to fetch the number of unique Pokémon entries
@app.route("/unique_pokemon")
def unique_pokemon():
    rows = read_csv()
    unique_list = []
    for row in rows:
        curr_pokemon = row["Pokemon"]
        if curr_pokemon not in unique_list:
            unique_list.append(curr_pokemon)
    return jsonify({"unique_pokemon": len(unique_list)})


@app.route("/config")
def get_config():
    # Determine game and shiny folder existence
    game = config.get("game", "crystal")
    shiny_gifs_folder = os.path.join(app.static_folder, "shiny_gifs", game)
    shiny_gifs_exists = os.path.isdir(shiny_gifs_folder)
    return jsonify(
        {
            "title": config.get("title", "Mains Leaderboard"),
            "port": config.get("port", 8080),
            "shiny_odds": config.get("shiny_odds", 8192),
            "volume": config.get("volume", 0.5),
            "game": game,
            "shiny_gifs_exists": shiny_gifs_exists,
        }
    )


def get_media_path(pokemon_name, shiny=False):
    """Return the path to the media file for the given Pokémon and game."""
    game_folder = config.get("game", "crystal")
    extensions = [".gif", ".png", ".jpg", ".webp"]  # Add supported extensions
    filename_base = sanitize_filename(pokemon_name)
    if shiny:
        shiny_folder = os.path.join(app.static_folder, "shiny_gifs", game_folder)
        for ext in extensions:
            path = os.path.join(shiny_folder, filename_base + ext)
            if os.path.exists(path):
                return shiny_folder, filename_base + ext
    normal_folder = os.path.join(app.static_folder, "gifs", game_folder)
    for ext in extensions:
        path = os.path.join(normal_folder, filename_base + ext)
        if os.path.exists(path):
            return normal_folder, filename_base + ext
    return None, None


@app.route("/last_pokemon")
def last_pokemon():
    rows = read_csv()
    if not rows:
        return "", 404

    # Attach index for tie-breaking
    for idx, row in enumerate(rows):
        try:
            row["_date_dt"] = datetime.strptime(row["Date"], "%m/%d/%Y")
        except ValueError:
            row["_date_dt"] = datetime.min
        row["_csv_idx"] = idx

    # Sort by date descending, then by CSV index descending (later rows first)
    rows.sort(key=lambda x: (x["_date_dt"], x["_csv_idx"]), reverse=True)
    last = rows[0]
    pokemon_name = last["Pokemon"]

    # Check for shiny (example: you may want to pass this from frontend)
    shiny = False
    folder, filename = get_media_path(pokemon_name, shiny=shiny)
    if not folder or not filename:
        return "", 404

    return send_from_directory(folder, filename)


@app.route("/pokemon_media/<pokemon_name>")
def pokemon_media(pokemon_name):
    shiny = request.args.get("shiny", "0") == "1"
    folder, filename = get_media_path(pokemon_name, shiny=shiny)
    if not folder or not filename:
        return "", 404
    return send_from_directory(folder, filename)


@app.route("/play_streak")
def play_streak():
    rows = read_csv()
    if not rows:
        return jsonify({"play_streak": 0})

    # Get all unique dates from the CSV
    date_set = set()
    for row in rows:
        try:
            dt = datetime.strptime(row["Date"], "%m/%d/%Y")
            date_set.add(dt.date())
        except ValueError:
            continue

    if not date_set:
        return jsonify({"play_streak": 0})

    today = datetime.now().date()
    sorted_dates = sorted(date_set, reverse=True)

    # If the most recent entry is not today or yesterday, streak is 0
    if (today not in date_set) and ((today - sorted_dates[0]).days > 1):
        return jsonify({"play_streak": 0})

    # Start from the most recent date, count consecutive days
    streak = 1
    for i in range(1, len(sorted_dates)):
        if (sorted_dates[i - 1] - sorted_dates[i]).days == 1:
            streak += 1
        else:
            break

    # If today is not in the streak, don't count today yet
    if today not in date_set:
        pass  # streak remains as is
    return jsonify({"play_streak": streak})


@app.route("/current_streak")
def current_streak():
    rows = read_csv()
    if not rows:
        return jsonify({"current_streak": 0})

    # Get all unique dates from the CSV
    date_set = set()
    for row in rows:
        try:
            dt = datetime.strptime(row["Date"], "%m/%d/%Y")
            date_set.add(dt.date())
        except ValueError:
            continue

    if not date_set:
        return jsonify({"current_streak": 0})

    today = datetime.now().date()
    sorted_dates = sorted(date_set, reverse=True)

    # If the most recent entry is not today or yesterday, streak is 0
    if (today not in date_set) and ((today - sorted_dates[0]).days > 1):
        return jsonify({"current_streak": 0})

    # Start from the most recent date, count consecutive days
    streak = 1
    for i in range(1, len(sorted_dates)):
        if (sorted_dates[i - 1] - sorted_dates[i]).days == 1:
            streak += 1
        else:
            break

    # If today is not in the streak, don't count today yet
    if today not in date_set:
        pass  # streak remains as is
    return jsonify({"current_streak": streak})


@app.route("/longest_streak")
def longest_streak():
    rows = read_csv()
    if not rows:
        return jsonify({"longest_streak": 0, "start_date": None, "end_date": None})

    # Get all unique dates from the CSV
    date_set = set()
    for row in rows:
        try:
            dt = datetime.strptime(row["Date"], "%m/%d/%Y")
            date_set.add(dt.date())
        except ValueError:
            continue

    if not date_set:
        return jsonify({"longest_streak": 0, "start_date": None, "end_date": None})

    sorted_dates = sorted(date_set)
    longest = 1
    current = 1
    streak_start = sorted_dates[0]
    streak_end = sorted_dates[0]
    longest_start = sorted_dates[0]
    longest_end = sorted_dates[0]

    for i in range(1, len(sorted_dates)):
        if (sorted_dates[i] - sorted_dates[i - 1]).days == 1:
            current += 1
            streak_end = sorted_dates[i]
            if current > longest:
                longest = current
                longest_start = streak_start
                longest_end = streak_end
        else:
            current = 1
            streak_start = sorted_dates[i]
            streak_end = sorted_dates[i]

    # Format dates as M/D/YYYY
    start_str = longest_start.strftime("%m/%d/%Y")
    start_str = re.sub(r"\b0(\d)", r"\1", start_str)
    end_str = longest_end.strftime("%m/%d/%Y")
    end_str = re.sub(r"\b0(\d)", r"\1", end_str)

    return jsonify(
        {"longest_streak": longest, "start_date": start_str, "end_date": end_str}
    )


@app.route("/max_runs_per_day")
def max_runs_per_day():
    rows = read_csv()
    if not rows:
        return jsonify({"max_runs": 0, "dates": []})

    date_counts = {}
    for row in rows:
        try:
            dt = datetime.strptime(row["Date"], "%m/%d/%Y")
            date_str = dt.strftime("%m/%d/%Y")
            # Remove leading zeros from month and day
            date_str = re.sub(r"\b0(\d)", r"\1", date_str)
        except ValueError:
            continue
        date_counts[date_str] = date_counts.get(date_str, 0) + 1

    if not date_counts:
        return jsonify({"max_runs": 0, "dates": []})

    max_runs = max(date_counts.values())
    max_dates = [date for date, count in date_counts.items() if count == max_runs]
    return jsonify({"max_runs": max_runs, "dates": max_dates})


@app.route("/average_bst")
def average_bst():
    rows = read_csv()
    if not rows:
        return jsonify({"average_bst": 0})

    total_bst = 0
    total_entries = len(rows)

    for row in rows:
        pokemon = row["Pokemon"]
        bst = get_pokemon_bst(pokemon)
        total_bst += bst

    average = total_bst / total_entries if total_entries > 0 else 0
    return jsonify({"average_bst": int(average)})


@app.route("/lowest_bst")
def lowest_bst():
    rows = read_csv()
    if not rows:
        return jsonify({"lowest_bst": 0})

    lowest_bst = 999

    for row in rows:
        pokemon = row["Pokemon"]
        bst = get_pokemon_bst(pokemon)
        if bst < lowest_bst:
            lowest_bst = bst

    return jsonify({"lowest_bst": lowest_bst})


def sanitize_filename(name):
    # Convert to lowercase and replace spaces with underscores
    return name.lower().replace(" ", "_")


def get_pokemon_bst(pokemon_name):
    """
    Get BST for a Pokemon with case-insensitive lookup.
    Returns 0 if Pokemon is not found.
    """
    # First try exact match
    if pokemon_name in pokemon_bst:
        return pokemon_bst[pokemon_name]

    # If no exact match, try case-insensitive lookup
    pokemon_lower = pokemon_name.lower()
    for bst_pokemon, bst_value in pokemon_bst.items():
        if bst_pokemon.lower() == pokemon_lower:
            return bst_value

    # If still no match, return 0
    return 0


@app.route("/pokemon_entries/<pokemon_name>")
def pokemon_entries(pokemon_name):
    """Get all entries for a specific Pokemon."""
    rows = read_csv()
    if not rows:
        return jsonify([])

    # Filter entries for the specific Pokemon
    pokemon_entries = []
    location_counts = {}

    for idx, row in enumerate(rows):
        if row["Pokemon"].lower() == pokemon_name.lower():
            try:
                row_date = datetime.strptime(row["Date"], "%m/%d/%Y")
            except ValueError:
                row_date = datetime.min

            pokemon_entries.append(
                {
                    "Pokemon": row["Pokemon"],
                    "Location": row["Location"],
                    "Date": row["Date"],
                    "Notes": row.get("Notes", ""),
                    "_date_dt": row_date,
                    "_csv_idx": idx,
                }
            )

            # Count locations for this Pokemon
            location = row["Location"]
            location_counts[location] = location_counts.get(location, 0) + 1

    # Sort entries by date descending, then by CSV index descending (most recent first)
    pokemon_entries.sort(key=lambda x: (x["_date_dt"], x["_csv_idx"]), reverse=True)

    # Calculate location percentages
    total_entries = len(pokemon_entries)
    location_percentages = []
    if total_entries > 0:
        for location, count in location_counts.items():
            percentage = (count / total_entries) * 100
            location_percentages.append(
                {"location": location, "count": count, "percentage": percentage}
            )

        # Sort by count descending
        location_percentages.sort(key=lambda x: x["count"], reverse=True)

    # Clean up the response
    for entry in pokemon_entries:
        entry.pop("_date_dt", None)
        entry.pop("_csv_idx", None)

    return jsonify(
        {
            "entries": pokemon_entries,
            "location_percentages": location_percentages,
            "total_entries": total_entries,
        }
    )


def ensure_notes_column():
    """Ensure the CSV file has a Notes column, adding it if missing."""
    if not os.path.exists(CSV_FILE):
        return  # File doesn't exist yet, will be created with Notes column

    # Read the first line to check headers
    with open(CSV_FILE, mode="r", newline="", encoding="utf-8") as f:
        first_line = f.readline().strip()
        if not first_line:
            return  # Empty file

        headers = first_line.split(",")

        # If Notes column already exists, we're good
        if "Notes" in headers:
            return

    # Notes column is missing, we need to add it
    print("Notes column not found in CSV. Adding Notes column...")

    # Read all existing data
    rows = []
    with open(CSV_FILE, mode="r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Add empty Notes field to existing rows
            row["Notes"] = ""
            rows.append(row)

    # Write back with Notes column
    with open(CSV_FILE, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Pokemon", "Location", "Date", "Notes"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Successfully added Notes column to {CSV_FILE}")


# Ensure the CSV file exists or create it if not, and ensure Notes column exists
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Pokemon", "Location", "Date", "Notes"])
        writer.writeheader()
else:
    # File exists, ensure it has the Notes column
    ensure_notes_column()


@app.route("/csv_data", methods=["GET"])
def get_csv_data():
    rows = read_csv()
    return jsonify(rows)


@app.route("/csv_update_row", methods=["POST"])
def csv_update_row():
    data = request.json
    row_idx = data.get("row_idx")
    new_row = data.get("row")
    rows = read_csv()
    if 0 <= row_idx < len(rows):
        # Only update allowed fields
        for field in ["Pokemon", "Location", "Date", "Notes"]:
            rows[row_idx][field] = new_row.get(field, rows[row_idx][field])
        write_csv(rows)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Invalid row index"})


@app.route("/csv_add_row", methods=["POST"])
def csv_add_row():
    data = request.json
    new_row = {
        "Pokemon": data.get("Pokemon", ""),
        "Location": data.get("Location", ""),
        "Date": data.get("Date", ""),
        "Notes": data.get("Notes", ""),
    }
    rows = read_csv()
    rows.append(new_row)
    write_csv(rows)
    return jsonify({"success": True})


@app.route("/csv_delete_row", methods=["POST"])
def csv_delete_row():
    data = request.json
    row_idx = data.get("row_idx")
    rows = read_csv()
    if 0 <= row_idx < len(rows):
        rows.pop(row_idx)
        write_csv(rows)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Invalid row index"})


if __name__ == "__main__":
    try:
        # Retrieve primary IP address
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        print("MainsLeaderboard is running at:")
        print()
        print(
            f"http://{ip}:{config['port']}"
            + " | This link is accessible anywhere on your network"
        )
        print(
            f"http://127.0.0.1:{config['port']}"
            + " | This link is only accessible from your local machine"
        )
        print()

        # Deploy web server
        from waitress import serve

        serve(app, host="0.0.0.0", port=config["port"], threads=100)
    except Exception as e:
        import traceback

        print("\nAn error occurred:\n")
        traceback.print_exc()
        input("\nPress Enter to exit...")
