import json

from aws_cdk import core as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_events as events
from aws_cdk import aws_lambda as lambda_
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

        rest = apigateway.RestApi(self, 'rest',
            rest_api_name=f'{share_prefix}EventScheduler',
            deploy_options=apigateway.StageOptions(
                stage_name='api',
                tracing_enabled=True
            )
        )

        publisher_function = lambda_.Function(self, 'publisher',
            code=lambda_.Code.from_inline(PUBLISHER_CODE),
            handler='index.handler',
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
                    time=stepfunctions.WaitTime.timestamp_path("$.publish_on")
                )
                .next(tasks.LambdaInvoke(self, 'publisher-invoke', lambda_function=publisher_function))
            )
        )
        scheduler.grant_start_execution(role)
        
        schedule_resource = rest.root.add_resource('schedule')
        schedule_resource.add_method(
            'post', 
            apigateway.AwsIntegration(
                service='states',
                action='StartExecution',
                options=apigateway.IntegrationOptions(
                    credentials_role=role,
                    request_templates={
                        'application/json': json.dumps({
                            'stateMachineArn': scheduler.state_machine_arn,
                            'input': "$util.escapeJavaScript($input.json('$'))"
                        })
                    },
                    passthrough_behavior=apigateway.PassthroughBehavior.NEVER,
                    integration_responses=[
                        apigateway.IntegrationResponse(
                            selection_pattern='200',
                            status_code='200',
                            response_templates={
                                'application/json': "$input.json('$.payload')"
                            }
                        )
                    ]
                )
            ),
            method_responses=[
                apigateway.MethodResponse(status_code='200')
            ]
        )

        cdk.CfnOutput(self, 'url',
            export_name=f'{share_prefix}EventSchedulerUrl',
            value=rest.url
        )


PUBLISHER_CODE= \
"""
import os
import json
import boto3


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