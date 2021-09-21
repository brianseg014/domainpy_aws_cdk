
from aws_cdk import core as cdk

from domainpy_aws_cdk.context.base import IContext, IEventStoreHook
from domainpy_aws_cdk.context.aws_lambda import LambdaContextBase
from domainpy_aws_cdk.eventstore.aws_dynamodb import DynamoDBTableEventStore


class DynamoDBTableEventStoreHook(IEventStoreHook):

    def __init__(
        self,
        event_store: DynamoDBTableEventStore
    ) -> None:
        self.event_store = event_store

    def bind(self, context: IContext):
        if isinstance(context, LambdaContextBase):
            self._bind_lambda_context(context)
        else:
            raise cdk.ValidationError('context-eventstore incompatible')

    def _bind_lambda_context(self, context: LambdaContextBase):
        function = context.function

        function.add_environment('EVENT_STORE_SERVICE', 'AWS::DynamoDB::Table')
        function.add_environment('EVENT_STORE_TABLE_NAME', self.event_store.table.table_name)
        self.event_store.table.grant_read_write_data(function)
