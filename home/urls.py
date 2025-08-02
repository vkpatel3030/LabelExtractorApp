from django.contrib import admin
from django.urls import path
from home import views
from home.meesho import meeshoindex
from home.amazon import amazonindex
from home.flipkart import flipkartindex
from home.myntra import myntraindex

urlpatterns = [
   path("", views.index, name='home'),
   path("meesho", meeshoindex, name='home-meesho'),
   path("amazon", amazonindex, name='home-amazon'),
   path("flipkart",flipkartindex, name='home-flipkart'),
   path("myntra/", myntraindex, name="myntra_index"),
   ]
