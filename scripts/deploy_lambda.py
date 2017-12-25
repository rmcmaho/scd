#!/usr/bin/env python

import boto3
import botocore.exceptions
import zipfile

import os
import logging
import sys

def logger():
    return logging.getLogger(__name__)

def setup_logger():
    log = logger()
    log.setLevel(logging.INFO)
    if not log.hasHandlers():
        log.addHandler(logging.StreamHandler(sys.stdout))

setup_logger()


def root_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def bin_dir():
    return os.path.join(root_dir(), 'build')


def lambda_dir():
    return os.path.join(root_dir(), 'src', 'lambda')


class LambdaConfig(object):
    def __init__(
            self, name, package_files, handler_func,
            handler_module=None, runtime="python3.6",
            role_name='lambda-dynamodb-execution-role'
        ):
        self._name = name
        self._package_files = package_files
        self._handler_func = handler_func

        self._handler_module = handler_module
        self._runtime = runtime
        self._role_name = role_name

        if not self._handler_module:
            self._handler_module = os.path.splitext(package_files[0])[0]

    def package_path(self):
        return os.path.join(bin_dir(), '{}.zip'.format(self._name))

    def build_package(self):
        logger().info('Building archive {}'.format(self.package_path()))
        with zipfile.ZipFile(self.package_path(), 'w') as package:
            for f in self._package_files:
                logger().info('Adding {}'.format(f))
                package.write(os.path.join(lambda_dir(), f), arcname=f)

    @property
    def name(self):
        return self._name

    @property
    def handler(self):
        return '{0}.{1}'.format(self._handler_module, self._handler_func)

    @property
    def runtime(self):
        return self._runtime

    @property
    def code(self):
        code_dict = {}
        with open(self.package_path(), 'rb') as f:
            code_dict['ZipFile'] = f.read()
        return code_dict
            
    @property
    def role_name(self):
        return self._role_name


def lambda_configs():
    return [ LambdaConfig('DynamoOverHttp', ['dynamo_over_http.py'], 'handler') ]


def function_exists(lambda_client, config):
    try:
        lambda_client.get_function_configuration(FunctionName=config.name)
        return True
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] != 'ResourceNotFoundException':
            raise e
        return False


def publish_lambda(lambda_client, iam_client, config):
    logger().info('Deploying function {}'.format(config.name))

    config.build_package()
    
    role = iam_client.get_role(RoleName=config.role_name)
    arn = role['Role']['Arn']

    if not function_exists(lambda_client, config):
        logger().info('Creating new function {}'.format(config.name))
        return lambda_client.create_function(
                FunctionName=config.name,
                Runtime=config.runtime,
                Handler=config.handler,
                Code=config.code,
                Role=arn)
    
    logger().info('Updating existing function {}'.format(config.name))
    config_response = lambda_client.update_function_configuration(
            FunctionName=config.name,
            Runtime=config.runtime,
            Handler=config.handler,
            Role=arn)
    code_response = lambda_client.update_function_code(
            FunctionName=config.name,
            ZipFile=config.code['ZipFile'])
    return {**config_response, **code_response}


def main():
    os.makedirs(bin_dir())
    lambda_client = boto3.client('lambda')
    iam_client = boto3.client('iam')
    for config in lambda_configs():
        publish_lambda(lambda_client, iam_client, config)


main()

