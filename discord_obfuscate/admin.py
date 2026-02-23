"""Admin models."""

# Standard Library
import json
from collections.abc import Mapping

# Django
from django.contrib import admin, messages
from django.contrib.auth.models import Group
from django.http import JsonResponse
from django.urls import path

# Third Party
from solo.admin import SingletonModelAdmin

# Discord Obfuscate App
from discord_obfuscate.constants import DEFAULT_OBFUSCATE_METHOD
from discord_obfuscate.config import default_obfuscation_values, sync_on_save_enabled
from discord_obfuscate.forms import (
    DiscordObfuscateConfigForm,
    DiscordRoleObfuscationForm,
    DiscordRoleOrderConfigForm,
)
from discord_obfuscate.models import (
    DiscordObfuscateConfig,
    DiscordRoleColorAssignment,
    DiscordRoleColorRule,
    DiscordRoleObfuscation,
    DiscordRoleOrder,
    DiscordRoleOrderConfig,
)
from discord_obfuscate.obfuscation import (
    fetch_roleset,
    generate_random_key,
    role_name_for_group,
)
from discord_obfuscate.role_colors import to_hex
from discord_obfuscate.tasks import sync_all_roles, sync_group_role

# Register your models here.

def _role_position(role, default=0):
    if role is None:
        return default
    if isinstance(role, Mapping):
        value = role.get("position", default)
    else:
        value = getattr(role, "position", default)
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _role_sort_key(role):
    position = _role_position(role, default=0)
    role_id = getattr(role, "id", 0) or 0
    try:
        role_id = int(role_id)
    except (TypeError, ValueError):
        role_id = 0
    return (-position, role_id)


def _role_is_everyone(role) -> bool:
    if role is None:
        return False
    if isinstance(role, Mapping):
        return role.get("name") == "@everyone"
    return getattr(role, "name", "") == "@everyone"


