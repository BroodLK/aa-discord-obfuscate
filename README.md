# AA Discord Obfuscate

Obfuscate Alliance Auth group names when syncing to Discord by replacing group names
with deterministic, configurable hashes. Includes per-group settings, previews, and
one-click sync actions.

![License](https://img.shields.io/badge/license-GPLv3-green)
![python](https://img.shields.io/badge/python-3.10%2B-informational)
![django](https://img.shields.io/badge/django-4.2-informational)
![allianceauth](https://img.shields.io/badge/allianceauth-4.3.1%2B-informational)

______________________________________________________________________

<!-- mdformat-toc start --slug=github --maxlevel=6 --minlevel=1 -->

- [AA Discord Obfuscate](#aa-discord-obfuscate)
  - [Features](#features)
  - [Requirements](#requirements)
  - [Installation](#installation)
  - [Configuration](#configuration)
    - [App Settings (settings/local.py)](#app-settings-settingslocalpy)
    - [Enable and Schedule Tasks](#enable-and-schedule-tasks)
    - [Default Settings](#default-settings)
  - [Usage](#usage)
    - [Per-Group Obfuscation](#per-group-obfuscation)
    - [Obfuscation Process](#obfuscation-process)
    - [Random Key Rotation](#random-key-rotation)
    - [Role Coloring](#role-coloring)
  - [Limitations](#limitations)
  - [Troubleshooting](#troubleshooting)
  - [Uninstall / Reset](#uninstall--reset)
  - [Development](#development)

<!-- mdformat-toc end -->

______________________________________________________________________

## Features<a name="features"></a>

- Obfuscates Discord role names for Alliance Auth groups using HMAC hashes.
- Per-group controls in Django admin: opt out, custom name override, method, format, dividers, and role color.
- Optional per-group role color applied during sync.
- Optional per-group random key mode with periodic rotation and role shuffling.
- Pattern-based role color rules for new roles.
- Preview and bulk sync actions in Django admin.

> [!CAUTION]
> This will not work on roles that are above the bot. Attempting to modify roles that are above the bot will result in an error and potentially terrible terrible things..

## Requirements<a name="requirements"></a>

- Alliance Auth 4.3.1+ (<5)
- Python 3.11+
- Discord service configured in Alliance Auth (bot and guild)

## Installation<a name="installation"></a>

Install the app in your AA virtual environment:

```bash
pip install git+https://github.com/ppfeufer/aa-discord-obfuscate
```

Add the app to your AA `INSTALLED_APPS` in `settings/local.py`:

```python
INSTALLED_APPS += [
    "discord_obfuscate",
]
```

Run migrations and restart AA:

```bash
python manage.py migrate
```

## Configuration<a name="configuration"></a>

### App Settings (settings/local.py)<a name="app-settings-settingslocalpy"></a>

Only one optional setting is supported in `settings/local.py`:

> [!CAUTION]
> Because this repository is public, anyone can see what this defaults to, not changing this to a unique value poses a significant security risk unless random keys are used.

```python
# Discord Obfuscate
DISCORD_OBFUSCATE_SECRET = "change-me"  # Defaults to SECRET_KEY
```

All other behavior is configured in Django admin.

### Enable and Schedule Tasks<a name="enable-and-schedule-tasks"></a>

The app ships periodic tasks, but they only run when enabled
1) Create the periodic tasks:

```bash
python manage.py obfuscate_setup
```

2) In Django admin, open `Discord Obfuscate Config` and enable the task toggles
   you need: `Periodic sync`, `Role color rule sync`, and/or `Random key rotation`.

This creates three periodic tasks in `Periodic Tasks` disabled by default:

- `Obfuscate Discord: Sync all roles` (hourly)
- `Obfuscate Discord: Sync role colors` (hourly)
- `Obfuscate Discord: Rotate random keys` (every 3 days)

> [!WARNING]
> You need to enable the periodic tasks in Periodic Tasks and the App's Configuration Admin to run them. The tasks exit early when their config toggles are disabled.

You can adjust
schedules in Django admin under `Periodic Tasks`.

### Default Settings<a name="default-settings"></a>

Use the `Discord Obfuscate Config` in Django admin to control defaults
for newly created per-group entries:

- `Sync on save` queues a rename task when you save a per-group config. (recommended)
- `Default opt-out` sets new entries to keep the original group name.
- `Default use random key` turns on random-key mode by default.
- `Default rotate name/position` controls the random key rotation behavior.
- `Default obfuscation type` chooses the hashing method for new entries.
- `Default divider characters` and `Default min chars before divider` set output
  formatting defaults.
- `Random key rotation enabled` periodically changes the random key used for random key input, and therfore changes the name of the obfuscated roles
- `Random key reposition enabled` periodically changes where the role is positioned in the list of discord roles for another layer of obfuscation
- `Role color rule sync enabled` and `Periodic sync enabled` gate their
  respective tasks.

Defaults are applied when entries are created.

## Usage<a name="usage"></a>

### Per-Group Obfuscation<a name="per-group-obfuscation"></a>

1) Go to `Discord Role Obfuscations` in Django admin.
2) Use the `Discover groups from Discord roles` action to create entries for
   roles that already exist in Discord, or **add entries manually** (recommended).
3) Configure per-group options:
   - Opt out to keep the original group name.
   - Custom name override (takes precedence over hashing).
   - Random key mode plus rotation flags.
   - Obfuscation method, format, divider characters, and min chars per divider.
   - Optional fixed role color (`#RRGGBB`).
4) Use the preview field to verify the output name.
5) Use the admin actions `Sync selected roles now` or `Sync all roles now`, or
   rely on sync-on-save (recommended) / periodic sync.

### Obfuscation Process<a name="obfuscation-process"></a>

When the Discord service requests group names, the app intercepts and computes the desired role
name for each group:

1) If `Opt out` is enabled, the original group name is used.
2) If `Custom name` is set, that value is sanitized and used.
3) Otherwise, the input is the group name or the random key (if enabled).
4) The input is hashed with HMAC using `DISCORD_OBFUSCATE_SECRET` and the
   selected method (SHA256/BLAKE2s with hex/base32 encoding).
5) The output is formatted with the per-group format (or `{hash12}`),
   sanitized to allowed characters, dividers inserted (if configured), and
   truncated to 100 characters.

When a sync runs, the app:

- Finds an existing Discord role by desired name, cached role ID, last obfuscated
  name, or original group name.
- Renames the role to the desired obfuscated name.
- Applies the per-group role color if set.

> [!NOTE]
> If no matching role exists, the Discord service can create it using the desired
> obfuscated name.

### Random Key Rotation<a name="random-key-rotation"></a>

Enable `Use random key` on a per-group basis to generate a 16-character
alphanumeric key that replaces the group name for obfuscation input. When the
random-key rotation task is enabled in Discord Obfuscate config, it will:

- Rotate keys for entries with `Use random key` enabled.
- Rename those roles to the newly obfuscated names.
- Shuffle those roles into the bottom positions in a random order. (if enabled)

Each random-key entry can opt out of renaming or repositioning via the two
checkboxes shown when `Use random key` is enabled.

### Role Coloring<a name="role-coloring"></a>

There are two ways to color roles. Per-group colors always take precedence.

Per-group fixed color:

- Set `Role color` on a `Discord Role Obfuscation` entry (`#RRGGBB`).
- The next sync applies that color when renaming, even if the name already matches.
- Roles with a fixed color are treated as pinned and are skipped by rule-based colors.
  Run a sync after setting a fixed color so the role ID is cached.

Rule-based random colors:

1) Create one or more `Discord Role Color Rules` with a name pattern
   (use `*` as the wildcard), optional case sensitivity, and a priority
   (lower numbers run first).
2) Enable `Role color rule sync` in `Discord Obfuscate Config`.
3) Enable the task in `Periodic Tasks`.

When the rule sync task runs, it:

- Scans all Discord roles and existing color assignments.
- Skips roles that already have a color, are pinned by per-group settings,
  or already have an assignment.
- Builds a 250-color palette and chooses a random unused color for each match.
- Updates the role in Discord and stores a `Discord Role Color Assignment`.
- Keeps assignments stable and cleans up stale ones if roles disappear.

## Limitations<a name="limitations"></a>

- State-based role mapping is not supported. The Alliance Auth Discord service
  passes a `state_name` argument, but this app ignores it and only uses group
  memberships.

## Uninstall / Reset<a name="uninstall--reset"></a>

If you want to fully remove this app and all of its data, do the following:

0) Reset role names (recommended)
- Set the obfuscation entry to opt-out for each group so the original group name
  is used, then run a sync to rename roles back to their defaults. (or save if you use update on save)

1) Stop services
- Stop the Celery worker/beat so no tasks run during cleanup.

2) Disable scheduled tasks (optional but recommended)
- In Django admin (`django_celery_beat`), delete periodic tasks named:
  - `Obfuscate Discord: Sync all roles`
  - `Obfuscate Discord: Sync role colors`
  - `Obfuscate Discord: Rotate random keys`

3) Remove database tables
- Run:

```bash
python manage.py migrate discord_obfuscate zero
```

This drops all `discord_obfuscate` tables and data.

4) Remove the app from settings
- Remove `discord_obfuscate` from `INSTALLED_APPS`.

5) Delete code
- Uninstall the package or remove the app directory, then restart Alliance Auth.

If you want to reset without uninstalling:
- Run step 3 only, then re‑run:

```bash
python manage.py migrate
```

This recreates empty tables with a clean state.
