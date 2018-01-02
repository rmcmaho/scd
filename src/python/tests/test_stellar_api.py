import json

import stellar_code_function as scf

import boto3
import botocore.stub
from botocore.stub import Stubber

def test_route_event():
    operation = scf.route_event('/stellar/code', 'POST')
    assert operation == scf.insert_stellar_system

def test_insert_stellar_system():
    db_client = boto3.client('dynamodb')
    request = {'ra': 0, 'dec': 0, 'dist': 0, 'proper':'TEST_STAR'}
    response = {
        'ConsumedCapacity': {
            'CapacityUnits': 1,
            'TableName': 'TEST_TABLE'
        },
        'ResponseMetadata': {
            'RequestId': 'abc123',
            'HTTPStatusCode': 200,
            'HostId': 'abc123'
        }
    }
    expected_params = {
        'TableName': botocore.stub.ANY,
        'Item': botocore.stub.ANY,
        'ReturnConsumedCapacity': botocore.stub.ANY
    }
    with Stubber(db_client) as db_stubber:
        db_stubber.add_response('put_item', response, expected_params)
        assert scf.insert_stellar_system(db_client, request) == response
    
