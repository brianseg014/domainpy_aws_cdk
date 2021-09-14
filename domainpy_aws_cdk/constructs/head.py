from __future__ import annotations

import re
import typing
import dataclasses
import jsii.errors

from aws_cdk import core as cdk
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as events_targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_python as lambda_python
from aws_cdk import aws_s3 as s3

from domainpy_aws_cdk.constructs.utils import DomainpyLayerVersion, LambdaIntegrationNoPermission
from domainpy_aws_cdk.constructs.tail import EventBus

class TraceStore(cdk.Construct):

    def __init__(self, scope: cdk.Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)

        self.table = dynamodb.Table(self, 'table',
            partition_key={ 'name': 'trace_id', 'type': dynamodb.AttributeType.STRING },
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST
        )


class MessageLake(cdk.Construct):

    def __init__(self, scope: cdk.Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)

        self.bucket = s3.Bucket(self, 'bucket',
            versioned=False,
            auto_delete_objects=False,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )


class CommandBus(cdk.Construct):

    def __init__(self, scope: cdk.Construct, construct_id: str, *, share_prefix: str):
        super().__init__(scope, construct_id)

        self.bus = events.EventBus(self, 'bus')

        cdk.CfnOutput(self, 'event_bus_name',
            export_name=f'{share_prefix}CommandBusName',
            value=self.bus.event_bus_name
        )


PATH_PARAMETER_PATTERN = re.compile('{(?P<param>\w+)}')


@dataclasses.dataclass
class GatewayMethodProps:
    topic: str
    http_method: str


@dataclasses.dataclass
class GatewayResourceProps:
    resource_path: str
    methods: typing.Tuple[GatewayMethodProps]


class Gateway(cdk.Construct):

    def __init__(
        self, 
        scope: cdk.Construct, 
        construct_id: str, 
        *,
        entry: str,
        resources: typing.Sequence[GatewayResourceProps],
        command_bus: CommandBus,
        trace_store: TraceStore,
        share_prefix: str,
        index: str = 'app',
        handler: str = 'handler',
        message_topic_header_key: str = 'x-message-topic'
    ):
        super().__init__(scope, construct_id)

        integration_bus = events.EventBus.from_event_bus_name(
            self, 'integration-bus', cdk.Fn.import_value(f'{share_prefix}IntegrationBusName')
        )

        domainpy_layer = DomainpyLayerVersion(self, 'domainpy')
        self.gateway_function = lambda_python.PythonFunction(self, 'gateway',
            entry=entry,
            runtime=lambda_.Runtime.PYTHON_3_8,
            index=index,
            handler=handler,
            environment={
                'TRACE_STORE_TABLE_NAME': trace_store.table.table_name,
                'COMMAND_BUS_NAME': command_bus.bus.event_bus_name
            },
            memory_size=512,
            layers=[domainpy_layer],
            timeout=cdk.Duration.seconds(30),
            tracing=lambda_.Tracing.ACTIVE,
            description='[GATEWAY] Entry point for all platform requests'
        )
        trace_store.table.grant_read_write_data(self.gateway_function)
        command_bus.bus.grant_put_events_to(self.gateway_function)

        self.resolver_function = lambda_.Function(self, 'resolver',
            code=lambda_.Code.from_inline(RESOLVER_CODE),
            runtime=lambda_.Runtime.PYTHON_3_8,
            handler='index.handler',
            environment={
                'TRACE_STORE_TABLE_NAME': trace_store.table.table_name
            },
            memory_size=512,
            layers=[domainpy_layer],
            tracing=lambda_.Tracing.ACTIVE,
            description='[GATEWAY] Updates trace store with integrations'
        )
        trace_store.table.grant_read_write_data(self.resolver_function)

        events.Rule(self, 'integartion-rule',
            event_bus=integration_bus,
            event_pattern=events.EventPattern(
                version=['0']
            ),
            targets=[
                events_targets.LambdaFunction(
                    self.resolver_function,
                    event=events.RuleTargetInput.from_event_path('$.detail')
                )
            ]
        )

        self.trace_function = lambda_.Function(self, 'trace',
            code=lambda_.Code.from_inline(GET_TRACE_RESOLUTION_CODE),
            runtime=lambda_.Runtime.PYTHON_3_8,
            handler='index.handler',
            environment={
                'TRACE_STORE_TABLE_NAME': trace_store.table.table_name
            },
            layers=[domainpy_layer],
            tracing=lambda_.Tracing.ACTIVE,
            description='[GATEWAY] Returns information abount command trace'
        )
        trace_store.table.grant_read_data(self.trace_function)

        self.rest = apigateway.RestApi(self, 'rest',
            rest_api_name=f'{share_prefix}Gateway',
            deploy_options=apigateway.StageOptions(
                stage_name='api',
                tracing_enabled=True
            )
        )
        # Due to policy length limits and with each endpoint grows
        # the policy size, single permission is used 
        self.gateway_function.add_permission('rest-invoke-permission',
            principal=iam.ServicePrincipal('apigateway.amazonaws.com'),
            action='lambda:InvokeFunction',
            source_arn=self.rest.arn_for_execute_api()
        )

        traces_resource = self.rest.root.add_resource('_traces')
        trace_item_resource = traces_resource.add_resource('{trace_id}')
        trace_item_resource.add_method('get', apigateway.LambdaIntegration(self.trace_function))

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
                            self.gateway_function,
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

GET_TRACE_RESOLUTION_CODE = """
import os
import json

from domainpy.infrastructure import DynamoDBTraceStore


TRACE_STORE_TABLE_NAME = os.getenv('TRACE_STORE_TABLE_NAME')

trace_store = DynamoDBTraceStore(mapper=None, table_name=TRACE_STORE_TABLE_NAME)

def handler(aws_event, context):
    resource = aws_event['resource']
    http_method = aws_event['httpMethod']

    if resource == '/_traces/{trace_id}':
        if http_method == 'GET':
            return trace_resolution_item_get_handler(aws_event, context)
        else:
            return unhanlded(aws_event, context)
    else:
        return unhanlded(aws_event, context)

def unhanlded(aws_event, context):
    return {
        "isBase64Encoded": False,
        "statusCode": 500,
        "body": 'Unhandled'
    }

def trace_resolution_item_get_handler(aws_event, context):
    path_parameters = aws_event['pathParameters']
    trace_id = path_parameters['trace_id']

    trace_resolution = trace_store.get_resolution(trace_id)

    return {
        "isBase64Encoded": False,
        "statusCode": 200,
        "body": json.dumps({
            'resolution': trace_resolution.resolution,
            'completed': trace_resolution.completed,
            'expected': trace_resolution.expected,
            'errors': trace_resolution.errors
        })
    }
"""

RESOLVER_CODE = """
import os
import time

t = time.time()
from aws_xray_sdk.core import patch_all
patch_all()
print('PATCHING', time.time() - t)

from domainpy.infrastructure import DynamoDBTraceStore, record_fromdict

TRACE_STORE_TABLE_NAME = os.getenv('TRACE_STORE_TABLE_NAME')

trace_store = DynamoDBTraceStore(mapper=None, table_name=TRACE_STORE_TABLE_NAME)

def handler(event, context):
    trace_store.resolve_context(
        record_fromdict(event)
    )
"""