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
import landgrab.utils as lg_utils

def game_history(HttpRequest):
    try:
        game = int(HttpRequest.GET.get('game','nope'))
    except ValueError:
        return render_to_response('lg_game_history.html',{'message':'welcome!'})
    
    auth_helper = lg_utils.AuthHelper(HttpRequest.session)

    game_helper = lg_utils.GameHelper(auth_helper.key, game)
    if not game_helper.details:
        return render_to_response('lg_game_history.html',{'message':"could not find game {0}".format(game)})

    log_helper = lg_utils.LogHelper(auth_helper.key, game)
    logs_to_fetch = set(lg_utils.troop_delta_log_types)
    if not game_helper.details.capitols:
        logs_to_fetch.remove(9)
    if not game_helper.details.teamGame:
        logs_to_fetch.remove(13)
    history = defaultdict(lambda : defaultdict(int))
    try:
        for log_type in logs_to_fetch:
            for log_data in log_helper.get_troop_delta_by_type(log_type):
                for player, change in log_data['data']:
                    history[int(log_data['turn'])][player] += change
    except TypeError:
        return render_to_response('lg_game_history.html',{'message':log_data}) 
      
    players = sorted(list((p['nickname'].split(' (')[0] for p in game_helper.details.players)))
    totals = dict(zip(history.keys(), (dict(zip(players, [0]*len(players))) for _ in history.keys())))
    graph_data = dict(zip(players, [[]]*len(players)))
    for turn, changes in history.iteritems():
        for player in players:
            if turn != 0:
                totals[turn][player] = totals[last_turn][player] + changes.get(player, 0)
            else:
                totals[turn][player] = changes.get(player, 0)
        last_turn = turn
    for conquer in log_helper.get_conquers():
        if totals[conquer['turn']][conquer['players'][1]] != 0:
            for turn in history.keys():
                if turn >= conquer['turn']:
                    totals[turn][conquer['players'][1]] = 0
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
   
    auth_helper = lg_utils.AuthHelper(HttpRequest.session)
    log_helper = lg_utils.LogHelper(auth_helper.key, game)
    
    kills = [
        (
            k[0].split(' (')[0], 
            k[1].split(' (')[0]
        ) for k in (
            l['data'].split(': has conquered ') for l in log_helper.get_logs_by_type(11)
        )
    ]
    nicks = {
            n[1].split(' from ')[0]:n[0][18:]
        for n in (
            l.split(' as ') for l in filter_logs(log_helper.get_logs_by_type(1), 1, 'Attempting to add') 
        )
    }
    attacks = []
    for a in log_helper.get_logs_by_type(8):
        s = a['data'].split(':')
        attacks.append(dict(
            attacker=[s[0][:s[0].find(' (') if s[0].find(' (') != -1 else None],int(s[3].split(',')[0][5:])],
            defender=[s[1][10:s[1].find(' (') if s[1].find(' (') != -1 else s[1].find(' from')],int(s[3].split(',')[1][5:])]
        ))
    

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

