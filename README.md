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
  - [How It Works](#how-it-works)
  - [Troubleshooting](#troubleshooting)
  - [Development](#development)

<!-- mdformat-toc end -->

______________________________________________________________________

## Features<a name="features"></a>

- Obfuscates Discord role names for Alliance Auth groups using HMAC hashes.
- Per-group controls in Django admin: opt out, custom name override, method, format, dividers.
- Optional per-group role color applied during sync.
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
in Django admin and then run:

```bash
python manage.py discord_obfuscate_setup_periodic_tasks
```

### Per-Group Options (Admin)

These options are configured per group in Django admin:

- Opt out of obfuscation and keep the original group name.
- Provide a custom name override.
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
