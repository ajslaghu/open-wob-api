#!/usr/bin/env python

import getopt
import os
import json
import sys
import re
from pprint import pprint

import redis
import requests
from sendgrid.helpers.mail import Email, Mail, Personalization, Content
from sendgrid import SendGridAPIClient

REDIS_HOST = 'redis'
REDIS_PORT = 6379
REDIS_DB = 0


def humanize(s):
    return u' '.join([x.capitalize() for x in s.split(u'-')])


class BackendAPI(object):
    URL = 'https://api.openwob.nl/v0'

    def find_by_id(self, gov_slug, id):
        es_query = {
            "filters": {
                "id": {"terms": [id]},
                'collection': {
                    'terms': [humanize(gov_slug)]
                },
                'types': {
                    'terms': ['item']
                }
            },
            "size": 1
        }

        return requests.post(
            '%s/search' % (self.URL,),
            data=json.dumps(es_query)).json()

api = BackendAPI()


def redis_client():
    return redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)


def get_all_email_keys(client):
    return client.keys('emails_*_*')


def sendmail(subject, content, to):
    api_key = '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'
    sg = SendGridAPIClient(apikey=api_key)

    mail = Mail()
    email = Email()
    email.email = 'contact@openstate.eu'
    email.name = 'Openwob'
    mail.from_email = email
    mail.subject = u'Openwob: ' + subject

    personalization = Personalization()
    for address in to:
        personalization.add_to(Email(address))
    mail.add_personalization(personalization)

    mail.add_content(Content("text/plain", content))

    sg.client.mail.send.post(request_body=mail.get())


def perform_mail_run(client, gov_slug, obj_id, default_status):
    print "Getting for %s : %s" % (gov_slug, obj_id,)
    emails = client.hgetall('emails_%s_%s' % (gov_slug, obj_id,))

    wob = api.find_by_id(gov_slug, obj_id)
    w = wob['item'][0]

    if w['status'] == default_status:
        return

    sendmail(
        w['title'],
        u'''De status van het volgende wob verzoek is gewijzigd:

%s

U kunt dit verzoek bekijken via de volgende link:

http://www.openwob.nl/%s/verzoek/%s

''' % (w['title'], gov_slug, obj_id,),
        emails.keys())


def main(argv=None):
    delete_keys = True
    default_status = 'Openstaand'

    try:
        opts, args = getopt.getopt(
            argv[1:], "ds:", ["no-delete-keys", "status"]
        )
    except getopt.error, msg:
        print >>sys.stderr, "send_emails.py [--no-delete-keys] --status <default>"

    # option processing
    for option, value in opts:
        if option in ("-d", "--no-delete-keys"):
            delete_keys = False
        if option in ("-s", "--status"):
            default_status = value

    client = redis_client()
    keys = get_all_email_keys(client)
    for key in keys:
        dummy, gov_slug, obj_id = key.split('_', 2)
        try:
            perform_mail_run(client, gov_slug, obj_id, default_status)
        except Exception as e:
            print >>sys.stderr, e
        if delete_keys:
            client.delete(key)
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
