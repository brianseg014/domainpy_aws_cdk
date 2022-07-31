from __future__ import annotations

import constructs
import aws_cdk as cdk
import aws_cdk.aws_s3 as cdk_s3

from .constructs.aws_kinesisfirehose import S3DeliveryStream


class Lake(constructs.Construct):
    def __init__(
        self,
        scope: constructs.Construct,
        id: str
    ) -> None:
        super().__init__(scope, id)

        self.bucket = cdk_s3.Bucket(
            self,
            "bucket",
            versioned=False,
            auto_delete_objects=True,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )


class Dam(constructs.Construct):
    def __init__(
        self,
        scope: constructs.Construct,
        construct_id: str,
        *,
        lake: Lake,
    ) -> None:
        super().__init__(scope, construct_id)

        self.firehose = S3DeliveryStream(
            self, "delivery_stream", bucket=lake.bucket
        )
