from __future__ import annotations

import abc
import typing

import constructs
import aws_cdk as cdk
import aws_cdk.aws_iam as cdk_iam
import aws_cdk.aws_sns as cdk_sns
import aws_cdk.aws_lambda as cdk_lambda
import aws_cdk.aws_sns_subscriptions as cdk_sns_subscriptions
import aws_cdk.aws_lambda_event_sources as cdk_lambda_sources

from .lake import Dam
from .context import Context
from .eventstore import EventStore
from .scheduler import Scheduler
from .constructs.aws_lambda import PackageAssetCode

from .utils import make_unique_resource_name


class Stream(constructs.Construct):
    def __init__(
        self,
        scope: constructs.Construct,
        id: str,
    ) -> None:
        super().__init__(scope, id)

        self.topic = cdk_sns.Topic(
            self,
            "topic",
            content_based_deduplication=False,
            fifo=True,
            topic_name=make_unique_resource_name(
                [s.node.id for s in self.node.scopes] + [".fifo"], "-", "-"
            ),
        )

    def add_stream_source(self, source: StreamSource) -> None:
        source.bind(self)

    def add_stream_subscription(self, subscription: StreamSubcription) -> None:
        subscription.bind(self)


class StreamSource:
    @abc.abstractmethod
    def bind(self, stream: Stream) -> None:
        pass


class StreamSubcription:
    @abc.abstractmethod
    def bind(self, stream: Stream) -> None:
        pass


class EventStoreSource(constructs.Construct, StreamSource):
    def __init__(
        self, scope: constructs.Construct, id: str, eventstore: EventStore
    ) -> None:
        super().__init__(scope, id)
        self.eventstore = eventstore

    def bind(self, stream: Stream) -> None:
        function = cdk_lambda.Function(
            self,
            "function",
            code=PackageAssetCode.from_python_inline(
                EVENT_STORE_STREAM_SOURCE_CODE,
                requirements=["aws-xray-sdk==2.8.0"],
            ),
            handler="index.handler",
            runtime=cdk_lambda.Runtime.PYTHON_3_8,
            environment={"TOPIC_ARN": stream.topic.topic_arn},
            description="[EventStoreSource] Publish events from eventstore into stream",
            timeout=cdk.Duration.minutes(1),
            tracing=cdk_lambda.Tracing.ACTIVE,
        )
        stream.topic.grant_publish(function)

        function.add_event_source(
            cdk_lambda_sources.DynamoEventSource(
                self.eventstore.table,
                starting_position=cdk_lambda.StartingPosition.LATEST,
            )
        )


class SchedulerSource(constructs.Construct, StreamSource):
    def __init__(
        self, scope: constructs.Construct, id: str, scheduler: Scheduler
    ) -> None:
        super().__init__(scope, id)
        self.scheduler = scheduler

    def bind(self, stream: Stream) -> None:
        publisher = cdk_lambda.Function(
            self,
            "publisher",
            code=cdk_lambda.Code.from_inline(SCHEDULER_STREAM_SOURCE_CODE),
            environment={"TOPIC_ARN": stream.topic.topic_arn},
            runtime=cdk_lambda.Runtime.PYTHON_3_8,
            handler="handler",
            description="[SchedulerSource] Put messages from scheduler into stream",
            timeout=cdk.Duration.seconds(30),
            tracing=cdk_lambda.Tracing.ACTIVE,
        )
        publisher.add_event_source(
            cdk_lambda_sources.SqsEventSource(self.scheduler.queue)
        )


class ContextSubscription(StreamSubcription):
    def __init__(
        self,
        context: Context,
        *,
        topics: typing.Optional[typing.Sequence[str]] = None,
    ) -> None:
        self.context = context
        self.topics = topics

    def bind(self, stream: Stream) -> None:
        if self.topics is None:
            filter_policy = None
        else:
            filter_policy = {
                "topic": cdk_sns.SubscriptionFilter.string_filter(
                    allowlist=self.topics
                )
            }

        stream.topic.add_subscription(
            cdk_sns_subscriptions.SqsSubscription(
                self.context.queue,
                raw_message_delivery=True,
                filter_policy=filter_policy,
            )
        )


