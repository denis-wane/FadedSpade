'''
Created on April 15, 2020
@author: denis.r.wane
'''
import sys
import requests
import json
import configparser
import datetime
import boto3
import tempfile

C_NAME_PREFIX = "SERVER_NAME_"
C_DNS_PREFIX = "SERVER_DNS_"
C_PORT_PREFIX = "SERVER_PORT_"

api_pwd = ""
server_list = []
newPlayer = []

# This function reads baseline properties from an ini file
# Properties include - server name, dns and port for each
# server running as well as the API Password 
def getConfigs ():
    config = configparser.ConfigParser()
    server = []

    session = boto3.Session(region_name='us-east-1')
    bucket = session.resource('s3').Bucket('fadedspade-configs')
    temporary_file = tempfile.NamedTemporaryFile()
    bucket.download_file('properties.ini', temporary_file.name)
 
    config.read_file(open(temporary_file.name))
    temporary_file.close()

    #config.read('./properties.ini')
    server_count = int(config.get("Servers","SERVER_COUNT"))

    for i in range(1,server_count + 1):
        server_name = C_NAME_PREFIX + str(i)
        server_dns = C_DNS_PREFIX + str(i)
        server_port = C_PORT_PREFIX + str(i)

        server_name = config.get("Servers",server_name)
        server_dns = config.get("Servers",server_dns)
        server_port = config.get("Servers",server_port)
        server = [server_name, server_dns, server_port]
        # Create a list of all server properties
        server_list.append(server)
    
    password = config.get("Admin","PASSWORD")
    
    return password

# This function creates a list of newly created player accounts by 
# comparing first login date to the current date.  Configured
# to label anything less than 1 day old a "New" Account (set in the
# compare_date variable).  Returns a list of new players.
def getNewPlayers(dns, port, pwd):
    current = datetime.datetime.now()
    # Adjust to change the definition of a new account
    compare_date = current - datetime.timedelta(days=1)

    query_string = "https://"+ dns + ":" + port + \
        "/api?Password=" + pwd + "&JSON=YES&Command=" +\
        "AccountsList&Player=&Fields=Player,FirstLogin"
    
    resp = requests.get(query_string)
    json_data = json.loads(resp.text)
    firstLoginData = json_data["FirstLogin"]
    userData = json_data["Player"]
    index = 0

    playerList = []

    for login in firstLoginData:
        try:
            login_dtm = datetime.datetime.strptime(login, '%Y-%m-%d %H:%M')
        except:
            e = sys.exc_info()[0]
            #print("Bad Date - " + login + " - " + str(index))
            #likely default date of 0000-00-00 00:00

        if (login_dtm > compare_date):
            playerList.append(userData[index])

        index = index+1
    
    # Return a list of newly created player accounts
    return playerList

# This function gets the full player account details for a
# player / server combination.  Returns the JSON dictionary
# for the player.
def getPlayer(dns, port, pwd, player):
    query_string = "https://" + dns + ":" + port + \
        "/api?Password=" + pwd + "&JSON=YES&Command=" +\
        "AccountsGet&Player=" + player

    resp = requests.get(query_string)
    json_data = json.loads(resp.text)

    return json_data 

# This function adds a new account to the target server for
# each player included in a list of player JSON data.  Errors
# are ignored as some accounts may already exist in the target
# server.
def loadPlayers(dns, port, pwd, to_load):
    base_query_string = "https://" + dns + ":" + port + \
        "/api?Password=" + pwd + "&JSON=YES&Command=" + \
        "AccountsAdd"

    for player in to_load:
        query_string = base_query_string + \
            "&Player=" + player["Player"] + \
            "&Location=" + player["Location"] + \
            "&Email=" + player["Email"] + \
            "&PWHash=" + player["PWHash"] + \
            "&FirstLogin=" + player["FirstLogin"] + \
            "&Note=Automated-Entry"

        try:
            resp = requests.get(query_string)
        except:
            e = sys.exc_info()[0]
            print("<p>Error: %s</p>" % e)


def lambda_handler(event, context):
    try:
        api_pwd = getConfigs()

        # Loop through all servers from properties file
        for server in server_list:
            server_name = server[0]
            dns = server[1]
            port = server[2]

            # Get New Players from the first server
            newPlayer = getNewPlayers(dns, port, api_pwd)
            print(str(len(newPlayer)) + " new players from Server: " + server_name)

            to_load = []

            # Loop through each new player
            for player in newPlayer:
                # Get Player details from current server
                player_json = getPlayer(dns, port, api_pwd, player)
                to_load.append(player_json)

            # Loop through all servers
            for target_server in server_list:
                target_name = target_server[0]

                # No need to add the player to the server they came from
                if server_name == target_name:
                   continue
                else:
                    target_dns = target_server[1]
                    target_port = target_server[2]
                    # Add the new players to each other server
                    loadPlayers(target_dns, target_port, api_pwd, to_load)

    except:
        e = sys.exc_info()[0]
        print("<p>Error: %s</p>" % e)

    return {
        'statusCode': 200,
        'body': json.dumps('Completed Successfully!')
    }
