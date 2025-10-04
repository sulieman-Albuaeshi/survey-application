from django.urls import include, path
from . import views

# app_name = "survey" 

urlpatterns = [
    path('__debug__/', include('debug_toolbar.urls')),
    path('Dashboard', views.Index, name='Dashboard'),
    path('Dashboard/<int:page_number>', views.Index, name='Dashboard_Page'),
    # the views need to be Change
    path('CreateSurvey', views.CreateSurvey, name='CreateSurvey'),
    path('responses', views.Responses, name='Responses'),

]

url_for_htmx = [
    path('CreateSubFile', views.CreateFile, name='CreateSubFile'),
    path("surveys/<int:pk>/delete", views.DeleteSurvey, name="DeleteSurvey"),
    # path('SearchSurveys', views.SearchSurveys, name='SearchSurveys'),
]

urlpatterns += url_for_htmx
print(urlpatterns)