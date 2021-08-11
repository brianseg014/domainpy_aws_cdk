import os
import json

from aws_cdk import core as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as tevents
from aws_cdk import aws_kinesisfirehose as kfirehose
from aws_cdk import aws_lambda as lamdba_
from aws_cdk import aws_s3 as s3


class EventLake(cdk.Construct):

    def __init__(self, scope: cdk.Construct, id: str) -> None:
        super().__init__(scope, id)

        self.bucket = s3.Bucket(self, 'bucket',
            versioned=False,
            auto_delete_objects=False,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

    @property
    def bucket_arn(self):
        return self.bucket.bucket_arn


class EventBus(cdk.Construct):

    def __init__(
        self, 
        scope: cdk.Construct, 
        construct_id: str, 
        event_lake: EventLake,
        *,
        export_name: str = None
    ) -> None:
        super().__init__(scope, construct_id)

        event_bus = events.EventBus(self, 'bus')
        
        firehose_role = iam.Role(self, 'firehose-role',
            assumed_by=iam.ServicePrincipal("firehose.amazonaws.com")
        )
        firehose_policy = iam.Policy(self, 'firehose-policy',
            statements=[
                iam.PolicyStatement(
                    actions=[
                        's3:AbortMultipartUpload',
                        's3:GetBucketLocation',
                        's3:GetObject',
                        's3:ListBucket',
                        's3:ListBucketMultipartUploads',
                        's3:PutObject'
                    ],
                    resources=[event_lake.bucket_arn, f'{event_lake.bucket_arn}/*']
                )
            ]
        )
        firehose_policy.attach_to_role(firehose_role)

        transformer = lamdba_.Function(self, 'transformer',
            code=lamdba_.Code.from_inline(TRANSFORMER_CODE),
            runtime=lamdba_.Runtime.PYTHON_3_8,
            handler='index.handler',
            timeout=cdk.Duration.minutes(3)
        )
        transformer.grant_invoke(firehose_role)

        firehose = kfirehose.CfnDeliveryStream(self, 'firehose',
            extended_s3_destination_configuration=kfirehose.CfnDeliveryStream.ExtendedS3DestinationConfigurationProperty(
                bucket_arn=event_lake.bucket_arn,
                buffering_hints=kfirehose.CfnDeliveryStream.BufferingHintsProperty(
                    interval_in_seconds=60,
                    size_in_m_bs=1
                ),
                role_arn=firehose_role.role_arn,
                processing_configuration=kfirehose.CfnDeliveryStream.ProcessingConfigurationProperty(
                    enabled=True,
                    processors=[
                        kfirehose.CfnDeliveryStream.ProcessorProperty(
                            type="Lambda",
                            parameters=[
                                kfirehose.CfnDeliveryStream.ProcessorParameterProperty(
                                    parameter_name="LambdaArn",
                                    parameter_value=transformer.function_arn
                                )
                            ]
                        )
                    ]
                )
                
            )
        )
        
        bus_to_firehouse_rule = events.Rule(self, 'bus-to-firehose',
            event_pattern=events.EventPattern(
                version=['0']
            ),
            event_bus=event_bus,
            targets=[
                tevents.KinesisFirehoseStream(
                    firehose, 
                    message=events.RuleTargetInput.from_event_path('$.detail')
                )
            ]
        )

        cdk.CfnOutput(self, 'event_bus_name',
            export_name=export_name,
            value=event_bus.event_bus_name
        )


TRANSFORMER_CODE = \
"""
import base64
def handler(event, context):
    output=[]
    for record in event['records']:
        payload = base64.b64decode(record['data']).decode('utf-8')
        payload = payload + '\\n'
        output_record = {
            'recordId': record['recordId'],
            'result': 'Ok',
            'data': base64.b64encode(payload.encode('utf-8'))
        }
        output.append(output_record)
    return {'records': output}
"""