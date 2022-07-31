import typing

import aws_cdk as cdk
import aws_cdk.aws_iam as cdk_iam
import aws_cdk.aws_lambda as cdk_lambda
import aws_cdk.aws_apigateway as cdk_apigateway


class LambdaIntegrationNoPermission(cdk_apigateway.LambdaIntegration):
    """Integrates an AWS Lambda function to an API Gateway method.
    Example::
        # Example automatically generated without compilation. See https://github.com/aws/jsii/issues/826
        handler = lambda_.Function(self, "MyFunction", ...)
        api.add_method("GET", LambdaIntegration(handler))
    """

    def __init__(
        self,
        handler: cdk_lambda.IFunction,
        *,
        allow_test_invoke: typing.Optional[bool] = None,
        proxy: typing.Optional[bool] = None,
        cache_key_parameters: typing.Optional[typing.Sequence[str]] = None,
        cache_namespace: typing.Optional[str] = None,
        connection_type: typing.Optional[cdk_apigateway.ConnectionType] = None,
        content_handling: typing.Optional[
            cdk_apigateway.ContentHandling
        ] = None,
        credentials_passthrough: typing.Optional[bool] = None,
        credentials_role: typing.Optional[cdk_iam.IRole] = None,
        integration_responses: typing.Optional[
            typing.Sequence[cdk_apigateway.IntegrationResponse]
        ] = None,
        passthrough_behavior: typing.Optional[
            cdk_apigateway.PassthroughBehavior
        ] = None,
        request_parameters: typing.Optional[typing.Mapping[str, str]] = None,
        request_templates: typing.Optional[typing.Mapping[str, str]] = None,
        timeout: typing.Optional[cdk.Duration] = None,
        vpc_link: typing.Optional[cdk_apigateway.IVpcLink] = None,
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

    def bind(self, method: cdk_apigateway.Method):
        config = super().bind(method)
        permissions = filter(
            lambda x: isinstance(x, cdk_lambda.CfnPermission),
            method.node.children,
        )
        for permission in permissions:
            method.node.try_remove_child(permission.node.id)
        return config
