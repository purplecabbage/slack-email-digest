#!/usr/bin/env python

import argparse
try:
    import argcomplete
except ImportError:
    argcomplete = False
import os
import slacker
import yaml
import time
import re
import sys
import datetime
import smtplib
from email.mime.text import MIMEText

def parse_args_and_config(config):
    parser = argparse.ArgumentParser(description='Slack to Email Digest')
    parser.add_argument('-v', '--verbose', help='verbose output', action='store_true')
    parser.add_argument('-n', '--dryrun', help='verbose output', action='store_true')
    parser.add_argument('-d', '--daysback', help='number of days back to digest', type=int, default=1)

    if argcomplete:
        argcomplete.autocomplete(parser)
    args = parser.parse_args()

    if args.daysback < 1:
        print('Error: daysback must be at least 1.')
        return

    conf = yaml.load(config)
    if 'slack' not in conf or 'mail' not in conf or 'channels' not in conf:
        print('Error: bad configuration, need "channels", "slack" and "mail" properties.')
        return
    if 'catchall' in conf['channels'] and not isinstance(conf['channels']['catchall'], str):
        print('Error: catchall must have one email address.')
        return
    if 'blacklist' not in conf['channels'] or not conf['channels']['blacklist']:
        conf['channels']['blacklist'] = []
    if 'map' not in conf['channels'] or not conf['channels']['map']:
        conf['channels']['map'] = []
    if type(conf['channels']['map']) is not list:
        print('Error: channels map must be a list.')
        return
    if type(conf['channels']['blacklist']) is not list:
        print('Error: channels blacklist must be a list.')
        return

    args.conf = conf
    return args

def send_digest(conf, channel, address, digest, date):
    print('Sending digest: #%s -> %s' % (channel, address))

    msg = MIMEText(digest, _charset='utf-8')
    msg['From'] = conf['mail']['fromAddress']
    msg['To'] = address
    msg['Subject'] = 'Slack digest for #%s [%s]' % (channel, format_day(date))
    server = smtplib.SMTP(conf['mail']['smtp'])
    if conf['mail']['useTLS']:
        server.starttls()
    if 'username' in conf['mail']:
        server.login(conf['mail']['username'], conf['mail']['password'])

    server.sendmail(conf['mail']['fromAddress'], address, msg.as_string())
    server.quit()

# Get a mapping between Slack internal user ids and real names
def get_usernames(slack):
    users = {}
    for user in slack.users.list().body['members']:
        real_name = user.get('real_name', user.get('name'))
        users[user['id']] = real_name
    return users

def filter_channels(slack, conf):
    channels = slack.channels.list().body['channels']
    filtered = {}
    sendTo = {}
    for channel in channels:
        name = channel['name']
        if name in conf['channels']['blacklist']:
            print('IGNORE channel: #%s' % name)
            continue
        if name in conf['channels']['map']:
            sendto = conf['channels']['map'][name]
            print('Digest channel: #%s -> %s' % (name, sendto))
            filtered[name] = channel['id']
            sendTo[name] = sendto
        elif 'catchall' in conf['channels']:
            sendto = conf['channels']['catchall']
            print('Digest channel: #%s -> %s' % (name, sendto))
            filtered[name] = channel['id']
            sendTo[name] = sendto
        else:
            print('IGNORE channel: #%s' % name)
            continue
    return filtered, sendTo

def get_digests(slack, channels, users, oldest, latest, reactions):
    digests = {}

    for name, id in channels.items():
        print('Digesting #%s' % name)
        messages = slack.channels.history(channel=id,
                                          oldest=oldest,
                                          latest=latest,
                                          count=1000)
        digest = ''
        for m in reversed(messages.body['messages']):
            if not m['type'] == 'message' or ('subtype' in m and m['subtype'] == 'bot_message'):
                continue
        
            user = m.get('user')
            if not user:
                user = m['comment']['user']
            sender = users.get(user, '')

            date = format_time(m['ts'])
            # Replace users id mentions with real names
            text = re.sub(r'<@(\w+)>', lambda m: '@' + users[m.group(1)], m['text'])

            digest += '%s - %s: %s\n' % (date, sender, text)
            if reactions:
              for reaction in m.get('reactions', []):
                digest += '%s : %s\n' % (reaction['name'], ', '.join(map(users.get, reaction['users'])))
            digest += '----\n'
        digests[name] = digest
    return digests

def timerange(now, daysback):
    day = daysback * 24 * 3600
    oldest = now - day
    oldest = oldest - (oldest % day)
    latest = now - (now % day) - 1
    return oldest, latest

def format_time(ts):
    return datetime.datetime.utcfromtimestamp(float(ts)).strftime('%Y-%m-%d %H:%M:%S UTC')

def format_day(ts):
    return datetime.datetime.utcfromtimestamp(float(ts)).strftime('%Y-%m-%d')

def main(args):
    now = time.time()
    oldest, latest = timerange(now, args.daysback)
    print('Running on %s' % format_day(now))
    print('Digesting messages between %s and %s' % (format_time(oldest), format_time(latest)))

    reactions = args.conf['slack']['reactions']
    print('Include reactions: %s' % reactions)

    slack = slacker.Slacker(args.conf['slack']['token'])
    channels, sendTo = filter_channels(slack, args.conf)
    users = get_usernames(slack)

    if not args.dryrun:
        digests = get_digests(slack, channels, users, oldest, latest, reactions)
        for channel, digest in digests.items():
            if digest and sendTo[channel]:
                sendto = sendTo[channel]
                send_digest(args.conf, channel, sendto, digest, oldest)

conf = os.environ['CONFIGURATION'] if 'CONFIGURATION' in os.environ else open('configuration.yaml')
args = parse_args_and_config(conf)
if args:
    main(args)
else:
    sys.exit(-1)
