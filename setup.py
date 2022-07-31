
from setuptools import setup, find_packages


setup(
    name='domainpy_aws_cdk',
    version='0.3.0',
    description='aws cdk constructs and stacks for domainpy (DDD, ES, CQRS, BDD and microservices)',
    author='Brian Estrada',
    author_email='brianseg014@gmail.com',
    packages=find_packages(),
    license='MIT',
    url='https://github.com/mymamachef/domainpy_aws_cdk',
    keywords=['domainpy', 'aws', 'cdk', 'ddd', 'event sourcing', 'CQRS'],
    install_requires=[
        "aws-cdk-lib==2.31.1",
        "constructs>=10.0.0,<11.0.0",
        "docker==5.0.3",
    ]
)
