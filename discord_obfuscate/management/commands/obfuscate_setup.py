"""Create or enable periodic tasks for discord_obfuscate."""

# Django
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

# Discord Obfuscate App
from discord_obfuscate.config import (
    periodic_sync_enabled,
    random_key_rotation_enabled,
    role_color_rule_sync_enabled,
)


class Command(BaseCommand):
    help = "Create or enable periodic Celery beat tasks for discord_obfuscate."

    def handle(self, *args, **options):
        try:
            from django_celery_beat.models import CrontabSchedule, PeriodicTask
        except Exception as exc:
            raise CommandError(
                "django_celery_beat is required to create periodic tasks."
            ) from exc

        hourly = {
            "minute": "0",
            "hour": "*/1",
            "day_of_week": "*",
            "day_of_month": "*",
            "month_of_year": "*",
            "timezone": settings.TIME_ZONE,
        }
        every_three_days = {
            "minute": "0",
            "hour": "0",
            "day_of_week": "*",
            "day_of_month": "*/3",
            "month_of_year": "*",
            "timezone": settings.TIME_ZONE,
        }

        self._ensure_periodic_task(
            PeriodicTask,
            CrontabSchedule,
            "discord_obfuscate_sync_all_roles",
            "discord_obfuscate.tasks.sync_all_roles",
            periodic_sync_enabled(),
            hourly,
        )
        self._ensure_periodic_task(
            PeriodicTask,
            CrontabSchedule,
            "discord_obfuscate_rotate_random_keys",
            "discord_obfuscate.tasks.rotate_random_keys_and_reorder_roles",
            random_key_rotation_enabled(),
            every_three_days,
        )
        self._ensure_periodic_task(
            PeriodicTask,
            CrontabSchedule,
            "discord_obfuscate_sync_role_colors",
            "discord_obfuscate.tasks.sync_role_color_rules",
            role_color_rule_sync_enabled(),
            hourly,
        )

    def _ensure_periodic_task(
        self,
        PeriodicTask,
        CrontabSchedule,
        name: str,
        task_path: str,
        enabled: bool,
        schedule: dict,
    ):
        if not enabled:
            task = PeriodicTask.objects.filter(name=name).first()
            if task and task.enabled:
                task.enabled = False
                task.save(update_fields=["enabled"])
                self.stdout.write(f"Disabled periodic task '{name}'.")
            else:
                self.stdout.write(f"Periodic task '{name}' is disabled.")
            return

        minute = schedule.get("minute", "0")
        hour = schedule.get("hour", "*/1")
        day_of_week = schedule.get("day_of_week", "*")
        day_of_month = schedule.get("day_of_month", "*")
        month_of_year = schedule.get("month_of_year", "*")
        timezone = schedule.get("timezone")

        task = PeriodicTask.objects.filter(name=name).first()
        if task:
            if not task.enabled:
                task.enabled = True
                task.save(update_fields=["enabled"])
                self.stdout.write(f"Enabled periodic task '{name}'.")
            else:
                self.stdout.write(f"Periodic task '{name}' already exists.")
            return

        crontab, _ = CrontabSchedule.objects.get_or_create(
            minute=minute,
            hour=hour,
            day_of_week=day_of_week,
            day_of_month=day_of_month,
            month_of_year=month_of_year,
            timezone=timezone,
        )

        task = PeriodicTask.objects.create(
            name=name,
            task=task_path,
            crontab=crontab,
            enabled=True,
        )

        self.stdout.write(
            f"Created periodic task '{task.name}' with schedule {minute} {hour} "
            f"{day_of_month} {month_of_year} {day_of_week} ({timezone})."
        )
