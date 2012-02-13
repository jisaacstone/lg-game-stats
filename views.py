from django.http import HttpResponse
from django.http import HttpRequest
from django.template import Context, loader
from django.shortcuts import render_to_response
from collections import defaultdict
from suds.client import Client
import suds
import datetime
import urllib
import wsgiref.handlers
import os
import json
import re
import math

import sys
sys.path += ['constants']
import constants

attack_re = '(?P<attacker>[\\w\\s]+)[()[\\]\\w\\s]*: Attacked (?P<defender>[\\w\\s]+)[()[\\]\\w\\s]* from [\\w\\s]+ to [\\w\\s]+, result: atk\\[[\\d,]+\\], def\\[[\\d,]+\\] : atk (?P<lost>-\\d+), def (?P<killed>-\\d+)'
assigned_re = "^[\w\s]+assigned to ([\w\s+]+)"
chown_re = "([\\w\\s]+)[\\w\\s\\[\\]()]* changed ownership of [\\w\\s]+ to ([\\w\\s]+)"

def filter1(log_string):
    player = re.findall(assigned_re, log_string)
    if player:
        return [(player[0].strip(), 1)]
    return player

def filter2(log_string):
    player = log_string.split(':')[0].split('(')[0]
    armies = sum(int(n) for n in re.findall("(\d+)<BR>",log_string))
    return [(player.strip(), armies)]

def filter8(log_string):
    m = re.match(attack_re, log_string)
    if m:
        return [
            (m.group('attacker').strip(), int(m.group('lost'))),
            (m.group('defender').strip(), int(m.group('killed')))
        ]
    else:
        return [("ALERT!!!", log_string)]

def filter12(log_string):
    player = log_string.split(':')[0].split('(')[0]
    armies = sum((int(n) for n in re.findall(': (\d+) armies.',log_string)))
    return [(player.strip(), armies)]

def filter13(log_string):
    match = re.findall(chown_re, log_string)
    if not match:
        return []
    c_from, c_to = match[0]
    return [(c_from.strip(), -1),(c_to.strip(), +1)]

log_filter = {1:filter1, 2:filter2, 8:filter8, 12:filter12, 13:filter13}

def get_all_logs(game):
    url = 'http://landgrab.net/landgrab/services/AuthService?wsdl'
    auth_client = Client(url)
    key = auth_client.service.initiateSession(constants.LG_DEV_KEY)
        
    url = 'http://landgrab.net/landgrab/services/LogService?wsdl'
    log_client = Client(url)
    
    try:
        return log_client.service.getAllLogs(key, game)
    except suds.WebFault:
        return False

def game_history(HttpRequest):
    try:
        game = int(HttpRequest.GET.get('game','nope'))
    except ValueError:
        return render_to_response('lg_game_history.html',{'message':'welcome!'})
    logs = get_all_logs(game)
    if not logs:
        return return_default('Sorry, game number seems to be invalid.')
    history = defaultdict(lambda : defaultdict(int))
      
    for log in logs: 
        if log['type'] in (1,2,8,12,13):
            data = log_filter[log['type']](log['data'])
            for player, change in data:
                history[int(log['turnNumber'])][player] += change

    del logs
    players = set((p for p in history[0].keys()))
    totals = dict(zip(history.keys(), (dict(zip(players, [0]*len(players))) for _ in history.keys())))
    graph_data = dict(zip(players, [[]]*len(players)))
    for turn, changes in history.iteritems():
        for player in players:
            if turn != 0:
                totals[turn][player] = totals[turn-1][player] + changes.get(player, 0)
            else:
                totals[turn][player] = changes.get(player, 0)
    for player in players:
        graph_data[player] = [
            math.log(n+1) if n>0 else 0.5 
            for turn, data in totals.iteritems() 
            for p, n in data.iteritems() 
            if p == player
        ]
    return render_to_response('lg_game_history.html', {'totals': totals, 'players': players, 'graph_data': graph_data}) 

def index(HttpRequest):
    try:
        game = int(HttpRequest.GET.get('game','nope'))
    except ValueError:
        return return_default('')
    def write(length, st):
        s = str(st)
        return '<td>'+s[:length]+'</td>'
    def filter_logs(logs, type, string):
        for log in logs:
            if log["type"] == type and log["data"].find(string) != -1:
                yield log["data"]
    
    all_logs = get_all_logs(game)
    if not all_logs:
        return return_default('Sorry, game number seems to be invalid.')
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
        'message':message,
        'pages':['deathgrid','history']
    })
    return HttpResponse(t.render(c),mimetype="text/html")

