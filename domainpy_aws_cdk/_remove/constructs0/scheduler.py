import os
import json
import shutil
import tempfile

from aws_cdk import core as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import aws_events as events
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_python as lambda_python
from aws_cdk import aws_stepfunctions as stepfunctions
from aws_cdk import aws_stepfunctions_tasks as tasks



class EventScheduler(cdk.Construct):

    def __init__(
        self, 
        scope: cdk.Construct, 
        construct_id: str, 
        *,
        share_prefix: str
    ) -> None:
        super().__init__(scope, construct_id)

        integration_bus = events.EventBus.from_event_bus_name(
            self, 'integration-bus', cdk.Fn.import_value(f'{share_prefix}IntegrationBusName')
        )

        role = iam.Role(self, 'role',
            assumed_by=iam.ServicePrincipal('apigateway.amazonaws.com')
        )

        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'requirements.txt'), 'w') as file:
                file.write('aws-xray-sdk==2.8.0\n')
            with open(os.path.join(tmp, 'index.py'), 'w') as file:
                file.write(PUBLISHER_CODE)

            publisher_function = lambda_python.PythonFunction(self, 'publisher',
                entry=tmp,
                handler='handler',
                runtime=lambda_.Runtime.PYTHON_3_8,
                environment={
                    'INTEGRATION_EVENT_BUS_NAME': integration_bus.event_bus_name
                },
                tracing=lambda_.Tracing.ACTIVE,
                description="[SCHEDULER] Publish integration event into integration bus"
            )
            integration_bus.grant_put_events_to(publisher_function)

        scheduler = stepfunctions.StateMachine(self, 'scheduler',
            definition=(
                stepfunctions.Wait(self, 'wait',
                    time=stepfunctions.WaitTime.timestamp_path("$.publish_at")
                )
                .next(tasks.LambdaInvoke(self, 'publisher-invoke', lambda_function=publisher_function))
            )
        )
        scheduler.grant_start_execution(role)
        
        cdk.CfnOutput(self, 'state-machine-arn',
            export_name=f'{share_prefix}EventSchedulerArn',
            value=scheduler.state_machine_arn
        )


PUBLISHER_CODE= \
"""
import os
import json
import boto3

from aws_xray_sdk.core import patch_all
patch_all()


INTEGRATION_EVENT_BUS_NAME = os.getenv('INTEGRATION_EVENT_BUS_NAME')

def handler(aws_event, context):
    cloudwatch_events = boto3.client('events')
    
    payload = aws_event['payload']

    cloudwatch_events.put_events(
        Entries=[
            {
                'Source': payload['context'],
                'DetailType': payload['topic'],
                'Detail': json.dumps(payload),
                'EventBusName': INTEGRATION_EVENT_BUS_NAME
            }
        ]
    )
"""