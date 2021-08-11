from __future__ import annotations

import os
import enum
import shutil
import tempfile
import typing

from aws_cdk import core as cdk
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_sns as sns
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_python as lambda_python


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


class MessageType(enum.Enum):
    APPLICATION_COMMAND = "ApplicationCommand"
    INTEGRATION_EVENT = "IntegrationEvent"


class Definition(typing.TypedDict, total=False):
    attribute_name: str
    attribute_type: str


class Publisher(cdk.Construct):

    def __init__(
        self, 
        scope: cdk.Construct, 
        construct_id: str,
        *,
        name: str,
        message_type: MessageType,
        structs: typing.Sequence[typing.Tuple[str, typing.Sequence[Definition]]],
        attributes: typing.Sequence[Definition],
        resolutions: typing.Sequence[str],
        trace_store: TraceStore,
    ) -> None:
        super().__init__(scope, construct_id)

        self.topic = sns.Topic(self, 'topic')

        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree('/Users/brianestrada/Offline/domainpy/domainpy', os.path.join(tmp, 'domainpy'))
            
            domainpy_layer = lambda_python.PythonLayerVersion(self, 'domainpy',
                entry=tmp,
                compatible_runtimes=[
                    lambda_.Runtime.PYTHON_3_7,
                    lambda_.Runtime.PYTHON_3_8
                ]
            )

        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'app.py'), 'w') as file:
                
                body_lines = []
                for struct_name, struct_definitions in structs:
                    body_lines.extend([
                        f"\tclass {struct_name}({message_type.value}.Struct):",
                    ])
                    body_lines.extend([
                        "\t\t" + d['attribute_name'] + ': ' + d['attribute_type']
                        for d in struct_definitions
                    ])
                    body_lines.extend([""])

                body_lines.extend(
                    '\t' + a['attribute_name'] + ': ' + a['attribute_type']
                    for a in attributes
                )
                
                body = '\n'.join(body_lines)
                file.write(
                    PUBLISHER_CODE.format(
                        name=name,
                        message_type=message_type.value,
                        definition=body,
                        resolutions=resolutions
                    )
                )

            self.function = lambda_python.PythonFunction(self, 'function',
                runtime=lambda_.Runtime.PYTHON_3_8,
                entry=tmp,
                index='app.py',
                handler='handler',
                environment={
                    'TOPIC_ARN': self.topic.topic_arn,
                    'TRACE_STORE_TABLE_NAME': trace_store.table_name
                },
                layers=[domainpy_layer],
                tracing=lambda_.Tracing.ACTIVE
            )

        cdk.CfnOutput(self, 'topic_arn', 
            export_name=name, 
            value=self.topic.topic_arn
        )


class Resolver(cdk.Construct):

    def __init__(self, scope: cdk.Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)


PUBLISHER_CODE = \
"""
import os
import uuid
import typing

from domainpy.application import ApplicationCommand, IntegrationEvent
from domainpy.infrastructure import (
    Mapper, 
    Transcoder, 
    AwsSimpleNotificationServicePublisher, 
    TraceStore, 
    TraceResolution, 
    DynamoDBTraceRecordManager
)

TOPIC_ARN = os.getenv('TOPIC_ARN')
TRACE_STORE_TABLE_NAME = os.getenv('TRACE_STORE_TABLE_NAME')

mapper = Mapper(
    transcoder=Transcoder()
)

@mapper.register
class {name}({message_type}):
{definition}

topic = {name}
resolutions = {resolutions}

def handler(event, context):
    trace_id = str(uuid.uuid4())
    print('Publishing', trace_id, 'with', event)

    message = topic(**event['arguments'])
    publish(trace_id, message, resolutions)

    return {{
        'statusCode': 200,
        'traceId': trace_id
    }}


def publish(
    trace_id: str,
    message: typing.Union[ApplicationCommand, IntegrationEvent],
    resolutions: typing.Tuple[TraceResolution]
) -> None:
    _message = message
    _record = mapper.serialize(message)

    publisher = AwsSimpleNotificationServicePublisher(TOPIC_ARN, mapper)
    publisher.publish(_message)

    trace_store_manager = DynamoDBTraceRecordManager(TRACE_STORE_TABLE_NAME)
    trace_store = TraceStore(trace_store_manager)
    trace_store.store_in_progress(trace_id, _record, resolutions)
"""
