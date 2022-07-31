import typing

import constructs
import aws_cdk as cdk
import aws_cdk.aws_s3 as cdk_s3
import aws_cdk.aws_iam as cdk_iam
import aws_cdk.aws_lambda as cdk_lambda
import aws_cdk.aws_kinesisfirehose as cdk_kfirehose

from ..utils import make_unique_resource_name


class S3DeliveryStream(cdk.Resource):
    def __init__(
        self, scope: constructs.Construct, id: str, *, bucket: cdk_s3.Bucket
    ) -> None:
        super().__init__(scope, id)

        role = cdk_iam.Role(
            self,
            "ServiceRole",
            assumed_by=cdk_iam.ServicePrincipal("firehose.amazonaws.com"),
        )
        self.grantPrincipal = role

        transformer = cdk_lambda.Function(
            self,
            "transformer",
            code=cdk_lambda.Code.from_inline(TRANSFORMER_CODE),
            runtime=cdk_lambda.Runtime.PYTHON_3_8,
            handler="index.handler",
            timeout=cdk.Duration.seconds(30),
            description="[DamTransformer] Adds new line at the end of each event",
        )
        transformer.grant_invoke(role)

        self.resource = cdk_kfirehose.CfnDeliveryStream(
            self,
            "delivery_stream",
            delivery_stream_name=make_unique_resource_name(
                [s.node.id for s in self.node.scopes] + ["delivery_stream"],
                "-",
                "-",
            ),
            extended_s3_destination_configuration=cdk_kfirehose.CfnDeliveryStream.ExtendedS3DestinationConfigurationProperty(
                bucket_arn=bucket.bucket_arn,
                buffering_hints=cdk_kfirehose.CfnDeliveryStream.BufferingHintsProperty(
                    interval_in_seconds=60, size_in_m_bs=1
                ),
                role_arn=role.role_arn,
                processing_configuration=cdk_kfirehose.CfnDeliveryStream.ProcessingConfigurationProperty(
                    enabled=True,
                    processors=[
                        cdk_kfirehose.CfnDeliveryStream.ProcessorProperty(
                            type="Lambda",
                            parameters=[
                                cdk_kfirehose.CfnDeliveryStream.ProcessorParameterProperty(
                                    parameter_name="LambdaArn",
                                    parameter_value=transformer.function_arn,
                                )
                            ],
                        )
                    ],
                ),
            ),
        )

        self.delivery_stream_arn = self.resource.attr_arn

    def grant(
        self, grantee: cdk_iam.IGrantable, *actions: str
    ) -> cdk_iam.Grant:
        return cdk_iam.Grant.add_to_principal(
            actions=actions,
            grantee=grantee,
            resource_arns=[self.delivery_stream_arn],
        )

    def grant_put_records(self, grantee: cdk_iam.IGrantable) -> cdk_iam.Grant:
        return self.grant(
            grantee, "firehose:PutRecord", "firehose:PutRecordBatch"
        )


TRANSFORMER_CODE = """
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
