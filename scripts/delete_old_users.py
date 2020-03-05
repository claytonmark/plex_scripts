#/usr/bin/env python3
import requests
import json
from xmltodict import parse
from datetime import datetime, timedelta
from plexapi.myplex import MyPlexAccount, PlexServer
from plexapi.exceptions import NotFound

delete_after_days = 30
dry_run = True # If true, don't remove just list
tautulli_purge = True # If true, remove users from Tautulli database after removing them from share (reccommended)

tautulli_conf = {
    'host': 'localhost',
    'port': 8181,
    'http_root': '',
    'api_key': 'YOUR-TAUTULLI-API-KEY-HERE'
}

plex_conf = {
    'host': 'localhost',
    'protocol': 'http://',
    'port': 32400,
    'plex_token': 'YOUR-PLEX-TOKEN-HERE'
}

omitted_users = ['Local']

def query_tautulli(cmd, args=[]):
    url = 'http://{}:{}{}/api/v2?apikey={}&cmd={}'.format(
        tautulli_conf['host'],
        tautulli_conf['port'],
        tautulli_conf['http_root'],
        tautulli_conf['api_key'],
        cmd
    )

    for arg in args:
        url = url + '&{}={}'.format(str(arg[0]), str(arg[1]))

    response = requests.get(url)

    if response.status_code != 200:
        raise Exception('Tautulli not responing properly, check your config')

    return json.loads(response.text)['response']['data']


def query_plextv(path, args=[], body=None):
    url = 'https://plex.tv/pms{}?X-Plex-Token={}'.format(
        path,
        plex_conf['plex_token']
    )
    
    for arg in args:
        url = url + '&{}={}'.format(str(arg[0]), str(arg[1]))
    if body is None:
        response = requests.get(url)
    else:
        response = requests.post(url, data=body)

    return parse(response.text, process_namespaces=True)

def get_users():
    return query_plextv('/friends/all')['MediaContainer']['User']

def main():
    before_date = datetime.now() - timedelta(days=delete_after_days)

    try:
        machine = PlexServer('{}{}:{}'.format(plex_conf['protocol'], plex_conf['host'], plex_conf['port']), plex_conf['plex_token'])
    except Exception:
        print('unable to connect to plex server for machine_id query')
        return

    try:
        account = MyPlexAccount(token=plex_conf['plex_token'])
        omitted_users.append(account.email)
    except Exception:
        print('unable to connect to plex cloud api for users query')
        return

    for user in get_users():
        if '@email' not in user or user['@email'] == '': # Home user
            continue
        if user['@email'] in omitted_users:
            continue
        try:
            plex_user = account.user(user['@email'])

            user_owned_server = False # storage variable for below
            if '@id' not in user['Server']: # They have multiple servers, see if share one
                user_owned_server = next(filter(lambda x: x['@owned'] == "0", user['Server']), False)

            my_server = next(filter(lambda x: x.TAG == 'Server' and x.machineIdentifier == machine.machineIdentifier, plex_user.servers), None)
            
            if my_server is not None and not user_owned_server: # If my_server is none, they are already removed and don't need interaction
                if my_server.lastSeenAt < before_date:
                    if dry_run:
                        print('Deleted user {} from Plex'.format(user['@title']))
                    else:
                        account.removeFriend(plex_user)

                    if dry_run:
                        print('Removed user {} from Tautulli'.format(user['@title']))
                    else:
                        if tautulli_purge:
                            query_tautulli('delete_user', args=[('user_id', user['@id'])])
                    
                    
        except NotFound:
            if dry_run:
                print('Removed user {} from Tautulli'.format(user['@title']))
            else:
                if tautulli_purge:
                    query_tautulli('delete_user', args=[('user_id', user['@id'])])


if __name__ == "__main__":
    main()