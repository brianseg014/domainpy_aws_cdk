import os
import tempfile

from aws_cdk import core as cdk
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_python as lambda_python
from aws_cdk import aws_lambda_event_sources as lambda_event_sources

from domainpy_aws_cdk.scheduler.base import IScheduleEventChannel, IIntegrationEventChannelHook
from domainpy_aws_cdk.scheduler.aws_sfn import StepFunctionScheduleEventChannel
from domainpy_aws_cdk.xcom.aws_sns import SnsTopicChannel


class SnsTopicIntegrationEventChannelHook(IIntegrationEventChannelHook):
    
    def __init__(
        self, 
        integration_event_channel: SnsTopicChannel
    ) -> None:
        self.integration_event_channel = integration_event_channel

    def bind(self, schedule_event_channel: IScheduleEventChannel) -> None:
        if isinstance(schedule_event_channel, StepFunctionScheduleEventChannel):
            self._bind_step_function_schedule(schedule_event_channel)
        else:
            raise Exception('schedule-integrationchannel incompatible')

    def _bind_step_function_schedule(self, schedule_event_channel: StepFunctionScheduleEventChannel) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'requirements.txt'), 'w') as file:
                file.write('aws-xray-sdk==2.8.0\n')
            with open(os.path.join(tmp, 'index.py'), 'w') as file:
                file.write(PUBLISHER_CODE)

            self.publisher = lambda_python.PythonFunction(schedule_event_channel, 'publisher',
                entry=tmp,
                handler='handler',
                runtime=lambda_.Runtime.PYTHON_3_8,
                environment={
                    'INTEGRATION_EVENT_CHANNEL_TOPIC_ARN': self.integration_event_channel.topic.topic_arn
                },
                tracing=lambda_.Tracing.ACTIVE,
                description="[SCHEDULER] Publish integration event into integration bus"
            )
            
        self.publisher.add_event_source(
            lambda_event_sources.SqsEventSource(schedule_event_channel.queue)
        )


PUBLISHER_CODE= \
"""
import os
import json
import boto3

from aws_xray_sdk.core import patch_all
patch_all()


INTEGRATION_EVENT_CHANNEL_TOPIC_ARN = os.getenv('INTEGRATION_EVENT_CHANNEL_TOPIC_ARN')

def handler(aws_event, context):
    client = boto3.client('sns')
    
    payload = aws_event['payload']

    trace_id = payload['trace_id']
    context = payload['context']
    topic = payload['topic']
    client.publish(
        TopicArn=INTEGRATION_EVENT_CHANNEL_TOPIC_ARN,
        MessageAttributes={
            'subject': {
                'DataType': 'string',
                'StringValue': f'{context}:{topic}'
            },
            'context': {
                'DataType': 'String',
                'StringValue': context
            },
            'topic': {
                'DataType': 'String',
                'StringValue': topic
            }
        },
        Message=json.dumps(payload)
    )
"""
