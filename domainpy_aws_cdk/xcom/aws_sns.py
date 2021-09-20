import typing

from aws_cdk import core as cdk
from aws_cdk import aws_sns as sns

from domainpy_aws_cdk.xcom.base import ChannelBase


class SnsTopicChannel(ChannelBase):
    class Import(ChannelBase):
        def __init__(self, scope: cdk.Construct, id: str, topic_arn: str):
            super().__init__(scope, id)

            self.topic = sns.Topic.from_topic_arn(self, 'topic', topic_arn)
    
    @classmethod
    def bring(cls, scope: cdk.Construct, id: str, export_name: str) -> Import:
        topic = cdk.Fn.import_value(f'{export_name}TopicArn')

        return SnsTopicChannel.Import(scope, id, topic)

    def __init__(
        self, 
        scope: cdk.Construct, 
        id: str, 
        *, 
        export_name: typing.Optional[str] = None
    ) -> None:
        super().__init__(scope, id)

        if export_name is None:
            export_name = ''

        self.topic = sns.Topic(self, 'topic')

        if export_name is not None:
            cdk.CfnOutput(self, 'topic-arn',
                export_name=f'{export_name}TopicArn',
                value=self.topic.topic_arn
            )
