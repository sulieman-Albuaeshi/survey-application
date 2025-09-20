from django.urls import include, path
from . import views


urlpatterns = [
    path('__debug__/', include('debug_toolbar.urls')),
    path('', views.index, name='index'),
    path('MySurvey', views.MySurvey, name='MySurvey'),
    path('CreateSurvey', views.CreateSurvey, name='CreateSurvey')
]

url_for_htmx = [
    path('CreateSubFile', views.CreateFile, name='CreateSubFile'),
]

urlpatterns += url_for_htmx 