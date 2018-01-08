
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


CONFIG_STACK_NAME_ = 'scd-config'
STACK_NAME_ = 'scd'
IAM_STACK_ = 'iam-stack'

STACK_TEMPLATE_PATH_ = {
    CONFIG_STACK_NAME_ : config_stack_template_path(),
    STACK_NAME_ : root_stack_template_path(),
    IAM_STACK_ : config_file('users_and_roles.yml')
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


def create_change_set(cloud_client, stack_name, parameters=[]):
    print('Creating change set for ' + stack_name)
    template_path = STACK_TEMPLATE_PATH_[stack_name]
    with open(template_path, 'r') as f:
        stack_template = f.read()

    response = cloud_client.create_change_set(
        StackName=stack_name,
        TemplateBody=stack_template,
        Capabilities=['CAPABILITY_NAMED_IAM'],
        ChangeSetName=stack_name+'-CHANGESET',
        ChangeSetType='CREATE',
        Parameters=parameters
    )

    change_set_arn = response['Id']


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

    package_dst = os.path.join(root_dir(), 'build', 'python_package.zip')
    create_package(srcs, package_dst, excludes)
    return package_dst


def main():
    cloud_client = boto3.client('cloudformation')
    try:
        response = cloud_client.describe_stacks(StackName=CONFIG_STACK_NAME_)
        config_desc = next(iter(response['Stacks']), None)
    except botocore.exceptions.ClientError:
        config_desc = None

    if config_desc is None:
        print('Creating config stack')
        config_desc = create_stack(cloud_client, CONFIG_STACK_NAME_)

    bucket_name = find_in_outputs(config_desc, 'ConfigS3BucketName')

    s3_client = boto3.client('s3')
    iam_template_version = upload_config_file(s3_client, bucket_name, 'users_and_roles.yml')
    stellar_api_template_version = upload_config_file(s3_client, bucket_name, 'stellar_api.yml')
    
    python_package = create_python_lambda_package()
    python_package_version = upload_file(s3_client, bucket_name, python_package, 'lambda_package.zip')

    # create_change_set(cloud_client, STACK_NAME_)

main()
