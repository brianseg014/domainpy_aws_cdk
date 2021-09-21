import typing

from aws_cdk import core as cdk
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as sns_subscriptions

from domainpy_aws_cdk.projector.base import IProjector, IDomainEventChannelSubscription, IChannelHook
from domainpy_aws_cdk.projector.aws_lambda import LambdaProjectorBase
from domainpy_aws_cdk.xcom.aws_sns import SnsTopicChannel


class SnsTopicDomainEventChannelSubscription(IDomainEventChannelSubscription):

    def __init__(
        self,
        channel: SnsTopicChannel,
        topics: typing.Dict[str, typing.Sequence[str]]
    ) -> None:
        self.channel = channel
        self.topics = topics

    def bind(self, projector: IProjector):
        if isinstance(projector, LambdaProjectorBase):
            self._bind_lambda_projector(projector)
        else:
            cdk.ValidationError('contextmap-channel incompatible')

    def _bind_lambda_projector(self, projector: LambdaProjectorBase):
        domain_event_topic = self.channel.topic
        projector_queue = projector.queue
        projector_dlq = projector.dlq

        subjects = [
            f'{context}:{topic}'
            for context,topics in self.topics.items()
            for topic in topics
        ]

        domain_event_topic.add_subscription(
            sns_subscriptions.SqsSubscription(projector_queue,
                raw_message_delivery=True,
                dead_letter_queue=projector_dlq,
                filter_policy={
                    'subject': sns.SubscriptionFilter(conditions=subjects),
                }
            )
        )


class SnsTopicChannelHook(IChannelHook):

    def __init__(
        self,
        channel_name: str,
        channel: SnsTopicChannel
    ) -> None:
        self.channel_name = channel_name
        self.channel = channel

    def bind(self, projector: IProjector):
        if isinstance(projector, LambdaProjectorBase):
            self._bind_lambda_projector(projector)
        else:
            cdk.ValidationError('projector-channel incompatible')

    def _bind_lambda_projector(self, context: LambdaProjectorBase):
        context_function = context.microservice
        channel_topic = self.channel.topic

        context_function.add_environment(f'{self.channel_name}_SERVICE', 'AWS::SNS::Topic')
        context_function.add_environment(f'{self.channel_name}_TOPIC_ARN', channel_topic.topic_arn)
        channel_topic.grant_publish(context_function)
