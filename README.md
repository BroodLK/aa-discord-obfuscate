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
  - [Usage](#usage)
    - [Optional Periodic Sync](#periodic-sync)
    - [Role Color Rules](#role-color-rules)
    - [Random Key Rotation](#random-key-rotation)
    - [Admin Labels](#admin-labels)
  - [How It Works](#how-it-works)
  - [Troubleshooting](#troubleshooting)
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
- Optional automatic sync on save via Celery tasks.

## Requirements<a name="requirements"></a>

- Alliance Auth 4.3.1+ (<5)
- Python 3.10+
- Discord service configured in Alliance Auth (bot and guild)
- Celery worker (for async sync actions)

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

## Usage<a name="usage"></a>

- Admin UI: manage everything in Django admin.
- Permissions: grant users `discord_obfuscate.basic_access` to access the admin section.
- Optional: enable sync-on-save and/or periodic sync in the Discord Obfuscate config.

### Optional Periodic Sync<a name="periodic-sync"></a>

If you want a periodic safety sync, enable it in the Discord Obfuscate config
in Django admin. The setup command will create an hourly task (tasks exit early
when disabled):

```bash
python manage.py obfuscate_setup
```

### Role Color Rules<a name="role-color-rules"></a>

Create role color rules in Django admin to match role name patterns (use `*` as
the wildcard). Periodic sync will assign a random unused color from a 250-color
palette to newly created matching roles. Enable the role color sync option in
Discord Obfuscate config. The setup command will create an hourly task (tasks
exit early when disabled).

### Random Key Rotation<a name="random-key-rotation"></a>

Enable `Use random key` on a per-group basis to generate a 16-character
alphanumeric key that replaces the group name for obfuscation input. When the
random-key rotation task is enabled in Discord Obfuscate config, it will:

- Rotate keys for entries with `Use random key` enabled.
- Rename those roles to the newly obfuscated names.
- Shuffle those roles into the bottom positions in a random order.

Each random-key entry can opt out of renaming or repositioning via the two
checkboxes shown when `Use random key` is enabled.

Run `python manage.py obfuscate_setup` after enabling the rotation option to
create the periodic task (default: every 3 days; tasks exit early when disabled).

### Admin Labels<a name="admin-labels"></a>

The admin uses title-cased labels for the new sections and shows
`Obfuscated Name` for the last obfuscated role name field.

### Per-Group Options (Admin)

These options are configured per group in Django admin:

- Opt out of obfuscation and keep the original group name.
- Provide a custom name override.
- Use a random key (16 chars) for obfuscation input.
- Choose the hashing method (SHA256/BLAKE2s, hex/base32).
- Customize the output format and dividers.
- Sync role names immediately for selected groups or all groups.

## How It Works<a name="how-it-works"></a>

- On startup the app patches the Alliance Auth Discord service to replace
  `_user_group_names` with obfuscated names.
- Each group can opt out, use a custom name, or use a hash-based name.
- Sync tasks rename existing Discord roles to their obfuscated names.

## Troubleshooting<a name="troubleshooting"></a>

- If roles are not changing, make sure the Discord service is configured and a
  Celery worker is running.
- If roles are missing, create them in Discord and then run a sync.

## Development<a name="development"></a>

Run tests:

```bash
python runtests.py
```
