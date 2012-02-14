import suds
from suds.client import Client
import re

troop_delta_log_types = set((1,2,8,12,13))
attack_re = '(?P<attacker>[\\w\\s]+)[()[\\]\\w\\s]*: Attacked (?P<defender>[\\w\\s]+)[()[\\]\\w\\s]* from [\\w\\s]+ to [\\w\\s]+, result: atk\\[[\\d,]+\\], def\\[[\\d,]+\\] : atk (?P<lost>-\\d+), def (?P<killed>-\\d+)'
assigned_re = "^[\w\s]+assigned to ([\w\s+]+)"
chown_re = "([\\w\\s]+)[\\w\\s\\[\\]()]* changed ownership of [\\w\\s]+ to ([\\w\\s]+)"

def filter_troop_delta(log):
    """ returns a list of tuples in the format
    (str(player), int(troop_change))
    for a given log """
    log_type = log["type"]
    log_string = log["data"]
    if log_type == 1:
        player = re.findall(assigned_re, log_string)
        if player:
            return [(player[0].strip(), 1)]
        return player
    elif log_type == 2:    
        player = log_string.split(':')[0].split('(')[0]
        armies = sum(int(n) for n in re.findall("(\d+)<BR>",log_string))
        return [(player.strip(), armies)]
    elif log_type == 8:
        m = re.match(attack_re, log_string)
        if m:
            significant_data = []
            if int(m.group('lost')) != 0:
                significant_data += [(m.group('attacker').strip(), int(m.group('lost')))]
            if int(m.group('killed')) != 0:
                significant_data += [(m.group('defender').strip(), int(m.group('killed')))]
            return significant_data
        else:
            return [("ALERT!!!", log_string)]
    elif log_type == 12:
        player = log_string.split(':')[0].split('(')[0]
        armies = sum((int(n) for n in re.findall(': (\d+) armies.',log_string)))
        return [(player.strip(), armies)]
    elif log_type == 13:
        match = re.findall(chown_re, log_string)
        if not match:
            return []
        c_from, c_to = match[0]
        return [(c_from.strip(), -1),(c_to.strip(), +1)]
    return []

class AuthHelper(object):
    api_url = 'http://landgrab.net/landgrab/services/AuthService?wsdl'
    
    def __init__(self):
        import sys
        sys.path += ['constants']
        import constants
        self.client = Client(self.api_url)
        self.key = self.client.service.initiateSession(constants.LG_DEV_KEY)

class LogHelper(object):
    """methods for retrieveing and sorting logs from the landgrab api"""
    api_url = 'http://landgrab.net/landgrab/services/LogService?wsdl'

    def __init__(self, api_key, game_number):
        self.client = Client(self.api_url)
        self.key = api_key
        self.game = game_number

    def get_logs_by_type(self, type):
        """ Returns a list of logs by type
        Can be one of the following:
        1 = Textual entry
        2 = Army placement
        3 = Game over
        4 = Capitol selection
        5 = Leader placement
        6 = March troops after territory conquer
        7 = Fortification
        8 = Attack
        9 = Capitol conquer
        10 = Territory conquer
        11 = Player conquer
        12 = Card trade-in bonus placement
        13 = Territory ownership change
        14 = Player borg or quit game
        15 = Territory selection"""
        try:
            return self.client.service.getLogsByType(self.key, self.game, type)
        except suds.WebFault as e:
            if "Fog of War" in str(e):
                return str(e)
            return "Game number {0} appears to be invalid".format(self.game)

    def get_troop_delta_by_type(self, type):
        """returns all the troop changes in all logs of a given type
        in the formant {'turn':turn number, 'data': [player/change tuples]"""
        if type not in troop_delta_log_types:
            return ['invailid log type']
        logs = self.get_logs_by_type(type)
        if not logs or isinstance(logs, basestring):
            return [logs]
        return map(lambda x: {'turn': x['turnNumber'], 'data': filter_troop_delta(x)}, logs)

    def get_all_logs(self):
        """returns all logs of all types for the game"""
        try:
            return self.client.service.getAllLogs(self.key, self.game)
        except suds.WebFault:
            return False
