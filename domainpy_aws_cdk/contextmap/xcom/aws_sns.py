import typing

from aws_cdk import core as cdk
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as sns_subscriptions

from domainpy_aws_cdk.contextmap.base import (
    IContextMap,
    IDomainEventChannelSubscription
)
from domainpy_aws_cdk.contextmap.aws_lambda import LambdaContextMapBase
from domainpy_aws_cdk.xcom.aws_sns import SnsTopicChannel


class SnsTopicDomainEventChannelSubscription(IDomainEventChannelSubscription):

    def __init__(
        self,
        channel: SnsTopicChannel,
        topics: typing.Dict[str, typing.Sequence[str]]
    ) -> None:
        self.channel = channel
        self.topics = topics

    def bind(self, context_map: IContextMap):
        if isinstance(context_map, LambdaContextMapBase):
            self._bind_lambda_context_map(context_map)
        else:
            cdk.ValidationError('contextmap-channel incompatible')

    def _bind_lambda_context_map(self, context_map: LambdaContextMapBase):
        domain_event_topic = self.channel.topic
        context_map_queue = context_map.queue
        context_map_dlq = context_map.dlq

        subjects = [
            f'{context}:{topic}'
            for context,topics in self.topics.items()
            for topic in topics
        ]

        domain_event_topic.add_subscription(
            sns_subscriptions.SqsSubscription(context_map_queue,
                raw_message_delivery=True,
                dead_letter_queue=context_map_dlq,
                filter_policy={
                    'subject': sns.SubscriptionFilter(conditions=subjects),
                }
            )
        )
