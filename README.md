# Logistica

An AllianceAuth plugin for monitoring EVE Online corporate contract stock levels. Logistica tracks outstanding item exchange contracts and alerts when stock falls below configured minimum thresholds.

## Features

- Dashboard showing outstanding item exchange contracts grouped by location
- Configurable minimum stock thresholds per solar system and contract title
- Visual indicators when stock is below threshold
- Filters contracts to corporations in a specific AllianceAuth state
- Background task to resolve unresolved structure location names via ESI

## Requirements

- [AllianceAuth](https://gitlab.com/allianceauth/allianceauth)
- [allianceauth-corptools](https://github.com/milleruk/allianceauth-corptools) — provides `CorporateContract`, `MapSystem`, and `EveLocation` models
- [django-solo](https://github.com/lazybird/django-solo) — for singleton configuration model
- [django-esi](https://gitlab.com/allianceauth/django-esi) — for ESI API access

## Installation

1. Place the `logistica` directory inside your AllianceAuth project (e.g. alongside `myauth/`).

2. Add `"logistica"` to `INSTALLED_APPS` in your `local.py` settings:

   ```python
   INSTALLED_APPS += [
       "logistica",
   ]
   ```

3. Add the Celery beat schedule for the location resolver task:

   ```python
   from celery.schedules import crontab

   CELERYBEAT_SCHEDULE["logistica_resolve_contract_locations"] = {
       "task": "logistica.tasks.resolve_contract_locations",
       "schedule": crontab(hour="*/6"),
   }
   ```

4. Run database migrations:

   ```bash
   python manage.py migrate logistica
   ```

5. Collect static files:

   ```bash
   python manage.py collectstatic
   ```

6. Restart your AllianceAuth services (Gunicorn, Celery worker, Celery beat).

## Configuration

### Global Configuration

Logistica has a single configuration object managed via the Django admin panel at **Admin → Logistica → Logistica Configuration**.

| Field      | Description                                                                                                                                                    |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `aa_state` | AllianceAuth State to filter contracts by. Only contracts issued by characters in corporations belonging to this state will be shown. Leave blank to show all. |

### Contract Thresholds

Thresholds define the minimum number of outstanding contracts expected for a given title in a given solar system. They can be managed via:

- The web interface at `/logistica/thresholds/` (requires `manage_contract_thresholds` permission)
- The Django admin panel at **Admin → Logistica → Contract Thresholds**

| Field           | Description                                                                                                         |
| --------------- | ------------------------------------------------------------------------------------------------------------------- |
| `solar_system`  | The solar system where the contract originates                                                                      |
| `title`         | The contract title to match                                                                                         |
| `match_type`    | `exact` — title must match exactly (case-insensitive); `contains` — title must contain the value (case-insensitive) |
| `minimum_count` | Minimum number of outstanding contracts expected                                                                    |

Contracts below their threshold are highlighted in red on the dashboard.

## Permissions

| Permission                             | Description                                                  |
| -------------------------------------- | ------------------------------------------------------------ |
| `logistica.view_logistica`             | Can view the logistics dashboard                             |
| `logistica.manage_contract_thresholds` | Can add and delete contract thresholds via the web interface |

Assign these permissions to AllianceAuth groups or states as appropriate. The navigation menu item is only visible to users who hold `view_logistica` or are staff.

## ESI Scopes

The location resolver task uses ESI to fetch structure names. It requires at least one character token with the following scope:

- `esi-universe.read_structures.v1`

The task will attempt to use available tokens until one succeeds. Structures that cannot be resolved (e.g. due to access restrictions) are skipped and logged.

## Background Tasks

| Task                                         | Schedule      | Description                                                                               |
| -------------------------------------------- | ------------- | ----------------------------------------------------------------------------------------- |
| `logistica.tasks.resolve_contract_locations` | Every 6 hours | Resolves structure names for contracts whose start or end location has not yet been named |

## Usage

1. Navigate to **Logistica** in the AllianceAuth menu (requires `view_logistica`).
2. The dashboard shows outstanding item exchange contracts grouped by location.
3. Each row shows the contract title, current count, threshold (if configured), and status.
4. Rows highlighted in red are below their minimum threshold.
5. Expand a row to see individual contract details including issuer, price, and expiry date.
6. Users with `manage_contract_thresholds` can navigate to the **Thresholds** tab to add or remove thresholds.
