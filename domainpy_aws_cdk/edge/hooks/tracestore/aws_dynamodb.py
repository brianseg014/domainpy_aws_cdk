import typing

from aws_cdk import core as cdk
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as lambda_event_sources

from domainpy_aws_cdk.edge.base import IGateway, ITraceStoreHook
from domainpy_aws_cdk.edge.aws_apigateway import RestApiGateway
from domainpy_aws_cdk.tracestore.aws_dynamodb import DynamoDBTableTraceStore


class DynamoDBTableTraceStoreHook(ITraceStoreHook):

    def __init__(
        self,
        trace_store: DynamoDBTableTraceStore,
        *,
        deploy_resolver: bool = True,
        deploy_trace_resource: bool = True,
        resolver_props: typing.Optional[lambda_.FunctionProps] = None,
        trace_props: typing.Optional[lambda_.FunctionProps] = None
    ) -> None:
        if isinstance(resolver_props, dict):
            resolver_props = lambda_.FunctionProps(**resolver_props)
        if isinstance(trace_props, dict):
            trace_props = lambda_.FunctionProps(**trace_props)

        self.trace_store = trace_store
        self.deploy_resolver = deploy_resolver
        self.deploy_trace_resource = deploy_trace_resource
        self.resolver_props = resolver_props
        self.trace_props = trace_props

    def bind(self, gateway: IGateway) -> None:
        if isinstance(gateway, RestApiGateway):
            self._bind_rest_api_gateway(gateway)
        else:
            raise cdk.ValidationError('gateway-tracestore incompatible')

    def _bind_rest_api_gateway(self, gateway: RestApiGateway) -> None:
        gateway.microservice.add_environment(
            'TRACE_STORE_TABLE_NAME', self.trace_store.table.table_name
        )
        self.trace_store.table.grant_read_write_data(gateway.microservice)

        if self.deploy_resolver:
            _resolver_props = {}
            if self.resolver_props is not None:
                _resolver_props = lambda_.FunctionProps(**self.resolver_props._values)

            self.resolver = lambda_.Function(gateway, 'resolver',
                code=lambda_.Code.from_inline(RESOLVER_CODE),
                runtime=lambda_.Runtime.PYTHON_3_8,
                handler='index.handler',
                memory_size=512,
                layers=[gateway.domainpy_layer],
                tracing=lambda_.Tracing.ACTIVE,
                description='[GATEWAY] Updates trace store with integrations',
                **_resolver_props,
                environment={
                    'TRACE_STORE_TABLE_NAME': self.trace_store.table.table_name,
                    **_resolver_props.get('environment', {})
                }
            )
            self.trace_store.table.grant_read_write_data(self.resolver)
            self.resolver.add_event_source(
                lambda_event_sources.SqsEventSource(gateway.resolver_queue)
            )

        if self.deploy_trace_resource:
            _trace_props = {}
            if self.trace_props is not None:
                _trace_props = self.trace_props._values

            self.trace = lambda_.Function(gateway, 'trace',
                code=lambda_.Code.from_inline(GET_TRACE_RESOLUTION_CODE),
                runtime=lambda_.Runtime.PYTHON_3_8,
                handler='index.handler',
                memory_size=512,
                layers=[gateway.domainpy_layer],
                tracing=lambda_.Tracing.ACTIVE,
                description='[GATEWAY] Returns information abount command trace',
                environment={
                    'TRACE_STORE_TABLE_NAME': self.trace_store.table.table_name,
                    **_trace_props.get('environment', {})
                },
            )
            self.trace_store.table.grant_read_data(self.trace)

            traces_resource = gateway.rest.root.add_resource('_traces')
            trace_item_resource = traces_resource.add_resource('{trace_id}')
            trace_item_resource.add_method('get', apigateway.LambdaIntegration(self.trace))


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
import json

t = time.time()
from aws_xray_sdk.core import patch_all
patch_all()
print('PATCHING', time.time() - t)

from domainpy.infrastructure import DynamoDBTraceStore, record_fromdict

TRACE_STORE_TABLE_NAME = os.getenv('TRACE_STORE_TABLE_NAME')

trace_store = DynamoDBTraceStore(mapper=None, table_name=TRACE_STORE_TABLE_NAME)

def handler(aws_event, context):
    print(aws_event)

    for sqs_record in aws_event['Records']:
        t = time.time()
        integration_dict = json.loads(sqs_record['body'])
        trace_store.resolve_context(
            record_fromdict(integration_dict)
        )
        print('RESOLVE CONTEXT', time.time() - t * 1000)
"""
