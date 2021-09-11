import os
import typing
import tempfile
import shutil

from aws_cdk import core as cdk
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_iam as iam
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


class LambdaIntegrationNoPermission(apigateway.LambdaIntegration):
    '''Integrates an AWS Lambda function to an API Gateway method.

    Example::

        # Example automatically generated without compilation. See https://github.com/aws/jsii/issues/826
        handler = lambda_.Function(self, "MyFunction", ...)
        api.add_method("GET", LambdaIntegration(handler))
    '''

    def __init__(
        self,
        handler: lambda_.IFunction,
        *,
        allow_test_invoke: typing.Optional[bool] = None,
        proxy: typing.Optional[bool] = None,
        cache_key_parameters: typing.Optional[typing.Sequence[str]] = None,
        cache_namespace: typing.Optional[str] = None,
        connection_type: typing.Optional[apigateway.ConnectionType] = None,
        content_handling: typing.Optional[apigateway.ContentHandling] = None,
        credentials_passthrough: typing.Optional[bool] = None,
        credentials_role: typing.Optional[iam.IRole] = None,
        integration_responses: typing.Optional[typing.Sequence[apigateway.IntegrationResponse]] = None,
        passthrough_behavior: typing.Optional[apigateway.PassthroughBehavior] = None,
        request_parameters: typing.Optional[typing.Mapping[str, str]] = None,
        request_templates: typing.Optional[typing.Mapping[str, str]] = None,
        timeout: typing.Optional[cdk.Duration] = None,
        vpc_link: typing.Optional[apigateway.IVpcLink] = None,
    ) -> None:
        super().__init__(
            handler,
            allow_test_invoke=allow_test_invoke,
            proxy=proxy,
            cache_key_parameters=cache_key_parameters,
            cache_namespace=cache_namespace,
            connection_type=connection_type,
            content_handling=content_handling,
            credentials_passthrough=credentials_passthrough,
            credentials_role=credentials_role,
            integration_responses=integration_responses,
            passthrough_behavior=passthrough_behavior,
            request_parameters=request_parameters,
            request_templates=request_templates,
            timeout=timeout,
            vpc_link=vpc_link,
        )

    def bind(self, method: apigateway.Method):
        config = super().bind(method)
        permissions = filter(
            lambda x: isinstance(x, lambda_.CfnPermission), method.node.children
        )
        for permission in permissions:
            method.node.try_remove_child(permission.node.id)
        return config
