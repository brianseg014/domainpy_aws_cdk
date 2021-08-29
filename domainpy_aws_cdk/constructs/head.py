from __future__ import annotations

import typing
import dataclasses

from aws_cdk import core as cdk
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as events_targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_sns as sns
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sqs as sqs


class TraceStore(cdk.Construct):

    def __init__(self, scope: cdk.Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)

        self.table = dynamodb.Table(self, 'table',
            partition_key={ 'name': 'trace_id', 'type': dynamodb.AttributeType.STRING },
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST
        )

    @property
    def table_name(self):
        return self.table.table_name

    def grant_read_write_data(self, grantee: iam.IGrantable) -> iam.Grant:
        return self.table.grant_read_write_data(grantee)


class MessageLake(cdk.Construct):

    def __init__(self, scope: cdk.Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)

        self.bucket = s3.Bucket(self, 'bucket',
            versioned=False,
            auto_delete_objects=False,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

    @property
    def bucket_arn(self):
        return self.bucket.bucket_arn

    def grant_write(self, grantee: iam.IGrantable) -> iam.Grant:
        return self.bucket.grant_write(grantee)


class Gateway(cdk.Construct):

    def __init__(
        self, 
        scope: cdk.Construct, 
        construct_id: str, 
        *,
        share_prefix: str
    ) -> None:
        super().__init__(scope, construct_id)

        self.resources: typing.Dict[str, apigateway.Resource] = {}

        self.rest = apigateway.RestApi(self, 'rest',
            rest_api_name=f'{share_prefix}Gateway',
            deploy_options=apigateway.StageOptions(
                stage_name='api',
                tracing_enabled=True
            )
        )

        self.response_model = apigateway.Model(self, f'response-model',
            rest_api=self.rest,
            schema=apigateway.JsonSchema(
                schema=apigateway.JsonSchemaVersion.DRAFT4,
                type=apigateway.JsonSchemaType.OBJECT,
                properties={
                    'traceId': apigateway.JsonSchema(
                        type=apigateway.JsonSchemaType.STRING
                    )
                }
            ),
            content_type='application/json',
            model_name='Response'
        )

        cdk.CfnOutput(self, 'url',
            export_name=f'{share_prefix}GatewayUrl',
            value=self.rest.url
        )

    def add_publisher(self, publisher: Publisher, resource_path: str, method: str) -> None:
        publisher_topic = publisher.definition.topic
        attributes = publisher.definition.attributes
        
        structs = {}
        if isinstance(publisher.definition, ApplicationCommandDefinition):
            structs = { s.struct_name: s.struct_definitions for s in publisher.definition.structs }

        resource_path_parts = resource_path.split('/')

        resource = self.rest.root
        for i,resource_path_part in enumerate(resource_path_parts):
            resource_key = '/'.join(resource_path_parts[:i + 1])
            if resource_key in self.resources:
                resource = self.resources[resource_key]
            else:
                resource = self.resources[resource_key] = resource.add_resource(resource_path_part)

        resource.add_method(
            method,
            apigateway.LambdaIntegration(publisher.function),
            request_models={
                'application/json': apigateway.Model(self, f'{publisher_topic}RequestModel',
                    rest_api=self.rest,
                    schema=apigateway.JsonSchema(
                        schema=apigateway.JsonSchemaVersion.DRAFT4,
                        type=apigateway.JsonSchemaType.OBJECT,
                        properties={
                            a.attribute_name: definition_to_jsonschema(a, structs)
                            for a in attributes
                        }
                    ),
                    content_type='application/json',
                    model_name=publisher_topic
                ),
            },
            method_responses=[
                apigateway.MethodResponse(
                    status_code='200',
                    response_models={
                        'application/json': self.response_model
                    }
                )
            ]
        )


@dataclasses.dataclass(frozen=True)
class Definition:
    attribute_name: str
    attribute_type: str


@dataclasses.dataclass(frozen=True)
class Struct:
    struct_name: str
    struct_definitions: typing.Sequence[Definition]


@dataclasses.dataclass(frozen=True)
class ApplicationCommandDefinition:
    topic: str
    version: int
    structs: typing.Sequence[Struct]
    attributes: typing.Sequence[Definition]
    resolutions: typing.Sequence[str]


@dataclasses.dataclass(frozen=True)
class IntegrationEventDefinition:
    topic: str
    version: int
    context: str
    resolve: str
    error: typing.Optional[str]
    attributes: typing.Sequence[Definition]
    resolutions: typing.Sequence[str]


PythonLineCode = str


class Publisher(cdk.Construct):

    def __init__(
        self, 
        scope: cdk.Construct, 
        construct_id: str,
        *,
        definition: typing.Union[ApplicationCommandDefinition, IntegrationEventDefinition],
        trace_store: TraceStore,
        share_prefix: str,
        domainpy_layer: lambda_.LayerVersion
    ) -> None:
        super().__init__(scope, construct_id)
        self.definition = definition

        self.topic = sns.Topic(self, 'topic')

        self.function = lambda_.Function(self, 'function',
            code=lambda_.Code.from_inline(self._build_publisher_code(definition)),
            runtime=lambda_.Runtime.PYTHON_3_8,
            handler='index.handler',
            environment={
                'PUBLISHER_TOPIC_ARN': self.topic.topic_arn,
                'TRACE_STORE_TABLE_NAME': trace_store.table_name
            },
            layers=[domainpy_layer],
            tracing=lambda_.Tracing.ACTIVE,
            description=f'[GATEWAY] Publish over sns topic the message for {definition.topic}'
        )
        self.topic.grant_publish(self.function)
        trace_store.grant_read_write_data(self.function)

        cdk.CfnOutput(self, 'topic_arn', 
            export_name=f'{share_prefix}{definition.topic}',
            value=self.topic.topic_arn
        )

    def _build_publisher_code(self, definition: typing.Union[ApplicationCommandDefinition, IntegrationEventDefinition]):
        message_definition = '\n'.join(self._build_message_code(definition))
        return PUBLISHER_CODE_TEMPLATE.format(
            message_definition=message_definition,
            message_topic=definition.topic,
            message_resolutions=definition.resolutions
        )

    def _build_message_code(self, definition: typing.Union[ApplicationCommandDefinition, IntegrationEventDefinition]) -> typing.Sequence[PythonLineCode]:
        if isinstance(definition, ApplicationCommandDefinition):
            return self._build_application_command_code(definition)
        else:
            return self._build_integration_event_code(definition)

    def _build_message_definitions_code(self, definitions: typing.Sequence[Definition])  -> typing.Sequence[PythonLineCode]:
        return [
            d.attribute_name + ': ' + d.attribute_type for d in definitions
        ]

    def _build_application_command_struct_code(self, struct: Struct) -> typing.Sequence[PythonLineCode]:
        struct_name = struct.struct_name
        struct_definitions = struct.struct_definitions

        body_lines = []
        body_lines.extend([
            f'class {struct_name}(ApplicationCommand.Struct):'
        ])
        body_lines.extend([
            f'\t{d}'
            for d in self._build_message_definitions_code(struct_definitions)
        ])
        return body_lines

    def _build_application_command_code(self, command: ApplicationCommandDefinition) -> typing.Sequence[PythonLineCode]:
        message_topic = command.topic
        message_version = command.version

        body_lines = []
        body_lines.extend([
            f'class {message_topic}(ApplicationCommand):',
            f'\t__version__: int = {message_version}'
        ])
        
        for struct in command.structs:
            body_lines.extend([''])
            body_lines.extend([
                f'\t{l}'
                for l in self._build_application_command_struct_code(struct)
            ])

        body_lines.extend([''])
        body_lines.extend([
            f'\t{l}'
            for l in self._build_message_definitions_code(command.attributes)
        ])

        return body_lines

    def _build_integration_event_code(self, integration: IntegrationEventDefinition) -> typing.Sequence[PythonLineCode]:
        message_topic = integration.topic
        message_version = integration.version
        message_resolve = integration.resolve
        message_error = integration.error
        message_context = integration.context

        body_lines = []
        body_lines.extend([
            f'class {message_topic}(IntegrationEvent):',
            f'\t__version__: int = {message_version}',
            f'\t__resolve__: str = "{message_resolve}"',
            f'\t__error__: typing.Optional[str] = "{message_error}"',
            f'\t__context__: str = "{message_context}"'
        ])

        body_lines.extend([''])
        body_lines.extend([
            f'\t{l}'
            for l in self._build_message_definitions_code(integration.attributes)
        ])

        return body_lines


class Resolver(cdk.Construct):

    def __init__(
        self, 
        scope: cdk.Construct, 
        construct_id: str, *,
        trace_store: TraceStore, 
        message_lake: MessageLake,
        share_prefix: str,
        domainpy_layer: lambda_.LayerVersion
    ) -> None:
        super().__init__(scope, construct_id)

        integration_bus = events.EventBus.from_event_bus_name(
            self, 'integration-bus', cdk.Fn.import_value(f'{share_prefix}IntegrationBusName')
        )

        self.topic = sns.Topic(self, 'topic')

        function = lambda_.Function(self, 'function',
            code=lambda_.Code.from_inline(RESOLVER_CODE),
            runtime=lambda_.Runtime.PYTHON_3_8,
            handler='index.handler',
            environment={
                'RESOLVER_TOPIC_ARN': self.topic.topic_arn,
                'TRACE_STORE_TABLE_NAME': trace_store.table_name
            },
            layers=[domainpy_layer],
            tracing=lambda_.Tracing.ACTIVE,
            description=f'[GATEWAY] Resolver'
        )
        self.topic.grant_publish(function)
        trace_store.grant_read_write_data(function)

        dlq = sqs.Queue(self, 'resolver-dlq')
        events.Rule(self, 'integartion-rule',
            event_bus=integration_bus,
            event_pattern=events.EventPattern(
                version=['0']
            ),
            targets=[
                events_targets.LambdaFunction(
                    function,
                    event=events.RuleTargetInput.from_event_path('$.detail'),
                    dead_letter_queue=dlq
                )
            ]
        )


def definition_to_jsonschema(
    definition: Definition, 
    structs: typing.Dict[str, typing.Sequence[Definition]]
) -> apigateway.JsonSchema:
    _type = definition.attribute_type
    if _type == 'str':
        return apigateway.JsonSchema(type=apigateway.JsonSchemaType.STRING)

    if _type in ('int', 'float'):
        return apigateway.JsonSchema(type=apigateway.JsonSchemaType.NUMBER)

    if _type == 'bool':
        return apigateway.JsonSchema(type=apigateway.JsonSchemaType.BOOLEAN)

    _matches = ('Tuple', 'List', 'Sequence')
    if any(m in _type for m in _matches):
        return apigateway.JsonSchema(type=apigateway.JsonSchemaType.ARRAY)

    if _type in structs:
        _struct = structs[_type]
        return apigateway.JsonSchema(
            type=apigateway.JsonSchemaType.OBJECT,
            properties={
                a.attribute_name: definition_to_jsonschema(a, structs)
                for a in _struct
            }
        )

    raise TypeError(f'unhandled: {_type}')


PUBLISHER_CODE_TEMPLATE = \
"""
import os
import uuid
import json
import typing
import logging
import datetime

from aws_xray_sdk.core import patch_all
patch_all()

from domainpy.application import (
    ApplicationCommand,
    IntegrationEvent,
    SuccessIntegrationEvent,
    FailureIntegrationEvent
)
from domainpy.infrastructure import (
    record_fromdict,
    MessageType,
    Mapper, 
    Transcoder, 
    AwsSimpleNotificationServicePublisher, 
    TraceStore, 
    TraceResolution, 
    DynamoDBTraceRecordManager
)
from domainpy.utils import Bus

PUBLISHER_TOPIC_ARN = os.getenv('PUBLISHER_TOPIC_ARN')
TRACE_STORE_TABLE_NAME = os.getenv('TRACE_STORE_TABLE_NAME')

# logging.getLogger().setLevel(logging.INFO)

transcoder=Transcoder()
mapper = Mapper(transcoder=transcoder)

@mapper.register
{message_definition}


def handler(event, context):
    trace_id = str(uuid.uuid4())

    payload = json.loads(event['body'])
    if 'trace_id' in payload:
        trace_id = payload.pop('trace_id')

    logging.info('Handle event with trace: %s: %s', trace_id, json.dumps(event))

    try:
        message = transcoder.decode(
            dict(
                timestamp=datetime.datetime.timestamp(datetime.datetime.now()),
                trace_id=trace_id,
                payload=payload
            ), 
            {message_topic}
        )

        publish(trace_id, message, {message_resolutions})
    except Exception as error:
        logging.exception('Mapping error: When handling event: %s', json.dumps(event))
        return {{
            'statusCode': 500,
            'isBase64Encoded': False,
            'body': f'Some error occurred. Contact the system administrator. Message: {message_topic} and Trace: {{trace_id}}'
        }}

    return {{
        'statusCode': 200,
        'headers': {{
            'Content-Type': 'application/json'
        }},
        'isBase64Encoded': False,
        'body': json.dumps({{
            'traceId': trace_id
        }})
    }}


def publish(
    trace_id: str,
    message: typing.Union[ApplicationCommand, IntegrationEvent],
    resolutions: typing.Tuple[TraceResolution]
) -> None:
    _message = message
    _record = mapper.serialize(message)

    publisher = AwsSimpleNotificationServicePublisher(PUBLISHER_TOPIC_ARN, mapper)
    publisher.publish(_message)
    
    trace_store_manager = DynamoDBTraceRecordManager(TRACE_STORE_TABLE_NAME)
    trace_store = TraceStore(trace_store_manager, Bus())
    trace_store.store_in_progress(trace_id, _record, resolutions)
"""

RESOLVER_CODE = \
"""
import os

from domainpy.application import IntegrationEvent
from domainpy.infrastructure import (
    Mapper,
    Transcoder,
    TraceStore,
    DynamoDBTraceRecordManager,
    AwsSimpleNotificationServicePublisher
)
from domainpy.utils import Bus, PublisherSubscriber

from aws_xray_sdk.core import patch_all
patch_all()

RESOLVER_TOPIC_ARN = os.getenv('RESOLVER_TOPIC_ARN')
TRACE_STORE_TABLE_NAME = os.getenv('TRACE_STORE_TABLE_NAME')

mapper = Mapper(
    transcoder=Transcoder()
)

def handler(event, context):
    resolver_bus = Bus()
    resolver_bus.attach(
        PublisherSubscriber(
            AwsSimpleNotificationServicePublisher(
                topic_arn=RESOLVER_TOPIC_ARN,
                mapper=mapper
            )
        )
    )

    trace_store_manager = DynamoDBTraceRecordManager(TRACE_STORE_TABLE_NAME)
    trace_store = TraceStore(trace_store_manager, resolver_bus)

    trace_id = event['trace_id']
    context = event['context']
    resolve = event['resolve']
    if resolve == IntegrationEvent.Resolution.success:
        trace_store.store_context_success(trace_id, context)
    elif resolve == IntegrationEvent.Resolution.failure:
        error = event['error']
        trace_store.store_context_failure(trace_id, context, error)

    return { "done": True }
"""
