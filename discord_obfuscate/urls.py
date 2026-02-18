"""App URLs"""

# Django
from django.urls import path

# AA Discord Obfuscate App
from discord_obfuscate import views

app_name: str = "discord_obfuscate"  # pylint: disable=invalid-name

urlpatterns = [
    path("", views.index, name="index"),
]
