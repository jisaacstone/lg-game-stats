from django.http import HttpResponse
from django.http import HttpRequest
from django.template import Context, loader
import cgi
import datetime
import urllib
import wsgiref.handlers
import os
import urllib2
import BeautifulSoup
import json
import pprint
import HTMLParser
import suds

from BeautifulSoup import BeautifulStoneSoup

pp = pprint.PrettyPrinter(indent=4)
valid_feeds = ['so','su','sf','hn']
sites = {'so':'stackoverflow.com','su':'superuser.com','sf':'serverfault.com'}

def index(HttpRequest, app):
    try:
        game = int(HttpRequest.GET.get('game','nope'))
    except ValueError:
        return return_default('')
    print 'working!'
    def write(length, st):
        s = str(st)
        return '<td>'+s[:length]+'</td>'
    def filter_logs(logs, type, string):
        for log in logs:
            if log["type"] == type and log["data"].find(string) != -1:
                yield log["data"]
    from suds.client import Client
    url = 'http://landgrab.net/landgrab/services/AuthService?wsdl'
    auth_client = Client(url)
    key = auth_client.service.initiateSession('ieSi3zD867hF3jnQaeJ8b5fV8M04sZr46Fs')
        
    url = 'http://landgrab.net/landgrab/services/LogService?wsdl'
    log_client = Client(url)
    
    try:
        all_logs = log_client.service.getAllLogs(key, game)
    except suds.WebFault, e:
        return return_default('sorry, game number appears to be invalid')
        
    kills = [
        (
            k[0].split(' (')[0], 
            k[1].split(' (')[0]
        ) for k in [
            l.split(': has conquered ') for l in filter_logs(all_logs, 11, 'conquered')
        ]
    ]
    nicks_raw = [
        (
            n[1].split(' from ')[0],
            n[0][18:]
        ) for n in [
            l.split(' as ') for l in filter_logs(all_logs, 1, 'Attempting to add') 
        ]
    ]
    nicks = dict(
        zip(
            [n[0] for n in nicks_raw],
            [n[1] for n in nicks_raw]
        )
    )
    attacks = []
    for a in filter_logs(all_logs, 8, ' from'):
        s = a.split(':')
        attacks.append(dict(
            attacker=[s[0][:s[0].find(' (') if s[0].find(' (') != -1 else None],int(s[3].split(',')[0][5:])],
            defender=[s[1][10:s[1].find(' (') if s[1].find(' (') != -1 else s[1].find(' from')],int(s[3].split(',')[1][5:])]))
    

    players = list(set([a["defender"][0] for a in attacks]))
    p_len = len(players)
    players = dict(zip(players, [0]*p_len))

    pvp = dict()
    for a in players:
        pvp[a]=dict()
        for d in players:
            pvp[a][d] = 0

    for a in attacks:
        pvp[a["attacker"][0]][a["defender"][0]] -= a["defender"][1]
        players[a["attacker"][0]] -= a["defender"][1]

    response = '<table><tr><td>Player</td><td>Nick</td>' 
    for p,t in sorted(players.items()):
        response += write(12, p)
    response += write(20, 'total kills')+'</tr>'

    for attacker,total in sorted(players.items()):
        response += '<tr>'+write(20, nicks[attacker] if attacker in nicks else attacker)
        response += write(20, attacker)
        for defender,loss in sorted(pvp[attacker].items()):
            if total > 0:
                response += write(20, ('* ' if (attacker, defender) in kills else '')+str((loss*100)/total)+'%')
            else:
                response += write(20,'N/A')
        response += write(20, str(total)+' troops')+'</td>'
    response += '</table>'
    response += '<p>* player killed</p>'
    return return_default(response)
    
def return_default(message):
    t = loader.get_template('lg_grid_default.html')
    c = Context({
        'message':message
    })
    return HttpResponse(t.render(c),mimetype="text/html")

