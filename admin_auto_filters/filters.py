from django.apps import apps
from django.contrib.admin.widgets import AutocompleteSelectMultiple as Base
from django import forms
from django.contrib import admin
from django.db.models.fields.related import ForeignObjectRel
from django.db.models.constants import LOOKUP_SEP  # this is '__'
from django.db.models.fields.related_descriptors import ReverseManyToOneDescriptor, ManyToManyDescriptor
from django.forms.widgets import Media, MEDIA_TYPES, media_property
from django.shortcuts import reverse
from django import VERSION as DJANGO_VERSION


class AutocompleteSelect(Base):
    def __init__(self, rel, admin_site, attrs=None, choices=(), using=None, custom_url=None):
        self.custom_url = custom_url
        super().__init__(rel, admin_site, attrs, choices, using)
    
    def get_url(self):
        return self.custom_url if self.custom_url else super().get_url()

    def optgroups(self, name, value, attr=None):
        """Return selected options based on the ModelChoiceIterator."""
        default = (None, [], 0)
        groups = [default]
        has_selected = False
        selected_choices = {
            str(v) for v in value
            if str(v) not in self.choices.field.empty_values
        }
        if not self.is_required and not self.allow_multiple_selected:
            default[1].append(self.create_option(name, '', '', False, 0))
        choices = (
            (obj.pk, self.choices.field.label_from_instance(obj))
            for obj in self.choices.queryset.using(self.db).filter(pk__in=selected_choices)
        )
        for option_value, option_label in choices:
            selected = (
                    str(option_value) in value and
                    (has_selected is False or self.allow_multiple_selected)
            )
            has_selected |= selected
            index = len(default[1])
            subgroup = default[1]
            subgroup.append(self.create_option(name, option_value, option_label, selected_choices, index))
        return groups


class AutocompleteFilter(admin.SimpleListFilter):
    template = 'django-admin-autocomplete-filter/autocomplete-filter.html'
    title = ''
    field_name = ''
    field_pk = 'id'
    use_pk_exact = True
    is_placeholder_title = False
    widget_attrs = {}
    rel_model = None
    parameter_name = None
    form_field = forms.ModelChoiceField
    autocomplete_model = None

    class Media:
        js = (
            'admin/js/jquery.init.js',
            'django-admin-autocomplete-filter/js/autocomplete_filter_qs.js',
        )
        css = {
            'screen': (
                'django-admin-autocomplete-filter/css/autocomplete-fix.css',
            ),
        }

    def __init__(self, request, params, model, model_admin):
        if self.autocomplete_model:
            self.rel_model = apps.get_model(self.autocomplete_model)

        parameter_name = '{}__{}__in'.format(
            self.field_name, self.field_pk)
        params[parameter_name] = ','.join(request.GET.getlist(parameter_name))

        self.parameter_name = '{}__{}__in'.format(
            self.field_name, self.field_pk)
        self.used_parameters = {}

        super().__init__(request, params, model, model_admin)

        field_to_use = self.field_name
        if self.rel_model:
            model = self.rel_model
            field_to_use = self.field_pk

        if DJANGO_VERSION >= (3, 2):
            remote_field = model._meta.get_field(field_to_use)
        else:
            remote_field = model._meta.get_field(field_to_use).remote_field

        widget = AutocompleteSelect(remote_field,
                                    model_admin.admin_site,
                                    custom_url=self.get_autocomplete_url(request, model_admin),)
        form_field = self.get_form_field()
        field = form_field(
            queryset=self.get_queryset_for_field(model, self.field_name),
            widget=widget,
            required=False,
        )

        self._add_media(model_admin, widget)

        attrs = self.widget_attrs.copy()
        attrs['id'] = 'id-%s-dal-filter' % self.parameter_name
        if self.is_placeholder_title:
            # Upper case letter P as dirty hack for bypass django2 widget force placeholder value as empty string ("")
            attrs['data-Placeholder'] = self.title
        self.rendered_widget = field.widget.render(
            name=self.parameter_name,
            value=self.value(),
            attrs=attrs
        )

    def get_queryset_for_field(self, model, name):
        return self.rel_model._meta.default_manager.all()

    def get_form_field(self):
        """Return the type of form field to be used."""
        return self.form_field

    def _add_media(self, model_admin, widget):

        if not hasattr(model_admin, 'Media'):
            model_admin.__class__.Media = type('Media', (object,), dict())
            model_admin.__class__.media = media_property(model_admin.__class__)

        def _get_media(obj):
            return Media(media=getattr(obj, 'Media', None))

        media = _get_media(model_admin) + widget.media + _get_media(AutocompleteFilter) + _get_media(self)

        for name in MEDIA_TYPES:
            setattr(model_admin.Media, name, getattr(media, "_" + name))

    def has_output(self):
        return True

    def lookups(self, request, model_admin):
        return ()

    def value(self):
        if self.used_parameters.get(self.parameter_name):
            return self.used_parameters.get(self.parameter_name).split(',')
        else:
            return []

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(**{self.parameter_name: self.value()})
        else:
            return queryset
    
    def get_autocomplete_url(self, request, model_admin):
        '''
            Hook to specify your custom view for autocomplete,
            instead of default django admin's search_results.
        '''
        return None


