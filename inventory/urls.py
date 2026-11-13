from django.urls import path
from . import views
urlpatterns=[
    path('',views.index,name='inventory_index'),
    path('customers/<int:pk>/',views.detail,name='inventory_detail'),
    path('customers/<int:pk>/walkthrough-operations/',views.walkthrough_operations,name='inventory_walkthrough_operations'),
    path('customers/<int:pk>/items/new/',views.item_new,name='inventory_item_new'),
    path('items/<int:pk>/edit/',views.item_edit,name='inventory_item_edit'),
    path('customers/<int:pk>/connections/new/',views.connection_new,name='inventory_connection_new'),
    path('connections/<int:pk>/edit/',views.connection_edit,name='inventory_connection_edit'),
    path('customers/<int:pk>/followups/new/',views.followup_new,name='inventory_followup_new'),
    path('followups/<int:pk>/edit/',views.followup_edit,name='inventory_followup_edit'),
    path('engagements/<int:pk>/intake-followups/',views.intake_followups,name='inventory_intake_followups'),
]
