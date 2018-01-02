
import decimal
import json

import boto3

import stellar_code.stellar_code as stellar_code


TABLE_STELLAR_SYSTEMS_ = 'stellar_systems'
TABLE_STELLAR_SECTORS_ = 'stellar_sectors'
TABLE_SYSTEM_SEARCHES_ = 'system_searches'


def generate_system_name(req):
    if 'proper' in req:
        return req['proper']
    if 'gl' in req:
        return req['gl']
    if 'hip' in req:
        return 'HIP ' + req['hip']
    return 'HYG ' + req['hyg']


def insert_stellar_system(db_client, request):
    sector_id = stellar_code.encode_equitorial(request['ra'], request['dec'], request['dist'])
    system_name = generate_system_name(request)
    item = {        
        'sector_id': {'S': sector_id},
        'system_name': {'S': system_name}
    }
    return db_client.put_item(
            TableName=TABLE_STELLAR_SYSTEMS_,
            Item=item,
            ReturnConsumedCapacity='TOTAL')


def route_event(resource_path, http_method):
    operations = {
        '/stellar/code' : { 'POST' : insert_stellar_system}
    }

    if resource_path not in operations:
        raise ValueError('Unsupported path "{}"'.format(resource_path))

    resource = operations[resource_path]
    if http_method not in resource:
        raise ValueError('{0} not supported on "{1}"'.format(http_method, resource))

    return resource[http_method]


def handler(event, context):

    print("Received event: " + json.dumps(event, indent=2))

    operation = route_event(event['resource'], event['httpMethod'])
    response = operation(boto3.client('dynamodb'), json.loads(event['body']))
    response_json = json.dumps(response, indent=2)

    print("Response: " + response_json)
    return {
        'statusCode': 200,
        'headers': {},
        'isBase64Encoded': False,
        'body': response_json
    }
    
    


