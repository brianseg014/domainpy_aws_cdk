import typing

from aws_cdk import core as cdk
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as sns_subscriptions

from domainpy_aws_cdk.context.base import (
    IContext, 
    ICommandChannelSubscription, 
    IIntegrationEventChannelHook, 
    IDomainEventChannelHook
)
from domainpy_aws_cdk.context.aws_lambda import LambdaContextBase
from domainpy_aws_cdk.xcom.aws_sns import SnsTopicChannel


class SnsTopicCommandChannelSubscription(ICommandChannelSubscription):
    
    def __init__(
        self, 
        channel: SnsTopicChannel,
        topics: typing.Sequence[str]
    ) -> None:
        self.channel = channel
        self.topics = topics

    def bind(self, context: IContext):
        if isinstance(context, LambdaContextBase):
            self._bind_lambda_context(context)
        else:
            raise cdk.ValidationError('context-channel incompatible')

    def _bind_lambda_context(self, context: LambdaContextBase):
        command_topic = self.channel.topic
        context_queue = context.queue
        context_dlq = context.dlq

        command_topic.add_subscription(
            sns_subscriptions.SqsSubscription(context_queue,
                raw_message_delivery=True,
                dead_letter_queue=context_dlq,
                filter_policy={
                    'topic': sns.SubscriptionFilter(conditions=self.topics)
                }
            )
        )


class SnsTopicDomainEventChannelHook(IDomainEventChannelHook):

    def __init__(
        self, 
        channel: SnsTopicChannel
    ) -> None:
        self.channel = channel

    def bind(self, context: IContext):
        if isinstance(context, LambdaContextBase):
            self._bind_lambda_context(context)
        else:
            cdk.ValidationError('context-domaineventchannel incompatible')

    def _bind_lambda_context(self, context: LambdaContextBase):
        context_function = context.function
        channel_topic = self.channel.topic

        context_function.add_environment('DOMAIN_EVENT_CHANNEL_SERVICE', 'AWS::SNS::Topic')
        context_function.add_environment('DOMAIN_EVENT_CHANNEL_TOPIC_ARN', channel_topic.topic_arn)
        channel_topic.grant_publish(context_function)


class SnsTopicIntegrationEventChannelHook(IIntegrationEventChannelHook):

    def __init__(
        self,
        channel: SnsTopicChannel
    ) -> None:
        self.channel = channel

    def bind(self, context: IContext):
        if isinstance(context, LambdaContextBase):
            self._bind_lambda_context(context)
        else:
            cdk.ValidationError('context-integrationeventchannel incompatible')

    def _bind_lambda_context(self, context: LambdaContextBase):
        context_function = context.function
        channel_topic = self.channel.topic

        context_function.add_environment('INTEGRATION_EVENT_CHANNEL_SERVICE', 'AWS::SNS::Topic')
        context_function.add_environment('INTEGRATION_EVENT_CHANNEL_TOPIC_ARN', channel_topic.topic_arn)
        channel_topic.grant_publish(context_function)
