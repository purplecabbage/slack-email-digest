[![Build Status](https://api.travis-ci.com/rabbah/slack-email-digest.svg?branch=master)](https://api.travis-ci.com/rabbah/slack-email-digest.svg?branch=master) 

### Slack to Email digest

This app will connect to Slack, retrieve the available channels and create a daily digest to send to designated email recipients.

### Setup and deployment

You will need a configuration.yaml file to run the app. If running this app through Travis CI you can encrypt the configuration.
```bash
travis login --com
travis encrypt-file configuration.yaml --add
```
