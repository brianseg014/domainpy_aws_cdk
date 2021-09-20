import os
import tempfile

from aws_cdk import core as cdk
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_python as lambda_python

from domainpy_aws_cdk.scheduler.base import ISchedulerChannel, IntegrationEventChannelHookBase
from domainpy_aws_cdk.scheduler.aws_sfn import StepFunctionSchedulerChannel
from domainpy_aws_cdk.xcom.aws_sns import SnsTopicChannel


class SnsTopicIntegrationEventChannelHook(IntegrationEventChannelHookBase):
    
    def __init__(
        self, 
        integration_channel: SnsTopicChannel
    ) -> None:
        self.integration_channel = integration_channel
        self._function = None

    @property
    def function(self):
        if self._function is None:
            raise cdk.ValidationError('should call bind first')
        return self._function

    def bind(self, scheduler: ISchedulerChannel):
        if isinstance(scheduler, StepFunctionSchedulerChannel):
            self._bind_step_function_scheduler(scheduler)
        else:
            raise cdk.ValidationResult('scheduler-integrationchannel incompatible')

    def _bind_step_function_scheduler(self, scheduler: StepFunctionSchedulerChannel) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'requirements.txt'), 'w') as file:
                file.write('aws-xray-sdk==2.8.0\n')
            with open(os.path.join(tmp, 'index.py'), 'w') as file:
                file.write(PUBLISHER_CODE)

            self._function = lambda_python.PythonFunction(scheduler, 'publisher',
                entry=tmp,
                handler='handler',
                runtime=lambda_.Runtime.PYTHON_3_8,
                environment={
                    'TOPIC_ARN': self.integration_channel.topic.topic_arn
                },
                tracing=lambda_.Tracing.ACTIVE,
                description="[SCHEDULER] Publish integration event into integration bus"
            )


PUBLISHER_CODE= \
"""
import os
import json
import boto3

from aws_xray_sdk.core import patch_all
patch_all()


TOPIC_ARN = os.getenv('TOPIC_ARN')

def handler(aws_event, context):
    client = boto3.client('sns')
    
    payload = aws_event['payload']

    trace_id = payload['trace_id']
    context = payload['context']
    topic = payload['topic']
    client.publish(
        TopicArn=TOPIC_ARN,
        MessageGroupId=trace_id,
        MessageDeduplicationId=f'{context}:{topic}:{trace_id}',
        MessageAttributes={
            'context': {
                'type': 'String',
                'value': context
            },
            'topic': {
                'type': 'String',
                'value': topic
            }
        },
        Message=json.dumps(payload)
    )
"""
