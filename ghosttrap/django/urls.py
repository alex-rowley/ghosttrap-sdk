from django.urls import path

from ghosttrap.django import js_report

urlpatterns = [
    path("js/", js_report, name="ghosttrap_js"),
]