def generate_choice_field(label_item):
    """
    Create a ModelChoiceField variant with a modified label_from_instance.
    Note that label_item can be a callable, or a model field, or a model callable.
    """
    class LabelledModelChoiceField(forms.ModelChoiceField):
        def label_from_instance(self, obj):
            if callable(label_item):
                value = label_item(obj)
            elif hasattr(obj, str(label_item)):
                attr = getattr(obj, label_item)
                if callable(attr):
                    value = attr()
                else:
                    value = attr
            else:
                raise ValueError('Invalid label_item specified: %s' % str(label_item))
            return value
    return LabelledModelChoiceField


def _get_rel_model(model, parameter_name):
    """
    A way to calculate the model for a parameter_name that includes LOOKUP_SEP.
    """
    field_names = str(parameter_name).split(LOOKUP_SEP)
    if len(field_names) == 1:
        return None
    else:
        rel_model = model
        for name in field_names[:-1]:
            rel_model = rel_model._meta.get_field(name).related_model
        return rel_model


def AutocompleteFilterFactory(title, base_parameter_name, viewname='', use_pk_exact=False, label_by=str):
    """
    An autocomplete widget filter with a customizable title. Use like this:
        AutocompleteFilterFactory('My title', 'field_name')
        AutocompleteFilterFactory('My title', 'fourth__third__second__first')
    Be sure to include distinct in the model admin get_queryset() if the second form is used.
    Assumes: parameter_name == f'fourth__third__second__{field_name}'
        * title: The title for the filter.
        * base_parameter_name: The field to use for the filter.
        * viewname: The name of the custom AutocompleteJsonView URL to use, if any.
        * use_pk_exact: Whether to use '__pk__exact' in the parameter name when possible.
        * label_by: How to generate the static label for the widget - a callable, the name
          of a model callable, or the name of a model field.
    """

    class NewMetaFilter(type(AutocompleteFilter)):
        """A metaclass for an autogenerated autocomplete filter class."""

        def __new__(cls, name, bases, attrs):
            super_new = super().__new__(cls, name, bases, attrs)
            super_new.use_pk_exact = use_pk_exact
            field_names = str(base_parameter_name).split(LOOKUP_SEP)
            super_new.field_name = field_names[-1]
            super_new.parameter_name = base_parameter_name
            if len(field_names) <= 1 and super_new.use_pk_exact:
                super_new.parameter_name += '__{}__exact'.format(super_new.field_pk)
            return super_new

    class NewFilter(AutocompleteFilter, metaclass=NewMetaFilter):
        """An autogenerated autocomplete filter class."""

        def __init__(self, request, params, model, model_admin):
            self.rel_model = _get_rel_model(model, base_parameter_name)
            self.form_field = generate_choice_field(label_by)
            super().__init__(request, params, model, model_admin)
            self.title = title

        def get_autocomplete_url(self, request, model_admin):
            if viewname == '':
                return super().get_autocomplete_url(request, model_admin)
            else:
                return reverse(viewname)

    return NewFilter
