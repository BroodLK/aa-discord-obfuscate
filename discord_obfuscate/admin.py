"""Admin models."""

# Django
from django.contrib import admin, messages
from django.contrib.auth.models import Group
from django.http import JsonResponse
from django.urls import path

# Third Party
from solo.admin import SingletonModelAdmin

# Discord Obfuscate App
from discord_obfuscate.app_settings import DISCORD_OBFUSCATE_DEFAULT_METHOD
from discord_obfuscate.config import sync_on_save_enabled
from discord_obfuscate.forms import (
    DiscordObfuscateConfigForm,
    DiscordRoleObfuscationForm,
)
from discord_obfuscate.models import DiscordObfuscateConfig, DiscordRoleObfuscation
from discord_obfuscate.obfuscation import fetch_roleset, role_name_for_group
from discord_obfuscate.tasks import sync_all_roles, sync_group_role

# Register your models here.


@admin.register(DiscordRoleObfuscation)
class DiscordRoleObfuscationAdmin(admin.ModelAdmin):
    form = DiscordRoleObfuscationForm
    list_display = (
        "group",
        "role_exists",
        "opt_out",
        "obfuscation_type",
        "custom_name",
        "last_obfuscated_name",
    )
    search_fields = ("group__name", "custom_name")
    list_filter = ("opt_out", "obfuscation_type")
    actions = ["discover_roles", "sync_selected_roles", "sync_all_roles_action"]
    fields = (
        "group",
        "opt_out",
        "custom_name",
        "obfuscation_type",
        "obfuscation_format",
        "divider_characters",
        "min_chars_before_divider",
        "preview",
    )

    class Media:
        js = ("discord_obfuscate/admin_preview.js",)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("group")
        self._roleset = fetch_roleset(use_cache=True)
        return qs

    def role_exists(self, obj):
        roleset = getattr(self, "_roleset", None) or fetch_roleset(use_cache=True)
        desired = role_name_for_group(obj.group, obj)
        if roleset.role_by_name(desired):
            return True
        if roleset.role_by_name(obj.group.name):
            return True
        if obj.role_id:
            for role in roleset:
                if role.id == obj.role_id:
                    return True
        return False

    role_exists.boolean = True
    role_exists.short_description = "Role Exists"

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj=obj, **kwargs)
        roleset = fetch_roleset(use_cache=True)
        role_names = {role.name for role in roleset}
        qs = Group.objects.filter(name__in=role_names)
        if obj:
            qs = (qs | Group.objects.filter(pk=obj.group_id)).distinct()
        if "group" in form.base_fields:
            form.base_fields["group"].queryset = qs
        return form

    @admin.action(description="Discover groups from Discord roles")
    def discover_roles(self, request, queryset):
        roleset = fetch_roleset(use_cache=True)
        role_names = {role.name for role in roleset}
        groups = Group.objects.filter(name__in=role_names)
        created = 0
        for group in groups:
            _, was_created = DiscordRoleObfuscation.objects.get_or_create(
                group=group,
                defaults={"obfuscation_type": DISCORD_OBFUSCATE_DEFAULT_METHOD},
            )
            if was_created:
                created += 1
        messages.success(request, f"Discovered {created} new groups.")

    @admin.action(description="Sync selected roles now")
    def sync_selected_roles(self, request, queryset):
        count = 0
        for config in queryset:
            sync_group_role.delay(config.group_id)
            count += 1
        messages.success(request, f"Queued sync for {count} groups.")

    @admin.action(description="Sync all roles now")
    def sync_all_roles_action(self, request, queryset):
        sync_all_roles.delay()
        messages.success(request, "Queued sync for all groups.")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not sync_on_save_enabled():
            return
        if form and form.has_changed():
            sync_group_role.delay(obj.group_id)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "preview/",
                self.admin_site.admin_view(self.preview_view),
                name="discord_obfuscate_preview",
            ),
        ]
        return custom_urls + urls

    def preview_view(self, request):
        if request.method != "POST":
            return JsonResponse({"error": "POST required"}, status=405)

        group_id = request.POST.get("group")
        group_name = ""
        if group_id:
            try:
                group_name = Group.objects.get(pk=group_id).name
            except Group.DoesNotExist:
                group_name = ""

        if not group_name:
            return JsonResponse({"preview": ""})

        custom_name = (request.POST.get("custom_name") or "").strip()
        opt_out = request.POST.get("opt_out") in {"on", "true", "1"}
        obfuscation_type = request.POST.get("obfuscation_type")
        obfuscation_format = (request.POST.get("obfuscation_format") or "").strip()
        min_chars = int(request.POST.get("min_chars_before_divider") or 0)
        dividers = request.POST.getlist("divider_characters")

        temp_group = Group(id=group_id, name=group_name)
        temp_config = DiscordRoleObfuscation(
            group=temp_group,
            opt_out=opt_out,
            obfuscation_type=obfuscation_type,
            obfuscation_format=obfuscation_format,
            custom_name=custom_name,
            min_chars_before_divider=min_chars,
        )
        temp_config.set_dividers(dividers)
        preview = role_name_for_group(temp_group, temp_config)

        return JsonResponse({"preview": preview})


@admin.register(DiscordObfuscateConfig)
class DiscordObfuscateConfigAdmin(SingletonModelAdmin):
    form = DiscordObfuscateConfigForm
    fields = (
        "sync_on_save",
        "role_color_enabled",
        "role_color",
        "periodic_sync_enabled",
        "periodic_sync_minute",
        "periodic_sync_hour",
        "periodic_sync_day_of_week",
        "periodic_sync_day_of_month",
        "periodic_sync_month_of_year",
        "periodic_sync_timezone",
    )
