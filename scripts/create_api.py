import boto3

import json

def dynamo_api_name():
    return 'DynamoDBOperations'

def dynamo_resource_name():
    return 'DynamoDBManager'

def find_or_create_api(api_client, api_name):
    response = api_client.get_rest_apis()
    api_ids = [e['id'] for e in response['items'] if e['name'] == api_name]

    if len(api_ids) > 1:
        raise Exception('Multiple APIs with same name {}'.format(api_ids))
    if api_ids:
        return api_ids[0]

    response = api_client.create_rest_api(name=api_name)
    return response['id']


def get_root_resource_id(api_client, api_id):
    response = api_client.get_resources(restApiId=api_id)
    return [e['id'] for e in response['items'] if e['path'] == '/'][0]


def find_or_create_resource(api_client, api_id, parent_id, path_part):
    def pred(e):
        try:
            return e['pathPart'] == path_part and e['parentId'] == parent_id
        except KeyError:
            return False

    response = api_client.get_resources(restApiId=api_id)
    resources = [e for e in response['items'] if pred(e)]
    if len(resources) > 1:
        raise Exception('Multiple resources with same path and parent {}'.format(resource_ids))
    if resources:
        return resources[0]

    return api_client.create_resource(
            restApiId=api_id,
            parentId=parent_id,
            pathPart=path_part)


def build_permission_arn(acct_id, api_id, stage, resource, method):
    arn_format = 'arn:aws:execute-api:{region}:{acct_id}:{api_id}/{stage}/{method}/{resource}'
    return arn_format.format(
            region='us-east-1',
            acct_id=acct_id,
            api_id=api_id,
            stage=stage,
            method=method,
            resource=resource)


def add_invoke_permission(lambda_client, source_arn, func_name, statement_id):
    func_policy_raw = lambda_client.get_policy(FunctionName=func_name)
    func_policy = json.loads(func_policy_raw['Policy'])
    statements = func_policy['Statement']

    def action_name():
        return 'lambda:InvokeFunction'

    permission_statement = [e for e in statements if e['Sid'] == statement_id]
    if not permission_statement:
        response = lambda_client.add_permission(
            FunctionName=func_name,
            StatementId=statement_id,
            Action=action_name(),
            Principal='apigateway.amazonaws.com',
            SourceArn=source_arn)
        return response['Statement']
    
    statement = permission_statement[0]
    if statement['Action'] != action_name() or statement['Condition']['ArnLike']['AWS:SourceArn'] != source_arn:
        raise Exception('Statement does not match expectations {}'.format(statement))

    return statement


def main():
    api_client = boto3.client('apigateway')
    account_id = boto3.client('sts').get_caller_identity().get('Account')
    
    api_id = find_or_create_api(api_client, dynamo_api_name())
    print('API ID {}'.format(api_id))

    root_id = get_root_resource_id(api_client, api_id)
    resource = find_or_create_resource(api_client, api_id, root_id, dynamo_resource_name())
    resource_id = resource['id']
    print('Resource ID {}'.format(resource_id))

    try:
        resource['resourceMethods']['POST']
        post_method = api_client.get_method(
                restApiId=api_id,
                resourceId=resource_id,
                httpMethod='POST')
    except KeyError:
        post_method = api_client.put_method(
                restApiId=api_id,
                resourceId=resource_id,
                httpMethod='POST',
                authorizationType='NONE')
    print('POST method created')

    if 'methodResponses' not in post_method or '200' not in post_method['methodResponses']:
        api_client.put_method_response(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='POST',
            statusCode='200',
            responseModels= {'application/json':'Empty'})
    print('POST method response configured')
    
    try:
        post_method_integration = post_method['methodIntegration']
    except KeyError:
        uri_format = 'arn:aws:apigateway:{region}:lambda:path/2015-03-31/functions/arn:aws:lambda:{region}:{acct_id}:function:{func_name}/invocations'
        func_uri = uri_format.format(region='us-east-1', acct_id=account_id, func_name='DynamoOverHttp')
        post_method_integration = api_client.put_integration(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='POST',
            type='AWS',
            integrationHttpMethod='POST',
            uri=func_uri)
    print('POST integration URI {}'.format(post_method_integration['uri']))

    try:
        post_method_integration['integrationResponses']['200']
    except KeyError:
        api_client.put_integration_response(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='POST',
            statusCode='200',
            responseTemplates= {'application/json':''})
    print('POST integration response')

    response = api_client.create_deployment(
            restApiId=api_id,
            stageName='prod')
    print('Deployment ID {}'.format(response['id']))

    lambda_client = boto3.client('lambda') 
    
    test_arn = build_permission_arn(account_id, api_id, stage='*', resource=dynamo_resource_name(), method='POST')
    response = add_invoke_permission(lambda_client, test_arn, 'DynamoOverHttp', 'apigateway-test-2')
    print('Add permission {}'.format(response['Sid']))

    prod_arn = build_permission_arn(account_id, api_id, stage='prod', resource=dynamo_resource_name(), method='POST')
    response = add_invoke_permission(lambda_client, test_arn, 'DynamoOverHttp', 'apigateway-prod-2')
    print('Add permission {}'.format(response['Sid']))

    test_data = {'key1':'value1','key2':'value2'}
    test_request = json.dumps({'operation':'echo', 'payload':test_data})
    test_response = api_client.test_invoke_method(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='POST',
            pathWithQueryString='',
            body=test_request)
    response_data = json.loads(test_response['body'])
    if test_data != response_data:
        raise Exception('Function test invoke failed : expected {0} actual {1}'.format(test_data, response_data))
    print('Test invoke success')


main()




