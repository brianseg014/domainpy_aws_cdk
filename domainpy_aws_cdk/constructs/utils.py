import os
import tempfile
import shutil

from aws_cdk import core as cdk
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_python as lambda_python


class DomainpyLayerVersion(lambda_python.PythonLayerVersion):

    def __init__(self, scope: cdk.Construct, id: str) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree('/Users/brianestrada/Offline/domainpy/domainpy', os.path.join(tmp, 'domainpy'), dirs_exist_ok=True)
            shutil.copyfile('/Users/brianestrada/Offline/domainpy/setup.py', os.path.join(tmp, 'setup.py'))

            with open(os.path.join(tmp, 'requirements.txt'), 'w') as file:
                file.write('aws-xray-sdk==2.8.0\n')
                file.write('typeguard==2.12.1\n')

            super().__init__(
                scope, id, 
                entry=tmp, 
                compatible_runtimes=[
                    lambda_.Runtime.PYTHON_3_7,
                    lambda_.Runtime.PYTHON_3_8
                ]
            )
