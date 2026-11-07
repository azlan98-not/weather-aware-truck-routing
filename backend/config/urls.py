"""Root URL configuration — versioned API under /api/v1/."""
from django.urls import include, path

urlpatterns = [
    path("api/v1/", include("apps.routing.urls")),
]
