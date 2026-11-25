from django.urls import path
from . import views
urlpatterns=[path('',views.inbox,name='news_inbox'),path('read/',views.inbox_read,name='news_inbox_read'),
    path('review/<int:pk>/',views.match_review,name='news_match_review'),
    path('issues/<int:pk>/articles/',views.issue_articles,name='news_issue_articles')]
