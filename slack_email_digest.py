#!/usr/bin/env python

import os
import slacker
import yaml
import time
import re
import datetime
import smtplib
from email.mime.text import MIMEText

def send_digest(conf, channel, address, digest):
    print('Sending digest: #%s -> %s' % (channel, address))

    msg = MIMEText(digest, _charset='utf-8')
    msg['From'] = conf['mail']['fromAddress']
    msg['To'] = address
    msg['Subject'] = 'Slack digest for #%s [%s]' % (
        channel, datetime.datetime.now().strftime('%Y-%m-%d'))
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

def get_digests(slack, channels, users, oldest, latest):
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
            for reaction in m.get('reactions', []):
                digest += '%s : %s\n' % (reaction['name'], ', '.join(map(users.get, reaction['users'])))
            digest += '----\n'
        digests[name] = digest
    return digests

def get_conf(params):
    conf = yaml.load(params)
    if 'slack' not in conf or 'mail' not in conf or 'channels' not in conf:
        print('Error: bad configuration, need "channels", "slack" and "mail" properties.')
        return -1
    if 'catchall' in conf['channels'] and not isinstance(conf['channels']['catchall'], str):
        print('Error: catchall must have one email address.')
        return -1
    if 'blacklist' not in conf['channels'] or not conf['channels']['blacklist']:
        conf['channels']['blacklist'] = []
    if 'map' not in conf['channels'] or not conf['channels']['map']:
        conf['channels']['map'] = []
    if type(conf['channels']['map']) is not list:
        print('Error: channels map must be a list.')
        return -1
    if type(conf['channels']['blacklist']) is not list:
        print('Error: channels blacklist must be a list.')
        return -1
    return conf

def timerange(now):
    day = 24 * 3600
    oldest = now - day
    oldest = oldest - (oldest % day)
    latest = now - (now % day) - 1
    return oldest, latest

def format_time(ts):
    return datetime.datetime.utcfromtimestamp(float(ts)).strftime('%Y-%m-%d %H:%M:%S UTC')

def main(params):
    oldest, latest = timerange(time.time())
    print('Digesting messages between %s and %s' % (format_time(oldest), format_time(latest)))

    conf = get_conf(params)
    slack = slacker.Slacker(conf['slack']['token'])
    channels, sendTo = filter_channels(slack, conf)
    users = get_usernames(slack)

    digests = get_digests(slack, channels, users, oldest, latest)
    for channel, digest in digests.items():
        if digest and sendTo[channel]:
            sendto = sendTo[channel]
            send_digest(conf, channel, sendto, digest)

config = os.environ['CONFIGURATION'] if 'CONFIGURATION' in os.environ else open('configuration.yaml')
main(config)
