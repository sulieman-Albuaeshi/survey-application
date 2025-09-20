from django.urls import include, path
from . import views

app_name = "mysurvey" 

urlpatterns = [
    path('__debug__/', include('debug_toolbar.urls')),
    path('', views.dashboard, name='Dashboard'),

]

url_for_htmx = [
    
]

urlpatterns += url_for_htmx 