class DamSubscription(StreamSubcription):
    def __init__(self, dam: Dam) -> None:
        self.dam = dam

    def bind(self, stream: Stream) -> None:
        # Create subscription under consuming construct in case of
        # cross-stack subscription
        if stream.topic.stack != self.dam.firehose.resource.stack:
            self.dam.firehose.resource.stack.add_dependency(stream.topic.stack)

        role = cdk_iam.Role(
            self.dam,
            f"{stream.node.id}Role",
            assumed_by=cdk_iam.ServicePrincipal("sns.amazonaws.com"),
        )
        role.add_to_policy(cdk_iam.PolicyStatement(
            actions=["firehose:PutRecord", "firehose:PutRecordBatch"],
            resources=[self.dam.firehose.delivery_stream_arn]
        ))

        cdk_sns.Subscription(
            self.dam,
            stream.node.id,
            topic=stream.topic,
            endpoint=self.dam.firehose.delivery_stream_arn,
            protocol=cdk_sns.SubscriptionProtocol.FIREHOSE,
            raw_message_delivery=True,
            region=self.regionFromArn(stream.topic),
            subscription_role_arn=role.role_arn
        )

    def regionFromArn(self, topic: cdk_sns.Topic) -> typing.Optional[str]:
        if topic.stack == self.dam.firehose.stack:
            return None
        return cdk.Stack.of(topic).split_arn(topic.topic_arn, cdk.ArnFormat.SLASH_RESOURCE_NAME).region


EVENT_STORE_STREAM_SOURCE_CODE = """
from aws_xray_sdk.core import patch_all
patch_all()

import os
import json
import decimal
import boto3
import boto3.dynamodb.types

TOPIC_ARN = os.getenv("TOPIC_ARN")

DESERIALIZER = boto3.dynamodb.types.TypeDeserializer()

sns = boto3.client("sns")

class JsonEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return float(o)
        return super().default(o)


def handler(aws_event, aws_context):
    for record in aws_event["Records"]:
        if record["eventName"] != "INSERT":
            continue

        new_image = record["dynamodb"]["NewImage"]

        message = {
            "stream_id": DESERIALIZER.deserialize(new_image["stream_id"]),
            "number": DESERIALIZER.deserialize(new_image["number"]),
            "topic": DESERIALIZER.deserialize(new_image["topic"]),
            "version": DESERIALIZER.deserialize(new_image["version"]),
            "timestamp": DESERIALIZER.deserialize(new_image["timestamp"]),
            "event": DESERIALIZER.deserialize(new_image["event"]),
            "is_snapshot": DESERIALIZER.deserialize(new_image["is_snapshot"]),
            "message_id": DESERIALIZER.deserialize(new_image["message_id"]),
            "correlation_id": DESERIALIZER.deserialize(new_image["correlation_id"]),
            "trace_id": DESERIALIZER.deserialize(new_image["trace_id"]),
            "context": DESERIALIZER.deserialize(new_image["context"]),
        }

        sns.publish(
            TopicArn=TOPIC_ARN,
            Message=json.dumps({ "type": "EVENT", "message": message}, cls=JsonEncoder),
            MessageAttributes={
                "topic": {
                    "DataType": "string",
                    "StringValue": message["topic"]
                },
                "context": {
                    "DataType": "string",
                    "StringValue": message["context"]
                }
            },
            MessageDeduplicationId=message["message_id"],
            MessageGroupId=message["trace_id"]
        )
"""


SCHEDULER_STREAM_SOURCE_CODE = """
import os
import json
import boto3

TOPIC_ARN = os.getenv('TOPIC_ARN')

def handler(aws_event, context):
    client = boto3.client('sns')
    
    client.publish(
        TopicArn=INTEGRATION_EVENT_CHANNEL_TOPIC_ARN,
        MessageAttributes={
            'topic': {
                'DataType': 'String',
                'StringValue': aws_event['payload']['topic']
            }
        },
        Message=json.dumps(aws_event['payload'])
    )
"""
