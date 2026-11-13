from django.urls import path

from .views import RatingsUploadView

urlpatterns = [
    path("upload/", RatingsUploadView.as_view(), name="ratings-upload"),
]