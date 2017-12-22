from __future__ import print_function

def lambda_handler(event, context):
    records = event['Records']
    for record in records:
        print(record['eventID'])
        print(record['eventName'])
    print('Processed {0}'.format(len(records)))
