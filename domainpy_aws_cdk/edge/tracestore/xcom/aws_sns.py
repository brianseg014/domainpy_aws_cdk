
from aws_cdk import core as cdk
from aws_cdk import aws_sns_subscriptions as sns_subscriptions

from domainpy_aws_cdk.edge.base import ITraceStoreHook, ITraceStoreSubscription
from domainpy_aws_cdk.edge.tracestore.aws_dynamodb import DynamoDBTableTraceStoreHook
from domainpy_aws_cdk.xcom.aws_sns import SnsTopicChannel


class SnsTopicChannelTraceStoreSubscription(ITraceStoreSubscription):

    def __init__(self, channel: SnsTopicChannel) -> None:
        self.channel = channel

    def bind(self, trace_store_hook: ITraceStoreHook):
        if isinstance(trace_store_hook, DynamoDBTableTraceStoreHook):
            self._bind_dynamodb_table_trace_store_hook(trace_store_hook)
        else:
            raise cdk.ValidationError('tracestoresubscription-channel incompatible')

    def _bind_dynamodb_table_trace_store_hook(self, trace_store_hook: DynamoDBTableTraceStoreHook):
        integration_event_topic = self.channel.topic
        resolver_queue = trace_store_hook.resolver_queue
        resolver_dlq = trace_store_hook.resolver_dlq

        integration_event_topic.add_subscription(
            sns_subscriptions.SqsSubscription(resolver_queue,
                raw_message_delivery=True,
                dead_letter_queue=resolver_dlq
            )
        )
