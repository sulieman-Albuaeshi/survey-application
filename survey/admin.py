from django.contrib import admin
from .models import Survey, CustomUser, Response


admin.site.register(Survey)
admin.site.register(CustomUser)
admin.site.register(Response)

