
import datetime
import json
import os
import re
import sys
import time
import zipfile

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


def build_dir():
    return os.path.join(root_dir(), 'build')

def config_file(file_name):
    return os.path.join(config_dir(), file_name)


def root_stack_template_path():
    return config_file('root_stack.yml')


def config_stack_template_path():
    return config_file('config_stack.yml')


def virtualenv_dir():
    return os.environ['VIRTUAL_ENV']


def virtualenv_site_packages():
    python_dist = "python{0}.{1}".format(sys.version_info.major, sys.version_info.minor)
    return os.path.join(virtualenv_dir(), 'lib', python_dist, 'site-packages')


class EmptyChangeSet(Exception):
    pass


CONFIG_STACK_NAME_ = 'scd-config'
STACK_NAME_ = 'scd'

STACK_TEMPLATE_PATH_ = {
    CONFIG_STACK_NAME_ : config_stack_template_path(),
    STACK_NAME_ : root_stack_template_path(),
    'scd-stellar-api' : config_file('stellar_api.yml')
}


def dump_cf_response(response):
    def datetime_handler(x):
        if isinstance(x, datetime.datetime):
            return x.isoformat()
        raise TypeError("Unknown type")

    return json.dumps(response, indent=2, default=datetime_handler)


def create_change_set(cloud_client, existing_stacks, stack_name, parameters=[]):
    stack_exists = stack_name in existing_stacks
    settings = {
        'StackName' : stack_name,
        'ChangeSetName' : stack_name+'-CHANGESET',
        'Capabilities' : ['CAPABILITY_NAMED_IAM'],
        'ChangeSetType' : 'UPDATE' if stack_exists else 'CREATE',
        'Parameters' : parameters
    }

    with open(STACK_TEMPLATE_PATH_[stack_name], 'r') as f:
        settings['TemplateBody'] = f.read()

    response = cloud_client.create_change_set(**settings)
    info = {
        'Arn' : response['Id'],
        'StackId' : response['StackId'],
        'StackName' : stack_name,
        'Type' : settings['ChangeSetType']
    }

    waiter = cloud_client.get_waiter('change_set_create_complete')
    try:
        waiter.wait(
            ChangeSetName = info['Arn'],
            WaiterConfig = {
                'Delay' : 1,
                'MaxAttempts' : 120
            }
        )
        return info
    except botocore.exceptions.WaiterError as e:
        print('Error while creating change set for ' + stack_name)

    response = cloud_client.describe_change_set(ChangeSetName = info['Arn'])

    if "didn't contain changes" in response['StatusReason']:
        raise EmptyChangeSet(info['Arn'])
    else:
        raise Exception(response['StatusReason'])


def find_in_outputs(stack_desc, key):
    return next(e['OutputValue'] for e in stack_desc['Outputs'] if e['OutputKey'] == key)


def upload_file(s3_client, bucket_name, file_path, file_key=None):
    if not file_key:
        file_key = os.path.basename(file_path)
    print('Uploading {0} --> {1}/{2}'.format(file_path, bucket_name, file_key))
    with open(file_path, 'rb') as f:
        response = s3_client.put_object(
            Body=f,
            Bucket=bucket_name,
            Key=file_key
        )
    return response['VersionId']


def upload_config_file(s3_client, bucket_name, template_name):
    return upload_file(s3_client, bucket_name, config_file(template_name))


def excluded_by(text, excludes=[]):
    return any(e for e in excludes if re.search(e, text))


def package_add_dir(package, src, excludes=[]):
    for root, dirs, files in os.walk(src):
        rel_path = os.path.relpath(root, src)
        dirs[:] = [d for d in dirs if not excluded_by(d, excludes)]
        files[:] = [f for f in files if not excluded_by(f, excludes)]
        for f in files:
            src_file = os.path.join(root, f)
            dst_file = os.path.join(rel_path, f)
            package.write(src_file, arcname=dst_file)


def create_package(src_list, dst, excludes=[]):
    with zipfile.ZipFile(dst, 'w', compression=zipfile.ZIP_DEFLATED) as package:
        for src in src_list:
            print('Zipping ' + src + ' --> ' + dst)
            package_add_dir(package, src, excludes)


def create_python_lambda_package():
    srcs = [
        os.path.join(root_dir(), 'src', 'python'),
        virtualenv_site_packages()
    ]
    excludes = [
        '^awscli',
        '^docutils',
        '^python_dateutils',
        '^boto',
        '^jmespath',
        '^setuptools'
        'dist-info$',
        '\.pyc$',
        '^__pycache__$'
    ]

    package_dst = os.path.join(build_dir(), 'python_package.zip')
    create_package(srcs, package_dst, excludes)
    return package_dst


def get_existing_stacks(cloud_client):
    describe_stacks_resp = cloud_client.describe_stacks()
    existing_stacks = {}
    for stack_summary in describe_stacks_resp['Stacks']:
        existing_stacks[stack_summary['StackName']] = stack_summary
    return existing_stacks


def execute_change_set(cloud_client, change_set_info):
    cloud_client.execute_change_set(
        ChangeSetName = change_set_info['Arn']
    )

    if change_set_info['Type'] == 'CREATE':
        waiter = cloud_client.get_waiter('stack_create_complete')
    else:
        waiter = cloud_client.get_waiter('stack_update_complete')

    try:
        waiter.wait(
            StackName = change_set_info['StackId'],
            WaiterConfig = {
                'Delay' : 5,
                'MaxAttempts' : 300
            }
        )
    except botocore.exceptions.WaiterError as e:
        raise Exception('Failed to execute change set for stack ' + change_set_info['StackName'])

    print("Stack change set complete")


def create_or_update_stack(cloud_client, stack_name, parameters=[]):
    existing_stacks = get_existing_stacks(cloud_client)

    print('Creating change set for stack ' + stack_name)
    try:
        config_change_set = create_change_set(cloud_client, existing_stacks, stack_name, parameters)
    except EmptyChangeSet:
        print('No changes for stack ' + stack_name)
        return

    print('Executing config change set ' + config_change_set['Arn'])
    execute_change_set(cloud_client, config_change_set)


def main():
    # boto3.set_stream_logger(name='botocore')
    # boto3.set_stream_logger(name='boto3')
    
    os.makedirs(build_dir(), exist_ok=True)

    cloud_client = boto3.client('cloudformation')

    # create_or_update_stack(cloud_client, STACK_NAME_)
    # create_or_update_stack(cloud_client, 'scd-stellar-api', [{'ParameterKey' : 'CodeS3BucketName', 'ParameterValue' :'scd-config-us-east-1-test'}])
    # return
    
    # create_or_update_stack(cloud_client, CONFIG_STACK_NAME_)

    existing_stacks = get_existing_stacks(cloud_client)
    bucket_name = find_in_outputs(existing_stacks[CONFIG_STACK_NAME_], 'ConfigS3BucketName')

    s3_client = boto3.client('s3')
    iam_template_version = upload_config_file(s3_client, bucket_name, 'users_and_roles.yml')
    stellar_api_template_version = upload_config_file(s3_client, bucket_name, 'stellar_api.yml')
    
    # python_package = create_python_lambda_package()
    # python_package_version = upload_file(s3_client, bucket_name, python_package, 'lambda_package.zip')
    
    create_or_update_stack(cloud_client, STACK_NAME_)

main()

