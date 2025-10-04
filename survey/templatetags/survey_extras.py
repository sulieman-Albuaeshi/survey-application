from django import template

register = template.Library()

@register.filter
def get_surveys(value):
    """
        Returns the correct list of surveys whether the input is a Paginator page
        or a plain list/queryset.
    """
    # If it's a paginator page object 
    # like page.object_list
    if hasattr(value, "object_list"):
        """
        If the value has an attribute 'object_list', it's likely a Paginator page.
        We return that list of objects.
        """
        return value.object_list
    # If it's already a list or queryset
    return value
