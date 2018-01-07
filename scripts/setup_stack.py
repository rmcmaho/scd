
import datetime
import json
import os
import time

import boto3
import botocore.exceptions

def script_path():
    return os.path.realpath(__file__)


def script_dir():
    return os.path.dirname(script_path())


def root_dir():
    return os.path.abspath(os.path.join(script_dir(), os.pardir))


def config_dir():
    return os.path.join(root_dir(), 'config')


def config_file(file_name):
    return os.path.join(config_dir(), file_name)


def root_stack_template_path():
    return config_file('root_stack.yml')


def config_stack_template_path():
    return config_file('config_stack.yml')


CONFIG_STACK_NAME_ = 'scd-config'
STACK_NAME_ = 'scd'

STACK_TEMPLATE_PATH_ = {
    CONFIG_STACK_NAME_ : config_stack_template_path(),
    STACK_NAME_ : root_stack_template_path()
}


def dump_cf_response(response):
    def datetime_handler(x):
        if isinstance(x, datetime.datetime):
            return x.isoformat()
        raise TypeError("Unknown type")

    return json.dumps(response, indent=2, default=datetime_handler)


def create_stack(cloud_client, stack_name):
    template_path = STACK_TEMPLATE_PATH_[stack_name]
    with open(template_path, 'r') as f:
        stack_template = f.read()

    response = cloud_client.create_stack(
        StackName=stack_name,
        TemplateBody=stack_template,
        Capabilities=['CAPABILITY_IAM']
    )

    stack_id = response['StackId']

    while True:
        time.sleep(1)
        response = cloud_client.describe_stacks(StackName=stack_id)
        stack_list = [stack for stack in response['Stacks'] if stack['StackId'] == stack_id]
        if not stack_list:
            raise Exception("Unknown stack " + stack_id)
        
        stack = stack_list[0]
        if stack['StackStatus'] == 'CREATE_IN_PROGRESS':
            print('Create in progress...')
            continue
        if stack['StackStatus'] != 'CREATE_COMPLETE':
            raise Exception(dump_cf_response(response))
        break

    return stack


def create_change_set(cloud_client, stack_name):
    template_path = STACK_TEMPLATE_PATH_[stack_name]
    with open(template_path, 'r') as f:
        stack_template = f.read()

    response = cloud_client.create_change_set(
        StackName=stack_name,
        TemplateBody=stack_template,
        Capabilities=['CAPABILITY_IAM'],
        ChangeSetName=stack_name+'-CHANGESET',
        ChangeSetType='CREATE'
    )

    change_set_arn = response['Id']


def find_in_outputs(stack_desc, key):
    return next(e['OutputValue'] for e in stack_desc['Outputs'] if e['OutputKey'] == key)


def upload_config_file(s3_client, bucket_name, template_name):
    with open(config_file(template_name), 'rb') as f:
        response = s3_client.put_object(
            Body=f,
            Bucket=bucket_name,
            Key=template_name
        )
    return response['VersionId']


def main():
    cloud_client = boto3.client('cloudformation')
    try:
        response = cloud_client.describe_stacks(StackName=CONFIG_STACK_NAME_)
        config_desc = next(iter(response['Stacks']), None)
    except botocore.exceptions.ClientError:
        config_desc = None

    if config_desc is None:
        config_desc = create_stack(cloud_client, CONFIG_STACK_NAME_)

    print(dump_cf_response(config_desc))

    bucket_name = find_in_outputs(config_desc, 'ConfigS3BucketName')

    s3_client = boto3.client('s3')
    iam_template_version = upload_config_file(s3_client, bucket_name, 'users_and_roles.yml')
    stellar_api_template_version = upload_config_file(s3_client, bucket_name, 'stellar_api.yml')
    
    create_change_set(cloud_client, STACK_NAME_)

main()
