"""Admin models."""

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
)
from discord_obfuscate.models import (
    DiscordObfuscateConfig,
    DiscordRoleColorAssignment,
    DiscordRoleColorRule,
    DiscordRoleObfuscation,
)
from discord_obfuscate.obfuscation import (
    fetch_roleset,
    generate_random_key,
    role_name_for_group,
)
from discord_obfuscate.tasks import sync_all_roles, sync_group_role

# Register your models here.


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
    fields = (
        "sync_on_save",
        "default_opt_out",
        "default_use_random_key",
        "default_random_key_rotate_name",
        "default_random_key_rotate_position",
        "default_obfuscation_type",
        "default_divider_characters",
        "default_min_chars_before_divider",
        "random_key_rotation_enabled",
        "random_key_reposition_enabled",
        "role_color_rule_sync_enabled",
        "periodic_sync_enabled",
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
