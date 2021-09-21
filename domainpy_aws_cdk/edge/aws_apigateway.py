import re
import typing
import jsii.errors

from aws_cdk import core as cdk
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_python as lambda_python
from aws_cdk import aws_sqs as sqs

from domainpy_aws_cdk.edge.base import BaseGateway, ITraceStoreHook
from domainpy_aws_cdk.utils import DomainpyLayerVersion, LambdaIntegrationNoPermission


class RestApiMethodProps:
    
    def __init__(
        self,
        *,
        topic: str,
        http_method: str
    ) -> None:
        self.topic = topic
        self.http_method = http_method


class RestApiResourceProps:
    
    def __init__(
        self,
        *,
        resource_path: str,
        methods: typing.Sequence[RestApiMethodProps]
    ) -> None:
        _methods = []
        for m in methods:
            if isinstance(m, dict):
                _methods.append(RestApiMethodProps(**m))
            _methods.append(m)
        methods = _methods

        self.resource_path = resource_path
        self.methods = methods


class RestApiGatewayProps:
    
    def __init__(
        self,
        *,
        resources: typing.Sequence[RestApiResourceProps],
        function_props: lambda_python.PythonFunctionProps,
        rest_api_props: apigateway.RestApiProps,
        message_topic_header_key: str = 'x-message-topic'
    ) -> None:
        self._values: typing.Dict[str, typing.Any] = {
            'resources': resources,
            'function_props': function_props,
            'rest_api_props': rest_api_props,
            'message_topic_header_key': message_topic_header_key
        }

    @property
    def resources(self) -> typing.Sequence[RestApiResourceProps]:
        result = self._values.get('resources')
        return typing.cast(typing.Sequence[RestApiResourceProps], result)

    @property
    def function_props(self) -> lambda_python.PythonFunctionProps:
        result = self._values.get('function_props')
        return typing.cast(lambda_python.PythonFunctionProps, result)

    @property
    def rest_api_props(self) -> str:
        result = self._values.get('rest_api_props')
        return typing.cast(lambda_python.PythonFunctionProps, result)

    @property
    def message_topic_header_key(self) -> str:
        result = self._values.get('message_topic_header_key')
        return typing.cast(lambda_python.PythonFunctionProps, result)


PATH_PARAMETER_PATTERN = re.compile('{(?P<param>\w+)}')

