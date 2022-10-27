"""Defines the test app config."""

from django.apps import AppConfig
from admin_auto_filters.views import AutocompleteJsonView


class TestappConfig(AppConfig):
    name = 'tests.testapp'
