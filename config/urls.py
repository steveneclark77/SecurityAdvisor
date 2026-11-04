from django.contrib import admin
from django.urls import path
from library import views
urlpatterns = [path('admin/',admin.site.urls),path('',views.dashboard,name='dashboard'),path('baselines/new/',views.create_baseline,name='create_baseline'),path('baselines/<int:pk>/',views.baseline_detail,name='baseline_detail'),path('baselines/<int:pk>/approve/',views.approve_baseline,name='approve_baseline')]