@admin.register(DiscordRoleObfuscation)
class DiscordRoleObfuscationAdmin(admin.ModelAdmin):
    form = DiscordRoleObfuscationForm
    list_display = (
        "group",
        "role_exists",
        "opt_out",
        "use_random_key",
        "random_key_rotate_name",
        "random_key_rotate_position",
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
        "use_random_key",
        "random_key",
        "random_key_rotate_name",
        "random_key_rotate_position",
        "role_color_enabled",
        "role_color",
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
        if obj and obj.group_id:
            qs = (qs | Group.objects.filter(pk=obj.group_id)).distinct()
        if "group" in form.base_fields:
            form.base_fields["group"].queryset = qs
        return form

    @admin.action(description="Discover groups from Discord roles")
    def discover_roles(self, request, queryset):
        roleset = fetch_roleset(use_cache=True)
        role_names = {role.name for role in roleset}
        groups = Group.objects.filter(name__in=role_names)
        defaults = default_obfuscation_values()
        defaults.setdefault("obfuscation_type", DEFAULT_OBFUSCATE_METHOD)
        created = 0
        for group in groups:
            _, was_created = DiscordRoleObfuscation.objects.get_or_create(
                group=group,
                defaults=defaults,
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
        use_random_key = request.POST.get("use_random_key") in {"on", "true", "1"}
        random_key = (request.POST.get("random_key") or "").strip()
        rotate_name = request.POST.get("random_key_rotate_name") in {"on", "true", "1"}
        rotate_position = request.POST.get("random_key_rotate_position") in {
            "on",
            "true",
            "1",
        }
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
            use_random_key=use_random_key,
            random_key=random_key or (generate_random_key(16) if use_random_key else ""),
            random_key_rotate_name=rotate_name if use_random_key else False,
            random_key_rotate_position=rotate_position if use_random_key else False,
        )
        temp_config.set_dividers(dividers)
        preview = role_name_for_group(temp_group, temp_config)

        return JsonResponse({"preview": preview})


@admin.register(DiscordObfuscateConfig)
class DiscordObfuscateConfigAdmin(SingletonModelAdmin):
    form = DiscordObfuscateConfigForm
    fieldsets = (
        (
            "Sync Behavior",
            {
                "description": (
                    "Controls when sync runs and whether roles must already exist in Discord."
                ),
                "fields": (
                    "sync_on_save",
                    "periodic_sync_enabled",
                    "require_existing_role",
                )
            },
        ),
        (
            "Defaults for New Entries",
            {
                "description": "Applied when new per-group configs are created.",
                "fields": (
                    "default_opt_out",
                    "default_use_random_key",
                    "default_random_key_rotate_name",
                    "default_random_key_rotate_position",
                    "default_obfuscation_type",
                    "default_divider_characters",
                    "default_min_chars_before_divider",
                )
            },
        ),
        (
            "Random Key Rotation",
            {
                "description": "Controls periodic random key rotation.",
                "fields": (
                    "random_key_rotation_enabled",
                )
            },
        ),
        (
            "Role Color Rules",
            {
                "description": "Controls periodic color assignment for matching roles.",
                "fields": ("role_color_rule_sync_enabled",),
            },
        ),
    )


@admin.register(DiscordRoleOrderConfig)
class DiscordRoleOrderConfigAdmin(SingletonModelAdmin):
    form = DiscordRoleOrderConfigForm
    change_form_template = "admin/discord_obfuscate/discordroleorderconfig/change_form.html"
    fieldsets = (
        (
            "Role Ordering",
            {
                "description": (
                    "Configure manual role ordering and select the bot role "
                    "to lock roles above it."
                ),
                "fields": (
                    "enabled",
                    "bot_role_id",
                    "reorder_mode",
                )
            },
        ),
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj=obj, **kwargs)
        roleset = fetch_roleset(use_cache=True)
        roles = sorted(list(roleset), key=_role_sort_key)
        choices = [("", "---------")]
        for role in roles:
            choices.append((str(role.id), f"{role.name} ({role.id})"))
        if "bot_role_id" in form.base_fields:
            form.base_fields["bot_role_id"].choices = choices
        return form

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not obj.enabled:
            return
        payload_raw = request.POST.get("role_order_data") or ""
        if not payload_raw:
            return
        try:
            payload = json.loads(payload_raw)
        except (TypeError, ValueError):
            messages.error(request, "Failed to parse role ordering payload.")
            return
        if not isinstance(payload, list):
            messages.error(request, "Invalid role ordering payload.")
            return

        roleset = fetch_roleset(use_cache=False)
        roles_by_id = {role.id: role for role in roleset}
        seen_ids: set[int] = set()
        for index, item in enumerate(payload, start=1):
            try:
                role_id = int(item.get("role_id"))
            except (TypeError, ValueError):
                continue
            user_locked = bool(item.get("locked"))
            role = roles_by_id.get(role_id)
            role_name = role.name if role else ""
            role_color = ""
            if role and getattr(role, "color", 0):
                role_color = to_hex(int(role.color))
            DiscordRoleOrder.objects.update_or_create(
                role_id=role_id,
                defaults={
                    "sort_order": index,
                    "locked": user_locked,
                    "role_name": role_name,
                    "role_color": role_color,
                },
            )
            seen_ids.add(role_id)

        if seen_ids:
            DiscordRoleOrder.objects.exclude(role_id__in=seen_ids).delete()
            messages.success(request, "Saved role ordering.")

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        roleset = fetch_roleset(use_cache=False)
        roles = list(roleset)
        roles_by_id = {role.id: role for role in roles}
        roles_by_name = {role.name: role for role in roles}
        configs = list(DiscordRoleObfuscation.objects.select_related("group"))
        config_by_role_id = {}

        for config in configs:
            role_id = None
            if config.role_id and config.role_id in roles_by_id:
                role_id = config.role_id
            else:
                desired = role_name_for_group(config.group, config)
                for name in (desired, config.last_obfuscated_name, config.group.name):
                    if name and name in roles_by_name:
                        role_id = roles_by_name[name].id
                        break
            if role_id and role_id not in config_by_role_id:
                config_by_role_id[role_id] = config

        order_entries = list(DiscordRoleOrder.objects.all())
        order_by_id = {entry.role_id: entry for entry in order_entries}
        ordered_ids = [
            entry.role_id
            for entry in sorted(order_entries, key=lambda e: e.sort_order)
            if entry.role_id in roles_by_id
        ]
        remaining_ids = [
            role.id
            for role in sorted(roles, key=_role_sort_key)
            if role.id not in ordered_ids
        ]
        display_ids = ordered_ids + remaining_ids

        obj = self.get_object(request, object_id) if object_id else None
        if obj is None:
            obj = DiscordRoleOrderConfig.get_solo()
        bot_role_id = getattr(obj, "bot_role_id", None)
        bot_role = roles_by_id.get(bot_role_id) if bot_role_id else None
        bot_position = _role_position(bot_role, default=None) if bot_role else None

        warnings = []
        if not roles:
            warnings.append("Failed to load roles from Discord.")
        else:
            positions = [_role_position(role, default=None) for role in roles]
            if len(roles) > 1 and (not positions or all(pos == 0 for pos in positions if pos is not None)):
                warnings.append(
                    "Role positions unavailable from Discord; ordering may be incorrect."
                )
        if bot_role_id and not bot_role:
            warnings.append("Configured bot role not found in Discord roles.")
        if not bot_role_id:
            warnings.append("Bot role not set; roles above the bot cannot be locked.")
        if obj and not obj.enabled:
            warnings.append("Role ordering is disabled. Enable it above to edit this table.")

        rows = []
        for role_id in display_ids:
            role = roles_by_id.get(role_id)
            if not role:
                continue
            config = config_by_role_id.get(role.id)
            reasons = []
            if _role_is_everyone(role):
                reasons.append("@everyone")
            if bot_position is not None and _role_position(role) >= bot_position:
                reasons.append("above bot")
            if config and config.opt_out:
                reasons.append("opt out")
            if config and config.use_random_key and not config.random_key_rotate_position:
                reasons.append("reorder disabled")
            system_locked = bool(reasons)
            user_locked = bool(order_by_id.get(role.id).locked) if role.id in order_by_id else False
            color_value = ""
            if getattr(role, "color", 0):
                color_value = to_hex(int(role.color))
            rows.append(
                {
                    "role_id": role.id,
                    "name": role.name,
                    "color": color_value,
                    "position": _role_position(role, default=None),
                    "user_locked": user_locked,
                    "system_locked": system_locked,
                    "lock_reasons": ", ".join(reasons),
                }
            )

        extra_context["role_order_rows"] = rows
        extra_context["role_order_warnings"] = warnings
        extra_context["role_order_enabled"] = bool(getattr(obj, "enabled", False))
        return super().changeform_view(
            request,
            object_id=object_id,
            form_url=form_url,
            extra_context=extra_context,
        )


class DiscordRoleColorAssignmentInline(admin.TabularInline):
    model = DiscordRoleColorAssignment
    extra = 0
    fields = ("role_name", "role_id", "color", "updated_at")
    readonly_fields = ("role_name", "role_id", "color", "updated_at")
    can_delete = False
    show_change_link = False


@admin.register(DiscordRoleColorRule)
class DiscordRoleColorRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "pattern", "enabled", "priority", "updated_at")
    list_filter = ("enabled",)
    search_fields = ("name", "pattern")
    fields = (
        "name",
        "pattern",
        "enabled",
        "case_sensitive",
        "priority",
    )
    inlines = [DiscordRoleColorAssignmentInline]


@admin.register(DiscordRoleColorAssignment)
class DiscordRoleColorAssignmentAdmin(admin.ModelAdmin):
    list_display = ("role_name", "color", "rule", "updated_at")
    list_filter = ("rule",)
    search_fields = ("role_name", "color")
    readonly_fields = ("rule", "role_name", "role_id", "color", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
