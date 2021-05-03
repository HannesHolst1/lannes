# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from napoleon_connection.napo import refresh_dataset
from django.urls import path, re_path
from app import views

urlpatterns = [

    # The home page
    path('', views.index, name='home'),

    path('dashboard/<str:dashboard>', views.dashboard, name='dashboard'),

    path('createrequest.html', views.createrequest, name='createrequest'),

    path('delete/<str:dashboard>', views.deletedashboard, name='deletedashboard'),

    path('load_tweets/<str:dashboard>', views.load_tweets, name='load_tweets'),

    # refresh data request
    path('refresh/<str:name>', views.refresh, name='refresh'),

    # Matches any html file
    re_path(r'^.*\.*', views.pages, name='pages'),

]
