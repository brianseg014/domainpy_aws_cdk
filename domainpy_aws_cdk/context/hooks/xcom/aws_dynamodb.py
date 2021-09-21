

from domainpy_aws_cdk.context.base import IContext, IChannelHook
from domainpy_aws_cdk.context.aws_lambda import LambdaContextBase
from domainpy_aws_cdk.xcom.aws_dynamodb import DynamoDBTableChannel


class DynamoDBTableChannelHook(IChannelHook):

    def __init__(
        self,
        channel_name: str,
        channel: DynamoDBTableChannel
    ) -> None:
        self.channel_name = channel_name
        self.channel = channel

    def bind(self, context: IContext):
        if isinstance(context, LambdaContextBase):
            self._bind_lambda_context(context)
        else:
            raise Exception('context-channel incompatible')

    def _bind_lambda_context(self, context: LambdaContextBase):
        context_function = context.microservice
        channel_table = self.channel.table

        context_function.add_environment(f'{self.channel_name}_SERVICE', 'AWS::DynamoDB::Table')
        context_function.add_environment(f'{self.channel_name}_TABLE_NAME', channel_table.table_name)
        channel_table.grant_read_write_data(context_function)
