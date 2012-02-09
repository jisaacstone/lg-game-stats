from django.conf.urls.defaults import patterns, include, url

urlpatterns = patterns('landgrab.views',
    url(r'^history/?$', 'game_history'),
    url(r'^$', 'index'),
    url(r'^deathgrid/?$', 'index' ),
)

