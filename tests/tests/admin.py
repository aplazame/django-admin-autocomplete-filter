from django.contrib import admin
from django.shortcuts import HttpResponse
from django.urls import path
from django.conf.urls import url
from admin_auto_filters.views import AutocompleteJsonView



class MyAdminSite(admin.AdminSite):
    def get_urls(self):
        urls = super().get_urls()
        custom_autocomplete = url(
            r'^custom-autocomplete/$',
            self.admin_view(AutocompleteJsonView.as_view(admin_site=self)),
            name='custom-autocomplete'
        )
        urls = [custom_autocomplete] + urls
        return urls
