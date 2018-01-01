
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


def insert_stellar_system(db_client, req_json):
    request = json.loads(req_json)
    sector_id = stellar_code.encode_equitorial(request['ra'], request['dec'], request['dist'])
    system_name = generate_system_name(request)
    item = {        
        'sector_id': sector_id,
        'system_name': system_name
    }
    table_client = db_client.Table(TABLE_STELLAR_SYSTEMS_)
    return table_client.put_item(Item=item)


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
    response = operation(boto3.resource('dynamodb'), event['body'])
    
    print("Response: " + response)
    return response
    
    


