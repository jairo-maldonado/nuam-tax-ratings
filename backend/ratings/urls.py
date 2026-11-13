from django.urls import path

from .views import RatingsListView, RatingsUploadView

urlpatterns = [
    path("", RatingsListView.as_view(), name="ratings-list"),
    path("upload/", RatingsUploadView.as_view(), name="ratings-upload"),
]