from django.apps import apps
from django.contrib.admin.views.autocomplete import AutocompleteJsonView as Base
from django.core.exceptions import FieldDoesNotExist, PermissionDenied
from django.http import Http404


class AutocompleteJsonView(Base):
    """Overriding django admin's AutocompleteJsonView"""

    def process_request(self, request):
        """
        Validate request integrity, extract and return request parameters.
        Since the subsequent view permission check requires the target model
        admin, which is determined here, raise PermissionDenied if the
        requested app, model or field are malformed.
        Raise Http404 if the target model admin is not configured properly with
        search_fields.
        """
        term = request.GET.get('term', '')
        try:
            app_label = request.GET['app_label']
            model_name = request.GET['model_name']
            field_name = request.GET['field_name']
        except KeyError as e:
            raise PermissionDenied from e
        # Retrieve objects from parameters.
        try:
            source_model = apps.get_model(app_label, model_name)
        except LookupError as e:
            raise PermissionDenied from e
        try:
            source_field = source_model._meta.get_field(field_name)
        except FieldDoesNotExist as e:
            raise PermissionDenied from e
        try:
            remote_model = getattr(source_field.remote_field, 'model', source_field.model)
        except AttributeError as e:
            raise PermissionDenied from e
        try:
            model_admin = self.admin_site._registry[remote_model]
        except KeyError as e:
            raise PermissionDenied from e
        # Validate suitability of objects.
        if not model_admin.get_search_fields(request):
            raise Http404(
                '%s must have search_fields for the autocomplete_view.' %
                type(model_admin).__qualname__
            )
        # this method add in Django 3.2 and the next line is changed because it breaks all
        to_field_name = getattr(source_field.remote_field, 'field_name', model_admin.model._meta.pk.name)
        if not model_admin.to_field_allowed(request, to_field_name):
            raise PermissionDenied

        return term, model_admin, source_field, to_field_name

    def get_queryset(self):
        """Return queryset based on ModelAdmin.get_search_results()."""
        qs = self.model_admin.get_queryset(self.request)
        # remove Django add in 3.2 and breaks all
        # qs = qs.complex_filter(self.source_field.get_limit_choices_to())
        qs, search_use_distinct = self.model_admin.get_search_results(self.request, qs, self.term)
        if search_use_distinct:
            qs = qs.distinct()
        return qs
