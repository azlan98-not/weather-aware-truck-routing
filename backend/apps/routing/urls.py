from django.urls import path

from apps.routing import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("routes/analyze/", views.analyze, name="routes-analyze"),
    path("routes/heatmap/", views.heatmap, name="routes-heatmap"),
]
