import suds
from suds.client import Client
import re
import sys

troop_delta_log_types = set((1,2,8,12,13,15))
name_re = '[\\w\\s_-]+'
borged_re = '[()[\\]\\w\\s,_-]*'
territory_re = '[\\w\\s.-_]+'
attack_re = "(?P<attacker>{0}){1}: Attacked (?P<defender>{0}){1} from {2} to {2}, result: atk\\[[\\d,]+\\], def\\[[\\d,]+\\] : atk (?P<lost>-\\d+), def (?P<killed>-\\d+)".format(name_re, borged_re, territory_re)
assigned_re = "^{0}assigned to ({1})".format(territory_re, name_re)
chown_re = "({0}){1} changed ownership of {2} to ({0})".format(territory_re, borged_re, name_re)

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
            return [("ALERT!!! Parser 8 Failed! Please Notify the Developers.", log_string)]
    elif log_type == 12:
        player = log_string.split(':')[0].split('(')[0]
        armies = sum((int(n) for n in re.findall(': (\d+) armies.',log_string)))
        return [(player.strip(), armies)]
    elif log_type == 13:
        match = re.findall(chown_re, log_string)
        if not match:
            return [("ALERT!!! Parser 13 Failed! Please Notify the Developers.", log_string)]
        c_from, c_to = match[0]
        return [(c_from.strip(), -1),(c_to.strip(), +1)]
    
    player = log_string.split(':')[0].split('(')[0]

    if log_type == 2:
        armies = sum((int(l.split(':')[1]) for l in log['machineData'].split(',')))
        return [(player.strip(), armies)]
    elif log_type == 15:
        armies = log['machineData'].count(',') + 1
        return [(player.strip(), armies)]

    return []

class AuthHelper(object):
    api_url = 'http://landgrab.net/landgrab/services/AuthService?wsdl'
    
    def __init__(self, session = None):
        if session and session.get('session_key'):
            self.key = session.get('session_key')
        else:    
            sys.path += ['constants']
            import constants
            a_client = Client(self.api_url)
            self.key = a_client.service.initiateSession(constants.LG_DEV_KEY)
            if session:
                session['session_key'] = self.key
                session.set_expiry(60*60*2)

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
        if not logs:
            return []
        if isinstance(logs, basestring):
            return [logs]
        return map(lambda x: {'turn': x['turnNumber'], 'data': filter_troop_delta(x)}, logs)

    def get_all_logs(self):
        """returns all logs of all types for the game"""
        try:
            return self.client.service.getAllLogs(self.key, self.game)
        except suds.WebFault:
            return False

class GameHelper(object):
    """methods for retrieveing and sorting game data from the landgrab api"""
    api_url = 'http://landgrab.net/landgrab/services/GameListService?wsdl'

    def __init__(self, api_key):
        self.client = Client(self.api_url)
        self.key = api_key

    def details(self, game_number):
        return self.client.service.getGameDetails(self.key, game_number)


