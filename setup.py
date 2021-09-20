
from setuptools import setup, find_packages


setup(
    name='domainpy_aws_cdk',
    version='0.2.0',
    description='aws cdk constructs and stacks for domainpy (DDD, ES, CQRS, BDD and microservices)',
    author='Brian Estrada',
    author_email='brianseg014@gmail.com',
    packages=find_packages(),
    license='MIT',
    url='https://github.com/mymamachef/domainpy_aws_cdk',
    keywords=['domainpy', 'aws', 'cdk', 'ddd', 'event sourcing', 'CQRS'],
    install_requires=[
        'aws-cdk.core==1.123.0',
        'aws-cdk.custom-resources==1.123.0',
        'aws-cdk.aws-dynamodb==1.123.0',
        'aws-cdk.aws-opensearchservice==1.123.0',
        'aws-cdk.aws-events==1.123.0',
        'aws-cdk.aws-events-targets==1.123.0',
        'aws-cdk.aws-lambda==1.123.0',
        'aws-cdk.aws-lambda-python==1.123.0',
        'aws-cdk.aws-lambda-event-sources==1.123.0',
        'aws-cdk.aws-sqs==1.123.0',
        'aws-cdk.aws-sns==1.123.0',
        'aws-cdk.aws-sns-subscriptions==1.123.0',
        'aws-cdk.aws-stepfunctions==1.123.0',
        'aws-cdk.aws-stepfunctions-tasks==1.123.0'
    ]
)
