from django.urls import include, path
from . import views


urlpatterns = [
    path('__debug__/', include('debug_toolbar.urls')),
    path('', views.dashboard, name='Mysurvey'),

]

url_for_htmx = [
    
]

urlpatterns += url_for_htmx 