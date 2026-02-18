"""App Views"""

# Django
from django.contrib.auth.decorators import login_required, permission_required
from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.contrib import messages
from django.forms import modelformset_factory
from django.contrib.auth.models import Group

# Discord Obfuscate App
from discord_obfuscate.app_settings import (
    DISCORD_OBFUSCATE_DEFAULT_METHOD,
    DISCORD_OBFUSCATE_SYNC_ON_SAVE,
)
from discord_obfuscate.forms import DiscordRoleObfuscationForm
from discord_obfuscate.models import DiscordRoleObfuscation
from discord_obfuscate.obfuscation import fetch_roleset, role_name_for_group
from discord_obfuscate.tasks import sync_all_roles, sync_group_role


@login_required
@permission_required("discord_obfuscate.basic_access")
def index(request: WSGIRequest) -> HttpResponse:
    """
    Index view
    :param request:
    :return:
    """

    roleset = fetch_roleset(use_cache=True)
    groups = list(Group.objects.order_by("name"))
    configs = {
        cfg.group_id: cfg
        for cfg in DiscordRoleObfuscation.objects.filter(group__in=groups)
    }

    def _group_has_role(group, config):
        desired = role_name_for_group(group, config)
        if roleset.role_by_name(desired):
            return True
        if roleset.role_by_name(group.name):
            return True
        if config and config.role_id:
            for role in roleset:
                if role.id == config.role_id:
                    return True
        return False

    managed_groups = [
        group for group in groups if _group_has_role(group, configs.get(group.id))
    ]

    for group in managed_groups:
        if group.id not in configs:
            configs[group.id], _ = DiscordRoleObfuscation.objects.get_or_create(
                group=group,
                defaults={"obfuscation_type": DISCORD_OBFUSCATE_DEFAULT_METHOD},
            )

    FormSet = modelformset_factory(
        DiscordRoleObfuscation, form=DiscordRoleObfuscationForm, extra=0
    )

    queryset = DiscordRoleObfuscation.objects.filter(
        group__in=managed_groups
    ).select_related("group")

    if request.method == "POST":
        if "sync_all" in request.POST:
            sync_all_roles.delay()
            messages.success(request, "Queued role sync for all groups.")
            return redirect("discord_obfuscate:index")

        formset = FormSet(request.POST, queryset=queryset)
        if formset.is_valid():
            changed_group_ids = []
            for form in formset:
                if form.has_changed():
                    instance = form.save()
                    changed_group_ids.append(instance.group_id)
            if DISCORD_OBFUSCATE_SYNC_ON_SAVE:
                for group_id in changed_group_ids:
                    sync_group_role.delay(group_id)
            messages.success(request, "Settings saved.")
            return redirect("discord_obfuscate:index")
    else:
        formset = FormSet(queryset=queryset)

    rows = []
    for form in formset:
        group = form.instance.group
        config = configs.get(group.id)
        desired_name = role_name_for_group(group, config)
        current_role = roleset.role_by_name(desired_name) or roleset.role_by_name(
            group.name
        )
        rows.append(
            {
                "group": group,
                "form": form,
                "desired_name": desired_name,
                "current_role": current_role.name if current_role else "",
                "role_exists": bool(current_role),
            }
        )

    context = {"rows": rows, "formset": formset}

    return render(request, "discord_obfuscate/index.html", context)