class RestApiGateway(BaseGateway):
    class Import(BaseGateway):
        def __init__(self, scope: cdk.Construct, id: str, domainpy_layer_arn: str, microsrevice_arn: str, restapi_id: str) -> None:
            super().__init__(scope, id)

            self.domainpy_layer = lambda_python.PythonLayerVersion.from_layer_version_arn(domainpy_layer_arn)
            self.microservice = lambda_python.PythonFunction.from_function_arn(self, 'microservice', microsrevice_arn)
            self.rest = apigateway.RestApi.from_rest_api_id(self, 'rest', restapi_id)

    @classmethod
    def bring(self, scope: cdk.Construct, id: str, export_name: str) -> Import:
        domainpy_layer_arn = cdk.Fn.import_value(f'{export_name}DomainpyLayerArn')
        microservice_arn = cdk.Fn.import_value(f'{export_name}MicroserviceArn')
        restapi_id = cdk.Fn.import_value(f'{export_name}RestApiId')

        return RestApiGateway.Import(scope, id, domainpy_layer_arn, microservice_arn, restapi_id)

    def __init__(
        self,
        scope: cdk.Construct,
        id: str,
        *,
        resources: typing.Sequence[RestApiResourceProps],
        microservice_props: typing.Optional[lambda_python.PythonFunctionProps] = None,
        rest_api_props: typing.Optional[apigateway.RestApiProps] = None,
        trace_store_hook: ITraceStoreHook,
        message_topic_header_key: str = 'x-message-topic',
        export_name: typing.Optional[str] = None
    ):
        super().__init__(scope, id)

        if isinstance(microservice_props, dict):
            microservice_props = lambda_python.PythonFunctionProps(**microservice_props)
        if isinstance(rest_api_props, dict):
            rest_api_props = apigateway.RestApiProps(**rest_api_props)

        self.domainpy_layer = DomainpyLayerVersion(self, 'domainpy')

        _microservice_props = {}
        if microservice_props is not None:
            _microservice_props = microservice_props._values

        self.microservice = lambda_python.PythonFunction(self, 'microservice',
            runtime=lambda_.Runtime.PYTHON_3_8,
            memory_size=512,
            timeout=cdk.Duration.seconds(30),
            tracing=lambda_.Tracing.ACTIVE,
            description='[GATEWAY] Entry point for requests',
            **_microservice_props,
            layers=[self.domainpy_layer, *_microservice_props.get('layers', [])]
        )

        _rest_api_props = {}
        if rest_api_props is not None:
            _rest_api_props = rest_api_props._values

        if 'rest_api_name' not in _rest_api_props:
            _rest_api_props['rest_api_name'] = export_name

        self.rest = apigateway.RestApi(self, 'rest',
            deploy_options=apigateway.StageOptions(
                stage_name='api',
                tracing_enabled=True
            ),
            **_rest_api_props
        )

        # Due to policy length limits and with each endpoint grows
        # the policy size, single permission is used 
        self.microservice.add_permission('rest-invoke-permission',
            principal=iam.ServicePrincipal('apigateway.amazonaws.com'),
            action='lambda:InvokeFunction',
            source_arn=self.rest.arn_for_execute_api()
        )

        _resources: typing.Dict[str, apigateway.Resource] = {}
        for resource_props in resources:
            resource_path_parts = resource_props.resource_path.split('/')

            path_parameters = []

            resource = self.rest.root
            for i,resource_path_part in enumerate(resource_path_parts):
                resource_key = '/'.join(resource_path_parts[:i + 1])
                if resource_key in _resources:
                    resource = _resources[resource_key]
                else:
                    resource = _resources[resource_key] = resource.add_resource(resource_path_part)

                path_parameter_matcher = PATH_PARAMETER_PATTERN.match(resource_path_part)
                if path_parameter_matcher is not None:
                    path_parameters.append(path_parameter_matcher.group('param'))

            for method_props in resource_props.methods:
                try:
                    resource.add_method(
                        method_props.http_method,
                        LambdaIntegrationNoPermission(
                            self.microservice,
                            proxy=False,
                            passthrough_behavior=apigateway.PassthroughBehavior.WHEN_NO_TEMPLATES,
                            request_templates={
                                'application/json': VTL_REQUEST_TEMPLATE.format(
                                    message_topic_header_key=message_topic_header_key,
                                    message_topic=method_props.topic
                                )
                            },
                            integration_responses=[
                                apigateway.IntegrationResponse(
                                    status_code='200'
                                )
                            ]
                        ),
                        method_responses=[
                            apigateway.MethodResponse(status_code='200')
                        ]
                    )
                except jsii.errors.JSIIError as error:
                    raise jsii.errors.JSIIError(
                        f'path {resource_props.resource_path} '
                        f'method {method_props.http_method}: {str(error)}'
                    ) from error

        self.resolver_dlq = sqs.Queue(self, 'resolver-dlq')
        self.resolver_queue = sqs.Queue(self, 'resolver-queue',
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=self.resolver_dlq
            )
        )

        trace_store_hook.bind(self)

        if export_name is not None:
            cdk.CfnOutput(self, 'domainpy-layer-arn',
                export_name=f'{export_name}DomainpyLayerArn',
                value=self.domainpy_layer.layer_version_arn
            )
            cdk.CfnOutput(self, 'microservice-arn',
                export_name=f'{export_name}MicroserviceArn',
                value=self.microservice.function_arn
            )
            cdk.CfnOutput(self, 'restapi-id',
                export_name=f'{export_name}RestApiId',
                value=self.rest.rest_api_id
            )


VTL_REQUEST_TEMPLATE = """
{{
    "resource": "$context.resourcePath",
    "path": "$context.path",
    "httpMethod": "$context.httpMethod",
    "headers": {{
        "{message_topic_header_key}": "{message_topic}"
        #if($input.params().header.size() > 0),#end
        #foreach($param in $input.params().header.keySet())
        "$param": "$input.params().header.get($param)"
        #if($foreach.hasNext),#end
        #end
    }},
    "queryStringParameters": {{
        #foreach($param in $input.params().querystring.keySet())
        "$param": "$input.params().querystring.get($param)"
        #if($foreach.hasNext),#end
        #end
    }},
    "pathParameters": {{
        #foreach($param in $input.params().path.keySet())
        "$param": "$input.params().path.get($param)"
        #if($foreach.hasNext),#end
        #end
    }},
    "parameters": $input.json('$'),
    "body": "$util.escapeJavaScript($input.body)"
}}
"""
