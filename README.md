[![Build Status](https://api.travis-ci.com/rabbah/slack-email-digest.svg?branch=master)](https://travis-ci.com/rabbah/slack-email-digest)

### Slack to Email digest

This app will connect to Slack, retrieve the available channels and create a daily digest to send to designated email recipients.

### Usage

The app is executed by running `slack_email_digest.py`. Use `-h` for help and available commands.
Generally, you run the app as follows.
```bash
slack_email_digest.py -c configuration.yaml
```

### Setup and deployment

You will need a configuration.yaml file to run the app. If running this app through Travis CI you can encrypt the configuration.
```bash
travis login --com
travis encrypt-file configuration.yaml --add
```
